import pandas as pd
import numpy as np
from datetime import timedelta
from app import config
from app.utils.storage import storage

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
        
        print(f"Latest Date: {latest_date.date()}")
        print(f"Latest NAV: {latest_nav}")

        from dateutil.relativedelta import relativedelta
        
        periods = {
            '1D': relativedelta(days=1),
            '1M': relativedelta(months=1),
            '3M': relativedelta(months=3),
            '6M': relativedelta(months=6),
            'YTD': 'YTD',
            '1Y': relativedelta(years=1),
            '2Y': relativedelta(years=2),
            '3Y': relativedelta(years=3),
            '5Y': relativedelta(years=5),
            '10Y': relativedelta(years=10),
            'Inception': 'Inception'
        }
        
        results = {
            'Date': latest_date.date(),
            'NAV': latest_nav
        }
        
        print(f"{'Period':<10} | {'Target Date':<12} | {'Actual Date':<12} | {'Past NAV':<10} | {'Abs Return':<10} | {'CAGR':<10}")
        print("-" * 80)

        for period_name, delta in periods.items():
            if period_name == 'YTD':
                start_of_year = pd.Timestamp(year=latest_date.year, month=1, day=1)
                target_date = start_of_year - timedelta(days=1) # Last day of previous year
            elif period_name == 'Inception':
                target_date = df['Date'].iloc[0]
            else:
                target_date = latest_date - delta
            
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
            
            # Calculate years difference for CAGR
            days_diff = (latest_date - past_date).days
            years = days_diff / 365.25
            
            if period_name == 'Inception':
                if years > 1:
                    cagr = (latest_nav / past_nav) ** (1 / years) - 1
                else:
                    cagr = abs_return
            elif hasattr(delta, 'years') and delta.years >= 1:
                # Use the actual time difference for the exponent to be precise
                cagr = (latest_nav / past_nav) ** (1 / years) - 1
            elif isinstance(delta, relativedelta) and (delta.years > 0 or (delta.months or 0) >= 12):
                 if years >= 1:
                    cagr = (latest_nav / past_nav) ** (1 / years) - 1

            results[f'{period_name}_Abs'] = abs_return
            if not np.isnan(cagr):
                results[f'{period_name}_CAGR'] = cagr
            
            cagr_str = f"{cagr:.4%}" if not np.isnan(cagr) else ""
            t_date_str = str(target_date.date()) if hasattr(target_date, 'date') else str(target_date)
            p_date_str = str(past_date.date())
            
            print(f"{period_name:<10} | {t_date_str:<12} | {p_date_str:<12} | {past_nav:<10.4f} | {abs_return:<10.4%} | {cagr_str:<10}")

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
                # Use storage abstraction to read from GCS or local
                nav_df = storage.read_csv(filepath)
                returns = self.calculate_returns(nav_df)
                
                # Add metadata
                returns['ISIN'] = isin
                returns['Scheme Name'] = scheme_name
                returns['Scheme Code'] = scheme_code
                
                all_results.append(returns)
            except Exception as e:
                print(f"Error calculating returns for {scheme_name}: {e}")
                
        return pd.DataFrame(all_results)
