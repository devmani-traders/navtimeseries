"""
Transaction-Aware Portfolio Time Series

This version uses transaction history to accurately reconstruct portfolio
holdings on each historical date, ensuring transactions are properly reflected.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from SQL.setup_db import create_app, db

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
        
        Args:
            client_code: Client code
            target_date: Date to reconstruct holdings for
        
        Returns:
            DataFrame with columns: isin, quantity, avg_nav, inception_date
        """
        with self.app.app_context():
            query = """
                WITH transaction_summary AS (
                    SELECT 
                        isin,
                        folio_no,
                        -- Calculate net quantity (buys - sells)
                        SUM(CASE 
                            WHEN transaction_type IN ('BUY', 'PURCHASE') THEN units
                            WHEN transaction_type IN ('SELL', 'REDEMPTION') THEN -units
                            ELSE 0
                        END) as quantity,
                        -- Calculate weighted average NAV
                        SUM(CASE 
                            WHEN transaction_type IN ('BUY', 'PURCHASE') THEN units * nav
                            ELSE 0
                        END) / NULLIF(SUM(CASE 
                            WHEN transaction_type IN ('BUY', 'PURCHASE') THEN units
                            ELSE 0
                        END), 0) as avg_nav,
                        -- Track when first bought
                        MIN(transaction_date) as inception_date
                    FROM transactions
                    WHERE client_code = :client_code
                    AND transaction_date <= :target_date
                    GROUP BY isin, folio_no
                    HAVING SUM(CASE 
                        WHEN transaction_type IN ('BUY', 'PURCHASE') THEN units
                        WHEN transaction_type IN ('SELL', 'REDEMPTION') THEN -units
                        ELSE 0
                    END) > 0
                )
                SELECT 
                    ts.isin,
                    mf.scheme_name,
                    SUM(ts.quantity) as quantity,
                    -- Weighted average across all folios
                    SUM(ts.quantity * ts.avg_nav) / SUM(ts.quantity) as avg_nav,
                    MIN(ts.inception_date) as inception_date
                FROM transaction_summary ts
                LEFT JOIN mf_fund mf ON ts.isin = mf.isin
                GROUP BY ts.isin, mf.scheme_name
                HAVING SUM(ts.quantity) > 0.0001  -- Handle floating point precision
                ORDER BY ts.isin
            """
            
            df = pd.read_sql(
                text(query),
                db.session.bind,
                params={'client_code': client_code, 'target_date': target_date}
            )
            
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
        Uses transaction history to ensure accuracy.
        """
        with self.app.app_context():
            result = self.calculate_portfolio_value_on_date(client_code, target_date)
            
            if not result:
                logger.debug(f"No portfolio value for {client_code} on {target_date}")
                return None
            
            # Get previous day's value for calculating change
            prev_query = """
                SELECT portfolio_value
                FROM portfolio_timeseries
                WHERE client_code = :client_code
                AND date < :target_date
                ORDER BY date DESC
                LIMIT 1
            """
            
            prev_result = db.session.execute(
                text(prev_query),
                {'client_code': client_code, 'target_date': target_date}
            )
            prev_row = prev_result.fetchone()
            
            if prev_row:
                prev_value = float(prev_row[0])
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
            
            # Upsert portfolio time series
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
            
            db.session.execute(text(upsert_query), {
                'client_code': client_code,
                'date': target_date,
                'portfolio_value': result['portfolio_value'],
                'invested_value': result['invested_value'],
                'day_change': day_change,
                'day_change_pct': day_change_pct,
                'cumulative_return_pct': cumulative_return_pct,
                'holdings_count': result['holdings_count']
            })
            
            # Store holdings snapshot
            for holding in result['holdings_detail']:
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
                db.session.execute(text(snapshot_query), {
                    'client_code': client_code,
                    'date': target_date,
                    'isin': holding['isin'],
                    'quantity': holding['quantity'],
                    'nav': holding['current_nav'],
                    'value': holding['value']
                })
            
            db.session.commit()
            
            logger.info(
                f"Updated {client_code} on {target_date}: "
                f"₹{result['portfolio_value']:,.2f} ({result['holdings_count']} holdings)"
            )
            
            return result
    
    def backfill_client_timeseries(self, client_code, days_back=None):
        """
        Backfill time series using transaction history.
        Starts from first transaction date.
        
        Args:
            client_code: Client code
            days_back: Optional limit on how far back (default: from first transaction)
        """
        with self.app.app_context():
            # Get date range
            date_query = """
                SELECT 
                    MIN(transaction_date) as first_date,
                    MAX(date) as last_nav_date
                FROM transactions t
                CROSS JOIN (SELECT MAX(date) as date FROM mf_nav_history) n
                WHERE t.client_code = :client_code
            """
            
            result = db.session.execute(
                text(date_query),
                {'client_code': client_code}
            ).fetchone()
            
            if not result or not result[0]:
                logger.warning(f"No transactions for {client_code}")
                return
            
            start_date = result[0]
            end_date = result[1]
            
            if days_back:
                start_date = max(start_date, end_date - timedelta(days=days_back))
            
            logger.info(f"Backfilling {client_code} from {start_date} to {end_date}")
            
            # Get all NAV dates in range
            nav_dates_query = """
                SELECT DISTINCT date
                FROM mf_nav_history
                WHERE date BETWEEN :start_date AND :end_date
                ORDER BY date
            """
            
            dates_df = pd.read_sql(
                text(nav_dates_query),
                db.session.bind,
                params={'start_date': start_date, 'end_date': end_date}
            )
            
            total_dates = len(dates_df)
            logger.info(f"Processing {total_dates} dates")
            
            success_count = 0
            for i, row in dates_df.iterrows():
                date = row['date']
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
        Returns discrepancies if any.
        """
        with self.app.app_context():
            query = """
                WITH tx_holdings AS (
                    SELECT 
                        isin,
                        SUM(CASE 
                            WHEN transaction_type IN ('BUY', 'PURCHASE') THEN units
                            WHEN transaction_type IN ('SELL', 'REDEMPTION') THEN -units
                        END) as tx_quantity
                    FROM transactions
                    WHERE client_code = :client_code
                    GROUP BY isin
                ),
                current_holdings AS (
                    SELECT isin, quantity as current_quantity
                    FROM holdings
                    WHERE client_code = :client_code
                )
                SELECT 
                    COALESCE(tx.isin, ch.isin) as isin,
                    COALESCE(tx.tx_quantity, 0) as transaction_quantity,
                    COALESCE(ch.current_quantity, 0) as holdings_quantity,
                    ABS(COALESCE(tx.tx_quantity, 0) - COALESCE(ch.current_quantity, 0)) as diff
                FROM tx_holdings tx
                FULL OUTER JOIN current_holdings ch ON tx.isin = ch.isin
                WHERE ABS(COALESCE(tx.tx_quantity, 0) - COALESCE(ch.current_quantity, 0)) > 0.0001
            """
            
            df = pd.read_sql(
                text(query),
                db.session.bind,
                params={'client_code': client_code}
            )
            
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
