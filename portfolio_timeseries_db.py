"""
Portfolio Time Series Database Manager

Store and manage portfolio time series in database for advanced analytics.
Uses SQLAlchemy ORM for all database operations.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from SQL.setup_db import create_app, db
from portfolio_models import PortfolioTimeSeries, PortfolioHoldingsSnapshot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PortfolioTimeSeriesDB:
    """Manage portfolio time series in database using SQLAlchemy ORM"""
    
    def __init__(self):
        self.app = create_app()
    
    def update_client_timeseries(self, client_code, date=None):
        """
        Calculate and store portfolio value for a client on a specific date.
        Uses SQLAlchemy ORM.
        
        Args:
            client_code: Client code
            date: Date (YYYY-MM-DD) - defaults to latest NAV date
        
        Returns:
            dict: Portfolio value record inserted
        """
        with self.app.app_context():
            from SQL.data.models import Holding, Fund, NavHistory
            
            if date is None:
                # Get latest NAV date using ORM
                date = db.session.query(func.max(NavHistory.date)).scalar()
            
            # Get holdings for this client using ORM
            holdings_query = (
                db.session.query(
                    Holding.isin,
                    Holding.quantity,
                    Holding.avg_nav,
                    Fund.scheme_name
                )
                .outerjoin(Fund, Holding.isin == Fund.isin)
                .filter(
                    Holding.client_code == client_code,
                    Holding.quantity > 0
                )
            )
            
            holdings_df = pd.read_sql(holdings_query.statement, db.session.bind)
            
            if holdings_df.empty:
                logger.warning(f"No holdings for {client_code}")
                return None
            
            # Get latest NAV for each holding on this date using ORM
            isins = holdings_df['isin'].tolist()
            
            # Subquery to get latest NAV for each ISIN up to target date
            nav_subquery = (
                db.session.query(
                    NavHistory.isin,
                    NavHistory.nav,
                    NavHistory.date,
                    func.row_number().over(
                        partition_by=NavHistory.isin,
                        order_by=NavHistory.date.desc()
                    ).label('rn')
                )
                .filter(
                    NavHistory.isin.in_(isins),
                    NavHistory.date <= date
                )
                .subquery()
            )
            
            nav_query = (
                db.session.query(
                    nav_subquery.c.isin,
                    nav_subquery.c.nav,
                    nav_subquery.c.date
                )
                .filter(nav_subquery.c.rn == 1)
            )
            
            nav_df = pd.read_sql(nav_query.statement, db.session.bind)
            
            if nav_df.empty:
                logger.warning(f"No NAV data for {client_code} on {date}")
                return None
            
            # Calculate portfolio value
            total_value = 0
            total_invested = 0
            holdings_snapshot = []
            
            for _, holding in holdings_df.iterrows():
                isin = holding['isin']
                quantity = float(holding['quantity'])
                avg_nav = float(holding['avg_nav']) if pd.notna(holding['avg_nav']) else None
                
                nav_row = nav_df[nav_df['isin'] == isin]
                if nav_row.empty:
                    continue
                
                current_nav = float(nav_row.iloc[0]['nav'])
                value = quantity * current_nav
                total_value += value
                
                if avg_nav:
                    total_invested += quantity * avg_nav
                
                # Store holding snapshot
                holdings_snapshot.append({
                    'client_code': client_code,
                    'date': date,
                    'isin': isin,
                    'quantity': quantity,
                    'nav': current_nav,
                    'value': value
                })
            
            if total_value == 0:
                logger.warning(f"Zero portfolio value for {client_code} on {date}")
                return None
            
            # Get previous day's value using ORM
            prev_record = (
                db.session.query(PortfolioTimeSeries)
                .filter(
                    PortfolioTimeSeries.client_code == client_code,
                    PortfolioTimeSeries.date < date
                )
                .order_by(PortfolioTimeSeries.date.desc())
                .first()
            )
            
            if prev_record:
                prev_value = float(prev_record.portfolio_value)
                day_change = total_value - prev_value
                day_change_pct = (day_change / prev_value) * 100 if prev_value > 0 else 0
            else:
                day_change = 0
                day_change_pct = 0
            
            # Calculate cumulative return
            if total_invested > 0:
                cumulative_return_pct = ((total_value - total_invested) / total_invested) * 100
            else:
                cumulative_return_pct = None
            
            # Upsert portfolio time series using PostgreSQL dialect
            stmt = insert(PortfolioTimeSeries).values(
                client_code=client_code,
                date=date,
                portfolio_value=total_value,
                invested_value=total_invested if total_invested > 0 else None,
                day_change=day_change,
                day_change_pct=day_change_pct,
                cumulative_return_pct=cumulative_return_pct,
                holdings_count=len(holdings_snapshot),
                updated_at=datetime.utcnow()
            )
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['client_code', 'date'],
                set_=dict(
                    portfolio_value=stmt.excluded.portfolio_value,
                    invested_value=stmt.excluded.invested_value,
                    day_change=stmt.excluded.day_change,
                    day_change_pct=stmt.excluded.day_change_pct,
                    cumulative_return_pct=stmt.excluded.cumulative_return_pct,
                    holdings_count=stmt.excluded.holdings_count,
                    updated_at=stmt.excluded.updated_at
                )
            )
            
            db.session.execute(stmt)
            
            # Insert holdings snapshots
            for snapshot in holdings_snapshot:
                snapshot_stmt = insert(PortfolioHoldingsSnapshot).values(**snapshot)
                
                snapshot_stmt = snapshot_stmt.on_conflict_do_update(
                    index_elements=['client_code', 'date', 'isin'],
                    set_=dict(
                        quantity=snapshot_stmt.excluded.quantity,
                        nav=snapshot_stmt.excluded.nav,
                        value=snapshot_stmt.excluded.value
                    )
                )
                
                db.session.execute(snapshot_stmt)
            
            db.session.commit()
            
            record = {
                'client_code': client_code,
                'date': date,
                'portfolio_value': total_value,
                'invested_value': total_invested if total_invested > 0 else None,
                'day_change': day_change,
                'day_change_pct': day_change_pct,
                'cumulative_return_pct': cumulative_return_pct,
                'holdings_count': len(holdings_snapshot)
            }
            
            logger.info(f"Updated time series for {client_code} on {date}: ₹{total_value:,.2f}")
            return record
    
    def update_all_clients_timeseries(self, date=None):
        """
        Update portfolio time series for all clients.
        Uses SQLAlchemy ORM.
        
        Args:
            date: Date (YYYY-MM-DD) - defaults to latest NAV date
        """
        with self.app.app_context():
            from SQL.data.models import Holding
            
            # Get all clients with holdings using ORM
            clients = (
                db.session.query(Holding.client_code.distinct())
                .filter(Holding.quantity > 0)
                .all()
            )
            clients = [c[0] for c in clients]
            
            logger.info(f"Updating time series for {len(clients)} clients")
            
            success_count = 0
            for client_code in clients:
                try:
                    record = self.update_client_timeseries(client_code, date)
                    if record:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Error updating {client_code}: {e}")
            
            logger.info(f"Successfully updated {success_count}/{len(clients)} clients")
    
    def backfill_timeseries(self, client_code, days_back=365):
        """
        Backfill historical portfolio time series.
        Uses SQLAlchemy ORM.
        
        Args:
            client_code: Client code
            days_back: Number of days to backfill
        """
        with self.app.app_context():
            from SQL.data.models import NavHistory
            
            # Get date range from NAV history using ORM
            cutoff_date = datetime.now().date() - timedelta(days=days_back)
            
            dates = (
                db.session.query(NavHistory.date.distinct())
                .filter(NavHistory.date >= cutoff_date)
                .order_by(NavHistory.date)
                .all()
            )
            dates = [d[0] for d in dates]
            
            logger.info(f"Backfilling {len(dates)} days for {client_code}")
            
            for i, date in enumerate(dates):
                try:
                    self.update_client_timeseries(client_code, date)
                    if (i + 1) % 50 == 0:
                        logger.info(f"Progress: {i+1}/{len(dates)} days")
                except Exception as e:
                    logger.error(f"Error on {date}: {e}")
            
            logger.info(f"Backfill completed for {client_code}")
    
    def get_timeseries(self, client_code, days=None, start_date=None, end_date=None):
        """
        Get portfolio time series from database.
        Uses SQLAlchemy ORM.
        
        Args:
            client_code: Client code
            days: Last N days
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with time series
        """
        with self.app.app_context():
            query = (
                db.session.query(
                    PortfolioTimeSeries.date,
                    PortfolioTimeSeries.portfolio_value,
                    PortfolioTimeSeries.invested_value,
                    PortfolioTimeSeries.day_change,
                    PortfolioTimeSeries.day_change_pct,
                    PortfolioTimeSeries.cumulative_return_pct,
                    PortfolioTimeSeries.holdings_count
                )
                .filter(PortfolioTimeSeries.client_code == client_code)
            )
            
            if days:
                cutoff = datetime.now().date() - timedelta(days=days)
                query = query.filter(PortfolioTimeSeries.date >= cutoff)
            
            if start_date:
                query = query.filter(PortfolioTimeSeries.date >= start_date)
            
            if end_date:
                query = query.filter(PortfolioTimeSeries.date <= end_date)
            
            query = query.order_by(PortfolioTimeSeries.date)
            
            return pd.read_sql(query.statement, db.session.bind)
    
    def get_all_clients_on_date(self, date):
        """
        Get portfolio values for all clients on a specific date.
        Uses SQLAlchemy ORM.
        """
        with self.app.app_context():
            query = (
                db.session.query(
                    PortfolioTimeSeries.client_code,
                    PortfolioTimeSeries.portfolio_value,
                    PortfolioTimeSeries.day_change,
                    PortfolioTimeSeries.day_change_pct,
                    PortfolioTimeSeries.cumulative_return_pct
                )
                .filter(PortfolioTimeSeries.date == date)
                .order_by(PortfolioTimeSeries.portfolio_value.desc())
            )
            
            return pd.read_sql(query.statement, db.session.bind)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio Time Series Database Manager (SQLAlchemy ORM)')
    parser.add_argument('--update-all', action='store_true', help='Update all clients for latest date')
    parser.add_argument('--client', type=str, help='Update specific client')
    parser.add_argument('--backfill-all', action='store_true', help='Backfill all clients')
    parser.add_argument('--days', type=int, default=365, help='Days to backfill (default: 365)')
    
    args = parser.parse_args()
    
    db_manager = PortfolioTimeSeriesDB()
    
    if args.update_all:
        print("Updating time series for all clients...")
        db_manager.update_all_clients_timeseries()
        print("Update completed")
    
    elif args.client:
        print(f"Updating time series for {args.client}...")
        record = db_manager.update_client_timeseries(args.client)
        if record:
            print(f"Portfolio Value: ₹{record['portfolio_value']:,.2f}")
            print(f"Day Change: ₹{record['day_change']:,.2f} ({record['day_change_pct']:.2f}%)")
    
    elif args.backfill_all:
        from SQL.data.models import Holding
        
        with db_manager.app.app_context():
            clients = (
                db.session.query(Holding.client_code.distinct())
                .filter(Holding.quantity > 0)
                .all()
            )
            clients = [c[0] for c in clients]
        
        print(f"Backfilling {args.days} days for {len(clients)} clients...")
        for client in clients:
            print(f"\nBackfilling {client}...")
            db_manager.backfill_timeseries(client, args.days)
        print("\nBackfill completed for all clients")
    
    else:
        parser.print_help()
