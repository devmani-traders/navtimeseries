import pandas as pd
import numpy as np
from datetime import timedelta

class ReturnCalculator:
    def __init__(self):
        pass

    def calculate_returns(self, df):
        """
        Calculates returns for various periods.
        df must have 'Date' and 'NAV' columns and be sorted by Date.
        """
        if df.empty:
            return {}

        # Ensure datetime
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        
        latest_date = df['Date'].iloc[-1]
        latest_nav = df['NAV'].iloc[-1]
        
        periods = {
            '1D': 1,
            '1M': 30,
            '3M': 90,
            '6M': 180,
            'YTD': 'YTD',
            '1Y': 365,
            '2Y': 365 * 2,
            '3Y': 365 * 3,
            '5Y': 365 * 5,
            '10Y': 365 * 10,
            'Inception': 'Inception'
        }
        
        results = {
            'Date': latest_date.date(),
            'NAV': latest_nav
        }
        
        for period_name, days in periods.items():
            if period_name == 'YTD':
                start_of_year = pd.Timestamp(year=latest_date.year, month=1, day=1)
                target_date = start_of_year - timedelta(days=1) # Last day of previous year
            elif period_name == 'Inception':
                target_date = df['Date'].iloc[0]
            else:
                target_date = latest_date - timedelta(days=days)
            
            # Find closest date <= target_date
            # We look for the price on or before the target date
            past_data = df[df['Date'] <= target_date]
            
            if past_data.empty:
                results[f'{period_name}_Abs'] = np.nan
                results[f'{period_name}_CAGR'] = np.nan
                continue
                
            past_date = past_data['Date'].iloc[-1]
            past_nav = past_data['NAV'].iloc[-1]
            
            # Calculate Absolute Return
            abs_return = (latest_nav / past_nav) - 1
            
            # Calculate CAGR for periods > 1Y
            cagr = np.nan
            
            if period_name == 'Inception':
                years = (latest_date - past_date).days / 365.25
                if years > 1:
                    cagr = (latest_nav / past_nav) ** (1 / years) - 1
                else:
                    cagr = abs_return
            elif isinstance(days, int) and days >= 365:
                years = days / 365
                cagr = (latest_nav / past_nav) ** (1 / years) - 1
            else:
                # For < 1Y, CAGR is usually same as Abs (or annualized, but typically we show Abs)
                # User asked for "absolute and compounded" for > 1Y usually, but let's follow request.
                # "1Y, 2Y (absolute and compounded)"
                # For < 1Y, usually just absolute.
                pass
            
            results[f'{period_name}_Abs'] = abs_return
            if not np.isnan(cagr):
                results[f'{period_name}_CAGR'] = cagr
                
        return results

    def compute_all_returns(self, master_df, nav_folder):
        """
        Computes returns for all schemes in the master list.
        """
        all_results = []
        
        for index, row in master_df.iterrows():
            scheme_code = row.get('Scheme Code')
            scheme_name = row.get('Scheme Name')
            isin = row.get('ISIN')
            
            if pd.isna(scheme_code) or scheme_code == '':
                continue
                
            filepath = f"{nav_folder}/{str(int(float(scheme_code)))}.csv"
            try:
                nav_df = pd.read_csv(filepath)
                returns = self.calculate_returns(nav_df)
                
                # Add metadata
                returns['ISIN'] = isin
                returns['Scheme Name'] = scheme_name
                returns['Scheme Code'] = scheme_code
                
                all_results.append(returns)
            except Exception as e:
                print(f"Error calculating returns for {scheme_name}: {e}")
                
        return pd.DataFrame(all_results)
