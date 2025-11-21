"""
Portfolio Time Series Database Manager

Store and manage portfolio time series in database for advanced analytics.
Provides functions to calculate, store, and query portfolio values over time.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from SQL.setup_db import create_app, db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PortfolioTimeSeriesDB:
    """Manage portfolio time series in database"""
    
    def __init__(self):
        self.app = create_app()
    
    def update_client_timeseries(self, client_code, date=None):
        """
        Calculate and store portfolio value for a client on a specific date.
        
        Args:
            client_code: Client code
            date: Date (YYYY-MM-DD) - defaults to latest NAV date
        
        Returns:
            dict: Portfolio value record inserted
        """
        if date is None:
            # Get latest NAV date
            with self.app.app_context():
                result = db.session.execute(text(
                    "SELECT MAX(date) FROM mf_nav_history"
                ))
                date = result.scalar()
        
        with self.app.app_context():
            # Get holdings for this client
            holdings_query = """
                SELECT 
                    h.isin,
                    h.quantity,
                    h.avg_nav,
                    s.scheme_name
                FROM holdings h
                LEFT JOIN mf_fund s ON h.isin = s.isin
                WHERE h.client_code = :client_code
                AND h.quantity > 0
            """
            
            holdings_df = pd.read_sql(
                holdings_query,
                db.session.bind,
                params={'client_code': client_code}
            )
            
            if holdings_df.empty:
                logger.warning(f"No holdings for {client_code}")
                return None
            
            # Get NAV for each holding on this date
            isins = holdings_df['isin'].tolist()
            isins_str = "','".join(isins)
            
            nav_query = f"""
                SELECT DISTINCT ON (isin)
                    isin, nav, date
                FROM mf_nav_history
                WHERE isin IN ('{isins_str}')
                AND date <= '{date}'
                ORDER BY isin, date DESC
            """
            
            nav_df = pd.read_sql(nav_query, db.session.bind)
            
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
                avg_nav = float(holding['avg_nav']) if holding['avg_nav'] else None
                
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
            
            # Get previous day's value for calculating change
            prev_query = """
                SELECT portfolio_value
                FROM portfolio_timeseries
                WHERE client_code = :client_code
                AND date < :date
                ORDER BY date DESC
                LIMIT 1
            """
            
            prev_result = db.session.execute(
                text(prev_query),
                {'client_code': client_code, 'date': date}
            )
            prev_row = prev_result.fetchone()
            
            if prev_row:
                prev_value = float(prev_row[0])
                day_change = total_value - prev_value
                day_change_pct = (day_change / prev_value) * 100 if prev_value > 0 else 0
            else:
                day_change = 0
                day_change_pct = 0
            
            # Calculate cumulative return (if invested value available)
            if total_invested > 0:
                cumulative_return_pct = ((total_value - total_invested) / total_invested) * 100
            else:
                cumulative_return_pct = None
            
            # Insert/Update portfolio time series
            upsert_query = """
                INSERT INTO portfolio_timeseries 
                    (client_code, date, portfolio_value, invested_value, 
                     day_change, day_change_pct, cumulative_return_pct, 
                     holdings_count, updated_at)
                VALUES 
                    (:client_code, :date, :portfolio_value, :invested_value,
                     :day_change, :day_change_pct, :cumulative_return_pct,
                     :holdings_count, NOW())
                ON CONFLICT (client_code, date)
                DO UPDATE SET
                    portfolio_value = EXCLUDED.portfolio_value,
                    invested_value = EXCLUDED.invested_value,
                    day_change = EXCLUDED.day_change,
                    day_change_pct = EXCLUDED.day_change_pct,
                    cumulative_return_pct = EXCLUDED.cumulative_return_pct,
                    holdings_count = EXCLUDED.holdings_count,
                    updated_at = NOW()
            """
            
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
            
            db.session.execute(text(upsert_query), record)
            
            # Insert holdings snapshot
            for snapshot in holdings_snapshot:
                snapshot_query = """
                    INSERT INTO portfolio_holdings_snapshot
                        (client_code, date, isin, quantity, nav, value)
                    VALUES
                        (:client_code, :date, :isin, :quantity, :nav, :value)
                    ON CONFLICT (client_code, date, isin)
                    DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        nav = EXCLUDED.nav,
                        value = EXCLUDED.value
                """
                db.session.execute(text(snapshot_query), snapshot)
            
            db.session.commit()
            
            logger.info(f"Updated time series for {client_code} on {date}: ₹{total_value:,.2f}")
            return record
    
    def update_all_clients_timeseries(self, date=None):
        """
        Update portfolio time series for all clients.
        
        Args:
            date: Date (YYYY-MM-DD) - defaults to latest NAV date
        """
        with self.app.app_context():
            # Get all clients with holdings
            result = db.session.execute(text(
                "SELECT DISTINCT client_code FROM holdings WHERE quantity > 0"
            ))
            clients = [row[0] for row in result]
            
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
        
        Args:
            client_code: Client code
            days_back: Number of days to backfill
        """
        with self.app.app_context():
            # Get date range from NAV history
            query = text("""
                SELECT DISTINCT date
                FROM mf_nav_history
                WHERE date >= CURRENT_DATE - INTERVAL ':days days'
                ORDER BY date
            """)
            
            result = db.session.execute(
                text(f"SELECT DISTINCT date FROM mf_nav_history WHERE date >= CURRENT_DATE - INTERVAL '{days_back} days' ORDER BY date")
            )
            dates = [row[0] for row in result]
            
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
        
        Args:
            client_code: Client code
            days: Last N days
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with time series
        """
        with self.app.app_context():
            query = """
                SELECT 
                    date,
                    portfolio_value,
                    invested_value,
                    day_change,
                    day_change_pct,
                    cumulative_return_pct,
                    holdings_count
                FROM portfolio_timeseries
                WHERE client_code = :client_code
            """
            
            params = {'client_code': client_code}
            
            if days:
                query += " AND date >= CURRENT_DATE - INTERVAL ':days days'"
                params['days'] = days
            
            if start_date:
                query += " AND date >= :start_date"
                params['start_date'] = start_date
            
            if end_date:
                query += " AND date <= :end_date"
                params['end_date'] = end_date
            
            query += " ORDER BY date"
            
            return pd.read_sql(text(query), db.session.bind, params=params)
    
    def get_all_clients_on_date(self, date):
        """Get portfolio values for all clients on a specific date"""
        with self.app.app_context():
            query = """
                SELECT 
                    client_code,
                    portfolio_value,
                    day_change,
                    day_change_pct,
                    cumulative_return_pct
                FROM portfolio_timeseries
                WHERE date = :date
                ORDER BY portfolio_value DESC
            """
            
            return pd.read_sql(text(query), db.session.bind, params={'date': date})


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio Time Series Database Manager')
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
        with db_manager.app.app_context():
            result = db.session.execute(text(
                "SELECT DISTINCT client_code FROM holdings WHERE quantity > 0"
            ))
            clients = [row[0] for row in result]
        
        print(f"Backfilling {args.days} days for {len(clients)} clients...")
        for client in clients:
            print(f"\nBackfilling {client}...")
            db_manager.backfill_timeseries(client, args.days)
        print("\nBackfill completed for all clients")
    
    else:
        parser.print_help()
