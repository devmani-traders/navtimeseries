"""
Portfolio Value Calculator

Calculates current portfolio value, returns, and P&L for client holdings
using the latest NAV data from the mf_nav_history table.
"""

import pandas as pd
import logging
from datetime import datetime
from SQL.setup_db import create_app, db
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PortfolioCalculator:
    """Calculate portfolio values and returns for client holdings"""
    
    def __init__(self):
        self.app = create_app()
    
    def get_latest_navs(self):
        """
        Get the latest NAV for each ISIN from mf_nav_history table.
        
        Returns:
            dict: {isin: {'nav': float, 'date': date}}
        """
        with self.app.app_context():
            query = text("""
                SELECT DISTINCT ON (isin) 
                    isin, 
                    nav, 
                    date as nav_date
                FROM mf_nav_history
                ORDER BY isin, date DESC
            """)
            
            result = db.session.execute(query)
            
            latest_navs = {}
            for row in result:
                latest_navs[row.isin] = {
                    'nav': float(row.nav),
                    'date': row.nav_date
                }
            
            logger.info(f"Fetched latest NAV for {len(latest_navs)} ISINs")
            return latest_navs
    
    def calculate_portfolio_values(self, client_code=None):
        """
        Calculate current portfolio value for all holdings or specific client.
        
        Args:
            client_code: Optional client code to filter (None = all clients)
        
        Returns:
            DataFrame with columns:
                - client_code
                - isin
                - scheme_name
                - quantity
                - avg_nav (invested NAV)
                - current_nav
                - invested_value
                - current_value
                - profit_loss
                - return_pct
                - nav_date
        """
        with self.app.app_context():
            # Base query
            query = """
                SELECT 
                    h.client_code,
                    h.isin,
                    s.scheme_name,
                    h.folio_no,
                    h.quantity,
                    h.avg_nav,
                    h.type,
                    h.last_updated
                FROM holdings h
                LEFT JOIN mf_fund s ON h.isin = s.isin
                WHERE h.quantity > 0
            """
            
            if client_code:
                query += f" AND h.client_code = '{client_code}'"
            
            query += " ORDER BY h.client_code, h.isin"
            
            # Execute query
            holdings_df = pd.read_sql(query, db.session.bind)
            
            if holdings_df.empty:
                logger.warning("No holdings found")
                return pd.DataFrame()
            
            logger.info(f"Processing {len(holdings_df)} holdings")
            
            # Get latest NAVs
            latest_navs = self.get_latest_navs()
            
            # Calculate values
            results = []
            for _, holding in holdings_df.iterrows():
                isin = holding['isin']
                quantity = float(holding['quantity'])
                avg_nav = float(holding['avg_nav']) if holding['avg_nav'] else None
                
                # Get current NAV
                nav_info = latest_navs.get(isin)
                if not nav_info:
                    logger.warning(f"No NAV found for ISIN {isin}")
                    continue
                
                current_nav = nav_info['nav']
                nav_date = nav_info['date']
                
                # Calculate values
                current_value = quantity * current_nav
                invested_value = quantity * avg_nav if avg_nav else None
                
                # Calculate P&L and returns
                if invested_value and invested_value > 0:
                    profit_loss = current_value - invested_value
                    return_pct = (profit_loss / invested_value) * 100
                else:
                    profit_loss = None
                    return_pct = None
                
                results.append({
                    'client_code': holding['client_code'],
                    'isin': isin,
                    'scheme_name': holding['scheme_name'],
                    'folio_no': holding['folio_no'],
                    'quantity': quantity,
                    'avg_nav': avg_nav,
                    'current_nav': current_nav,
                    'invested_value': invested_value,
                    'current_value': current_value,
                    'profit_loss': profit_loss,
                    'return_pct': return_pct,
                    'nav_date': nav_date,
                    'holding_type': holding['type']
                })
            
            return pd.DataFrame(results)
    
    def get_client_summary(self, client_code):
        """
        Get portfolio summary for a specific client.
        
        Args:
            client_code: Client code
        
        Returns:
            dict: Summary with total invested, current value, P&L, returns
        """
        portfolio_df = self.calculate_portfolio_values(client_code)
        
        if portfolio_df.empty:
            return {
                'client_code': client_code,
                'total_holdings': 0,
                'total_invested': 0,
                'total_current_value': 0,
                'total_profit_loss': 0,
                'overall_return_pct': 0
            }
        
        summary = {
            'client_code': client_code,
            'total_holdings': len(portfolio_df),
            'total_invested': portfolio_df['invested_value'].sum(),
            'total_current_value': portfolio_df['current_value'].sum(),
            'total_profit_loss': portfolio_df['profit_loss'].sum(),
        }
        
        # Overall return percentage
        if summary['total_invested'] > 0:
            summary['overall_return_pct'] = (
                summary['total_profit_loss'] / summary['total_invested']
            ) * 100
        else:
            summary['overall_return_pct'] = 0
        
        return summary
    
    def calculate_portfolio_timeseries(self, client_code, start_date=None, end_date=None):
        """
        Calculate portfolio value time series for a client.
        Shows portfolio value on each date based on holdings and historical NAV.
        
        Args:
            client_code: Client code
            start_date: Start date (YYYY-MM-DD) - defaults to earliest NAV date
            end_date: End date (YYYY-MM-DD) - defaults to latest NAV date
        
        Returns:
            DataFrame with columns:
                - date
                - total_value (portfolio value on that date)
                - day_change (absolute change from previous day)
                - day_change_pct (% change from previous day)
        """
        with self.app.app_context():
            # Get holdings for this client
            holdings_query = """
                SELECT 
                    h.isin,
                    h.quantity,
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
                logger.warning(f"No holdings found for client {client_code}")
                return pd.DataFrame()
            
            logger.info(f"Calculating time series for {len(holdings_df)} holdings")
            
            # Get NAV history for all ISINs in portfolio
            isins = holdings_df['isin'].tolist()
            isins_str = "','".join(isins)
            
            nav_query = f"""
                SELECT 
                    isin,
                    date,
                    nav
                FROM mf_nav_history
                WHERE isin IN ('{isins_str}')
            """
            
            if start_date:
                nav_query += f" AND date >= '{start_date}'"
            if end_date:
                nav_query += f" AND date <= '{end_date}'"
            
            nav_query += " ORDER BY date, isin"
            
            nav_history_df = pd.read_sql(nav_query, db.session.bind)
            
            if nav_history_df.empty:
                logger.warning("No NAV history found")
                return pd.DataFrame()
            
            # Pivot to get NAV for each ISIN on each date
            nav_pivot = nav_history_df.pivot(index='date', columns='isin', values='nav')
            
            # Forward fill missing NAV values (use last known NAV)
            nav_pivot = nav_pivot.fillna(method='ffill')
            
            # Calculate portfolio value for each date
            portfolio_values = []
            
            for date, nav_row in nav_pivot.iterrows():
                total_value = 0
                holdings_detail = []
                
                for _, holding in holdings_df.iterrows():
                    isin = holding['isin']
                    quantity = float(holding['quantity'])
                    
                    if isin in nav_row.index and pd.notna(nav_row[isin]):
                        nav = float(nav_row[isin])
                        value = quantity * nav
                        total_value += value
                        
                        holdings_detail.append({
                            'isin': isin,
                            'scheme_name': holding['scheme_name'],
                            'quantity': quantity,
                            'nav': nav,
                            'value': value
                        })
                
                portfolio_values.append({
                    'date': date,
                    'total_value': total_value,
                    'holdings_count': len(holdings_detail)
                })
            
            # Convert to DataFrame
            timeseries_df = pd.DataFrame(portfolio_values)
            
            if timeseries_df.empty:
                return timeseries_df
            
            # Sort by date
            timeseries_df = timeseries_df.sort_values('date')
            
            # Calculate daily changes
            timeseries_df['day_change'] = timeseries_df['total_value'].diff()
            timeseries_df['day_change_pct'] = (
                timeseries_df['total_value'].pct_change() * 100
            )
            
            # Calculate cumulative return from start
            first_value = timeseries_df['total_value'].iloc[0]
            timeseries_df['cumulative_return_pct'] = (
                (timeseries_df['total_value'] / first_value - 1) * 100
            )
            
            logger.info(f"Generated time series with {len(timeseries_df)} data points")
            
            return timeseries_df
    
    def calculate_monthly_returns(self, client_code, start_date=None, end_date=None):
        """
        Calculate monthly portfolio returns.
        
        Args:
            client_code: Client code
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with columns:
                - month (YYYY-MM)
                - start_value
                - end_value
                - monthly_return_pct
                - best_day (date with highest gain)
                - worst_day (date with highest loss)
        """
        timeseries_df = self.calculate_portfolio_timeseries(
            client_code, start_date, end_date
        )
        
        if timeseries_df.empty:
            return pd.DataFrame()
        
        # Ensure date is datetime
        timeseries_df['date'] = pd.to_datetime(timeseries_df['date'])
        
        # Group by month
        timeseries_df['month'] = timeseries_df['date'].dt.to_period('M')
        
        monthly_results = []
        
        for month, group in timeseries_df.groupby('month'):
            start_value = group['total_value'].iloc[0]
            end_value = group['total_value'].iloc[-1]
            monthly_return = ((end_value / start_value) - 1) * 100 if start_value > 0 else 0
            
            # Find best and worst days
            best_day = group.loc[group['day_change'].idxmax(), 'date'] if len(group) > 1 else None
            worst_day = group.loc[group['day_change'].idxmin(), 'date'] if len(group) > 1 else None
            
            monthly_results.append({
                'month': str(month),
                'start_value': start_value,
                'end_value': end_value,
                'monthly_return_pct': monthly_return,
                'best_day': best_day,
                'worst_day': worst_day,
                'trading_days': len(group)
            })
        
        return pd.DataFrame(monthly_results)

    
    def export_portfolio_report(self, output_path, client_code=None):
        """
        Export portfolio valuation report to CSV.
        
        Args:
            output_path: Path to save CSV
            client_code: Optional client code filter
        """
        portfolio_df = self.calculate_portfolio_values(client_code)
        
        if portfolio_df.empty:
            logger.warning("No data to export")
            return
        
        # Format for display
        portfolio_df['invested_value'] = portfolio_df['invested_value'].round(2)
        portfolio_df['current_value'] = portfolio_df['current_value'].round(2)
        portfolio_df['profit_loss'] = portfolio_df['profit_loss'].round(2)
        portfolio_df['return_pct'] = portfolio_df['return_pct'].round(2)
        
        portfolio_df.to_csv(output_path, index=False)
        logger.info(f"Portfolio report exported to {output_path}")
        
        return portfolio_df


def update_holding_current_values():
    """
    Update holdings table with current NAV and values.
    Adds computed columns if needed.
    
    Note: This requires adding columns to holdings table:
        - current_nav (Numeric)
        - current_value (Numeric)
        - profit_loss (Numeric)
        - return_pct (Numeric)
        - nav_as_of_date (Date)
    """
    calculator = PortfolioCalculator()
    
    with calculator.app.app_context():
        # Get all portfolio values
        portfolio_df = calculator.calculate_portfolio_values()
        
        if portfolio_df.empty:
            logger.warning("No holdings to update")
            return
        
        # Update each holding (if you add computed columns to holdings table)
        for _, row in portfolio_df.iterrows():
            update_query = text("""
                UPDATE holdings
                SET 
                    last_updated = :last_updated
                WHERE client_code = :client_code 
                AND isin = :isin
            """)
            
            db.session.execute(update_query, {
                'client_code': row['client_code'],
                'isin': row['isin'],
                'last_updated': datetime.utcnow()
            })
        
        db.session.commit()
        logger.info(f"Updated {len(portfolio_df)} holdings")


if __name__ == "__main__":
    import sys
    
    calculator = PortfolioCalculator()
    
    # Example usage
    if len(sys.argv) > 1:
        client_code = sys.argv[1]
        
        # Get client summary
        summary = calculator.get_client_summary(client_code)
        print(f"\n{'='*60}")
        print(f"Portfolio Summary for {client_code}")
        print(f"{'='*60}")
        print(f"  Total Holdings: {summary['total_holdings']}")
        print(f"  Total Invested: ₹{summary['total_invested']:,.2f}")
        print(f"  Current Value: ₹{summary['total_current_value']:,.2f}")
        print(f"  Profit/Loss: ₹{summary['total_profit_loss']:,.2f}")
        print(f"  Overall Return: {summary['overall_return_pct']:.2f}%")
        
        # Generate time series
        print(f"\n{'='*60}")
        print("Generating Portfolio Time Series...")
        print(f"{'='*60}")
        
        timeseries_df = calculator.calculate_portfolio_timeseries(client_code)
        
        if not timeseries_df.empty:
            # Show latest 10 days
            print("\nLast 10 Days:")
            print(timeseries_df[['date', 'total_value', 'day_change', 'day_change_pct', 'cumulative_return_pct']].tail(10).to_string(index=False))
            
            # Export time series
            ts_filename = f'portfolio_timeseries_{client_code}.csv'
            timeseries_df.to_csv(ts_filename, index=False)
            print(f"\nTime series exported to: {ts_filename}")
            
            # Calculate monthly returns
            monthly_df = calculator.calculate_monthly_returns(client_code)
            
            if not monthly_df.empty:
                print("\n" + "="*60)
                print("Monthly Returns:")
                print("="*60)
                print(monthly_df[['month', 'start_value', 'end_value', 'monthly_return_pct']].to_string(index=False))
                
                # Export monthly returns
                monthly_filename = f'portfolio_monthly_{client_code}.csv'
                monthly_df.to_csv(monthly_filename, index=False)
                print(f"\nMonthly returns exported to: {monthly_filename}")
        
        # Export detailed holdings report
        calculator.export_portfolio_report(
            f'portfolio_holdings_{client_code}.csv',
            client_code
        )
        print(f"\nDetailed holdings exported to: portfolio_holdings_{client_code}.csv")
        
    else:
        # Export all portfolios
        calculator.export_portfolio_report('portfolio_all_clients.csv')
        print("Exported portfolio report for all clients")

