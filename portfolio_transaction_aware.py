"""
Transaction-Aware Portfolio Time Series

This version uses transaction history to accurately reconstruct portfolio
holdings on each historical date, ensuring transactions are properly reflected.
Uses SQLAlchemy ORM for database operations.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from sqlalchemy import func, case
from sqlalchemy.dialects.postgresql import insert
from SQL.setup_db import create_app, db
from portfolio_models import PortfolioTimeSeries, PortfolioHoldingsSnapshot, Transaction

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TransactionAwarePortfolioCalculator:
    """
    Calculate portfolio time series using transaction history.
    Accurately reconstructs holdings on each date.
    """
    
    def __init__(self):
        self.app = create_app()
    
    def get_holdings_on_date(self, client_code, target_date):
        """
        Reconstruct holdings as of a specific date using transaction history.
        Uses SQLAlchemy ORM.
        
        Args:
            client_code: Client code
            target_date: Date to reconstruct holdings for
        
        Returns:
            DataFrame with columns: isin, quantity, avg_nav, inception_date
        """
        with self.app.app_context():
            # Build query using SQLAlchemy ORM
            buy_units = case(
                (Transaction.transaction_type.in_(['BUY', 'PURCHASE']), Transaction.units),
                else_=0
            )
            
            sell_units = case(
                (Transaction.transaction_type.in_(['SELL', 'REDEMPTION']), Transaction.units),
                else_=0
            )
            
            buy_value = case(
                (Transaction.transaction_type.in_(['BUY', 'PURCHASE']), Transaction.units * Transaction.nav),
                else_=0
            )
            
            # Subquery for transaction summary per folio
            from sqlalchemy.orm import aliased
            from SQL.data.models import Fund  # Assuming your Fund model location
            
            subquery = (
                db.session.query(
                    Transaction.isin,
                    Transaction.folio_no,
                    func.sum(buy_units - sell_units).label('quantity'),
                    (func.sum(buy_value) / func.nullif(func.sum(buy_units), 0)).label('avg_nav'),
                    func.min(Transaction.transaction_date).label('inception_date')
                )
                .filter(
                    Transaction.client_code == client_code,
                    Transaction.transaction_date <= target_date
                )
                .group_by(Transaction.isin, Transaction.folio_no)
                .having(func.sum(buy_units - sell_units) > 0)
                .subquery()
            )
            
            # Aggregate across folios and join with fund details
            query = (
                db.session.query(
                    subquery.c.isin,
                    Fund.scheme_name,
                    func.sum(subquery.c.quantity).label('quantity'),
                    (func.sum(subquery.c.quantity * subquery.c.avg_nav) / 
                     func.sum(subquery.c.quantity)).label('avg_nav'),
                    func.min(subquery.c.inception_date).label('inception_date')
                )
                .outerjoin(Fund, subquery.c.isin == Fund.isin)
                .group_by(subquery.c.isin, Fund.scheme_name)
                .having(func.sum(subquery.c.quantity) > 0.0001)
                .order_by(subquery.c.isin)
            )
            
            df = pd.read_sql(query.statement, db.session.bind)
            
            logger.debug(f"Holdings on {target_date} for {client_code}: {len(df)} positions")
            return df
    
    def calculate_portfolio_value_on_date(self, client_code, target_date):
        """
        Calculate portfolio value on a specific date using transaction history.
        
        Args:
            client_code: Client code
            target_date: Date to calculate for
        
        Returns:
            dict: Portfolio metrics
        """
        with self.app.app_context():
            # Get holdings as they were on this date
            holdings_df = self.get_holdings_on_date(client_code, target_date)
            
            if holdings_df.empty:
                logger.debug(f"No holdings for {client_code} on {target_date}")
                return None
            
            # Get NAV for each holding on this date
            isins = holdings_df['isin'].tolist()
            isins_str = "','".join(isins)
            
            nav_query = f"""
                SELECT DISTINCT ON (isin)
                    isin, nav, date as nav_date
                FROM mf_nav_history
                WHERE isin IN ('{isins_str}')
                AND date <= '{target_date}'
                ORDER BY isin, date DESC
            """
            
            nav_df = pd.read_sql(nav_query, db.session.bind)
            
            if nav_df.empty:
                logger.warning(f"No NAV data available for {client_code} on {target_date}")
                return None
            
            # Calculate portfolio value
            total_value = 0
            total_invested = 0
            holdings_detail = []
            
            for _, holding in holdings_df.iterrows():
                isin = holding['isin']
                quantity = float(holding['quantity'])
                avg_nav = float(holding['avg_nav']) if pd.notna(holding['avg_nav']) else None
                
                nav_row = nav_df[nav_df['isin'] == isin]
                if nav_row.empty:
                    logger.warning(f"No NAV for {isin} on {target_date}")
                    continue
                
                current_nav = float(nav_row.iloc[0]['nav'])
                value = quantity * current_nav
                total_value += value
                
                if avg_nav:
                    invested = quantity * avg_nav
                    total_invested += invested
                
                holdings_detail.append({
                    'isin': isin,
                    'scheme_name': holding['scheme_name'],
                    'quantity': quantity,
                    'avg_nav': avg_nav,
                    'current_nav': current_nav,
                    'value': value,
                    'invested': invested if avg_nav else None
                })
            
            if total_value == 0:
                return None
            
            return {
                'date': target_date,
                'portfolio_value': total_value,
                'invested_value': total_invested if total_invested > 0 else None,
                'holdings_count': len(holdings_detail),
                'holdings_detail': holdings_detail
            }
    
    def update_timeseries_for_date(self, client_code, target_date):
        """
        Calculate and store portfolio time series for a specific date.
        Uses transaction history and SQLAlchemy ORM.
        """
        with self.app.app_context():
            result = self.calculate_portfolio_value_on_date(client_code, target_date)
            
            if not result:
                logger.debug(f"No portfolio value for {client_code} on {target_date}")
                return None
            
            # Get previous day's value using ORM
            prev_record = (
                db.session.query(PortfolioTimeSeries)
                .filter(
                    PortfolioTimeSeries.client_code == client_code,
                    PortfolioTimeSeries.date < target_date
                )
                .order_by(PortfolioTimeSeries.date.desc())
                .first()
            )
            
            if prev_record:
                prev_value = float(prev_record.portfolio_value)
                day_change = result['portfolio_value'] - prev_value
                day_change_pct = (day_change / prev_value) * 100 if prev_value > 0 else 0
            else:
                day_change = 0
                day_change_pct = 0
            
            # Calculate cumulative return
            if result['invested_value'] and result['invested_value'] > 0:
                cumulative_return_pct = (
                    (result['portfolio_value'] - result['invested_value']) / 
                    result['invested_value']
                ) * 100
            else:
                cumulative_return_pct = None
            
            # Upsert portfolio time series using PostgreSQL dialect
            stmt = insert(PortfolioTimeSeries).values(
                client_code=client_code,
                date=target_date,
                portfolio_value=result['portfolio_value'],
                invested_value=result['invested_value'],
                day_change=day_change,
                day_change_pct=day_change_pct,
                cumulative_return_pct=cumulative_return_pct,
                holdings_count=result['holdings_count'],
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
            
            # Store holdings snapshots
            for holding in result['holdings_detail']:
                snapshot_stmt = insert(PortfolioHoldingsSnapshot).values(
                    client_code=client_code,
                    date=target_date,
                    isin=holding['isin'],
                    quantity=holding['quantity'],
                    nav=holding['current_nav'],
                    value=holding['value']
                )
                
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
            
            logger.info(
                f"Updated {client_code} on {target_date}: "
                f"₹{result['portfolio_value']:,.2f} ({result['holdings_count']} holdings)"
            )
            
            return result
    
    def backfill_client_timeseries(self, client_code, days_back=None):
        """
        Backfill time series using transaction history.
        Starts from first transaction date. Uses SQLAlchemy ORM.
        
        Args:
            client_code: Client code
            days_back: Optional limit on how far back (default: from first transaction)
        """
        with self.app.app_context():
            # Get date range using ORM
            from SQL.data.models import NavHistory
            
            first_tx = (
                db.session.query(func.min(Transaction.transaction_date))
                .filter(Transaction.client_code == client_code)
                .scalar()
            )
            
            last_nav = (
                db.session.query(func.max(NavHistory.date))
                .scalar()
            )
            
            if not first_tx:
                logger.warning(f"No transactions for {client_code}")
                return
            
            start_date = first_tx
            end_date = last_nav
            
            if days_back:
                start_date = max(start_date, end_date - timedelta(days=days_back))
            
            logger.info(f"Backfilling {client_code} from {start_date} to {end_date}")
            
            # Get all NAV dates in range using ORM
            nav_dates = (
                db.session.query(NavHistory.date.distinct())
                .filter(NavHistory.date.between(start_date, end_date))
                .order_by(NavHistory.date)
                .all()
            )
            
            total_dates = len(nav_dates)
            logger.info(f"Processing {total_dates} dates")
            
            success_count = 0
            for i, (date,) in enumerate(nav_dates):
                try:
                    result = self.update_timeseries_for_date(client_code, date)
                    if result:
                        success_count += 1
                    
                    if (i + 1) % 50 == 0:
                        logger.info(f"Progress: {i+1}/{total_dates} ({success_count} successful)")
                        
                except Exception as e:
                    logger.error(f"Error on {date}: {e}")
            
            logger.info(f"Backfill completed: {success_count}/{total_dates} dates")
    
    def verify_holdings_consistency(self, client_code):
        """
        Verify that current holdings table matches transaction history.
        Returns discrepancies if any. Uses SQLAlchemy ORM.
        """
        with self.app.app_context():
            # Calculate holdings from transactions
            buy_units = case(
                (Transaction.transaction_type.in_(['BUY', 'PURCHASE']), Transaction.units),
                else_=0
            )
            
            sell_units = case(
                (Transaction.transaction_type.in_(['SELL', 'REDEMPTION']), Transaction.units),
                else_=0
            )
            
            tx_holdings = (
                db.session.query(
                    Transaction.isin,
                    func.sum(buy_units - sell_units).label('tx_quantity')
                )
                .filter(Transaction.client_code == client_code)
                .group_by(Transaction.isin)
            ).subquery()
            
            # Get current holdings from holdings table
            from SQL.data.models import Holding
            
            current_holdings = (
                db.session.query(
                    Holding.isin,
                    Holding.quantity.label('current_quantity')
                )
                .filter(Holding.client_code == client_code)
            ).subquery()
            
            # Full outer join to find discrepancies
            query = (
                db.session.query(
                    func.coalesce(tx_holdings.c.isin, current_holdings.c.isin).label('isin'),
                    func.coalesce(tx_holdings.c.tx_quantity, 0).label('transaction_quantity'),
                    func.coalesce(current_holdings.c.current_quantity, 0).label('holdings_quantity'),
                    func.abs(
                        func.coalesce(tx_holdings.c.tx_quantity, 0) - 
                        func.coalesce(current_holdings.c.current_quantity, 0)
                    ).label('diff')
                )
                .select_from(tx_holdings)
                .outerjoin(current_holdings, tx_holdings.c.isin == current_holdings.c.isin)
                .filter(
                    func.abs(
                        func.coalesce(tx_holdings.c.tx_quantity, 0) - 
                        func.coalesce(current_holdings.c.current_quantity, 0)
                    ) > 0.0001
                )
            )
            
            df = pd.read_sql(query.statement, db.session.bind)
            
            if df.empty:
                logger.info(f"✓ Holdings consistent with transactions for {client_code}")
                return None
            else:
                logger.warning(f"✗ Found {len(df)} discrepancies for {client_code}")
                return df


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Transaction-Aware Portfolio Calculator')
    parser.add_argument('--client', type=str, help='Client code')
    parser.add_argument('--backfill', action='store_true', help='Backfill time series')
    parser.add_argument('--days', type=int, help='Days to backfill')
    parser.add_argument('--verify', action='store_true', help='Verify holdings consistency')
    parser.add_argument('--date', type=str, help='Calculate for specific date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    calc = TransactionAwarePortfolioCalculator()
    
    if args.verify:
        if args.client:
            discrepancies = calc.verify_holdings_consistency(args.client)
            if discrepancies is not None:
                print("\nDiscrepancies found:")
                print(discrepancies)
        else:
            print("Please specify --client")
    
    elif args.backfill:
        if args.client:
            calc.backfill_client_timeseries(args.client, args.days)
        else:
            print("Please specify --client")
    
    elif args.date:
        if args.client:
            result = calc.calculate_portfolio_value_on_date(args.client, args.date)
            if result:
                print(f"\nPortfolio on {args.date}:")
                print(f"  Value: ₹{result['portfolio_value']:,.2f}")
                print(f"  Invested: ₹{result['invested_value']:,.2f}" if result['invested_value'] else "  Invested: N/A")
                print(f"  Holdings: {result['holdings_count']}")
        else:
            print("Please specify --client")
    
    else:
        parser.print_help()
