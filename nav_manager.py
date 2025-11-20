import pandas as pd
import requests
import os
import re
import logging
from datetime import datetime, timedelta
import config
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(config.BASE_DIR, "pipeline.log")),
        logging.StreamHandler()
    ]
)

class NavManager:
    def __init__(self):
        self.nav_all_file = config.NAV_ALL_FILE
        self.nav_all_url = config.AMFI_NAV_ALL_URL
        self.historical_url = config.AMFI_NAV_HISTORY_URL
        self.output_folder = config.HISTORICAL_NAV_DIR
        
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)
            
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Accept": "*/*"
        }

    def download_nav_all(self):
        """Downloads the NAVAll.txt file from AMFI with retry logic."""
        logging.info(f"Downloading NAVAll.txt from {self.nav_all_url}...")
        for attempt in range(3):
            try:
                response = requests.get(self.nav_all_url, headers=self.headers, timeout=30)
                response.raise_for_status()
                with open(self.nav_all_file, 'w') as f:
                    f.write(response.text)
                logging.info(f"Downloaded NAVAll file to {self.nav_all_file}")
                return True
            except Exception as e:
                logging.warning(f"Attempt {attempt+1} failed to download NAVAll: {e}")
                time.sleep(2)
        
        logging.error("Failed to download NAVAll file after 3 attempts.")
        return False

    def get_scheme_code_map(self):
        """Parses NAVAll.txt and returns a dictionary mapping ISIN to Scheme Code."""
        if not os.path.exists(self.nav_all_file):
            if not self.download_nav_all():
                return {}

        isin_map = {}
        try:
            with open(self.nav_all_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or ";" not in line:
                        continue
                    
                    parts = line.split(';')
                    if len(parts) >= 6:
                        scheme_code = parts[0]
                        isin_payout = parts[1]
                        isin_reinv = parts[2]
                        
                        # Map both ISINs if they exist
                        if isin_payout and isin_payout != '-':
                            isin_map[isin_payout] = scheme_code
                        if isin_reinv and isin_reinv != '-':
                            isin_map[isin_reinv] = scheme_code
                            
        except Exception as e:
            logging.error(f"Error parsing NAVAll file: {e}")
            
        return isin_map

    def update_master_list_with_codes(self, master_list_path):
        """Updates the master list CSV with Scheme Codes using NAVAll data."""
        try:
            df = pd.read_csv(master_list_path)
        except Exception as e:
            logging.error(f"Failed to read master list: {e}")
            return None
        
        # Check if 'Scheme Code' column exists, if not create it
        if 'Scheme Code' not in df.columns:
            df['Scheme Code'] = None
            
        # Identify missing codes
        # We treat empty strings and NaN as missing
        df['Scheme Code'] = df['Scheme Code'].astype(str).replace('nan', '').replace('None', '')
        missing_mask = df['Scheme Code'] == ''
        
        if not missing_mask.any():
            logging.info("All ISINs already have Scheme Codes.")
            return df

        logging.info("Found ISINs without Scheme Codes. Updating...")
        isin_map = self.get_scheme_code_map()
        
        updated_count = 0
        def get_code(row):
            nonlocal updated_count
            current_code = row['Scheme Code']
            if current_code and current_code != '':
                return current_code
            
            new_code = isin_map.get(row['ISIN'], '')
            if new_code:
                updated_count += 1
            return new_code

        df['Scheme Code'] = df.apply(get_code, axis=1)
        
        # Save back
        df.to_csv(master_list_path, index=False)
        logging.info(f"Updated master list saved to {master_list_path}. Updated {updated_count} records.")
        return df

    def _build_history_url(self, scheme_code, from_date, to_date):
        return f"{self.historical_url}?query_type=historical_period&from_date={from_date}&to_date={to_date}&sd_id={scheme_code}"

    def _fetch_data_chunk(self, scheme_code, start_date, end_date):
        """Fetches a chunk of data from AMFI."""
        # Updated date format to %Y-%m-%d as per new script
        fmt_start = start_date.strftime("%Y-%m-%d")
        fmt_end = end_date.strftime("%Y-%m-%d")
        url = self._build_history_url(scheme_code, fmt_start, fmt_end)
        logging.info(f"Requesting URL: {url}")
        
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.headers, timeout=30)
                if resp.ok:
                    data = resp.json()
                    return data.get("data", {}).get("nav_groups", [{}])[0].get("historical_records", [])
                else:
                    logging.warning(f"API returned {resp.status_code} for {scheme_code}. Response: {resp.text}")
            except Exception as e:
                logging.warning(f"Error fetching data for {scheme_code} ({fmt_start} to {fmt_end}): {e}")
                time.sleep(1)
        return []

    def load_nav_all_data(self):
        """Parses NAVAll.txt and returns a dictionary of {scheme_code: {'date': date_obj, 'nav': float}}."""
        if not os.path.exists(self.nav_all_file):
             if not self.download_nav_all():
                 return {}

        nav_data = {}
        try:
            with open(self.nav_all_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or ";" not in line:
                        continue
                    
                    parts = line.split(';')
                    if len(parts) >= 6:
                        try:
                            scheme_code = parts[0]
                            nav_str = parts[4]
                            date_str = parts[5]
                            
                            if nav_str == 'N.A.' or not nav_str:
                                continue
                                
                            nav = float(nav_str)
                            # Date format in NAVAll is usually dd-MMM-yyyy (e.g., 20-Nov-2025)
                            # But let's handle potential variations if needed, though usually it's consistent.
                            date_obj = datetime.strptime(date_str, "%d-%b-%Y")
                            
                            nav_data[scheme_code] = {
                                'date': date_obj,
                                'nav': nav
                            }
                        except ValueError:
                            continue # Skip rows with parse errors
                            
        except Exception as e:
            logging.error(f"Error parsing NAVAll file for data: {e}")
            
        return nav_data

    def ensure_data_updated(self, scheme_code, scheme_name, nav_all_data=None):
        """
        Ensures local data is up to date for the given scheme.
        Uses nav_all_data for single-day updates if provided and applicable.
        """
        filename = f"{scheme_code}.csv"
        filepath = os.path.join(self.output_folder, filename)
        
        existing_df, last_date = self._load_existing_data(filepath)
        
        # 1. Try NAVAll Append (Optimization)
        if self._try_update_from_navall(existing_df, scheme_code, scheme_name, nav_all_data, last_date, filepath):
            return True
            
        # 2. Fallback to API
        return self._update_from_api(existing_df, scheme_code, scheme_name, last_date, filepath)

    def _load_existing_data(self, filepath):
        """Loads existing data from CSV and returns (df, last_date)."""
        existing_df = pd.DataFrame()
        last_date = None
        
        if os.path.exists(filepath):
            try:
                existing_df = pd.read_csv(filepath)
                if not existing_df.empty:
                    existing_df['Date'] = pd.to_datetime(existing_df['Date'])
                    last_date = existing_df['Date'].max()
            except Exception as e:
                logging.error(f"Error reading existing file {filepath}: {e}. Will re-download.")
                existing_df = pd.DataFrame()
        return existing_df, last_date

    def _save_data(self, df, filepath, scheme_name):
        """Deduplicates, sorts, and saves the DataFrame."""
        # Deduplicate and Sort
        final_df = df.drop_duplicates(subset=['Date'], keep='last')
        final_df = final_df.sort_values('Date')
        
        # Save
        final_df.to_csv(filepath, index=False)
        logging.info(f"Saved {len(final_df)} records for {scheme_name} to {filepath}")

    def _try_update_from_navall(self, existing_df, scheme_code, scheme_name, nav_all_data, last_date, filepath):
        """Attempts to update data using NAVAll.txt. Returns True if successful."""
        if not last_date or not nav_all_data:
            return False
            
        latest_info = nav_all_data.get(scheme_code)
        if not latest_info:
            return False
            
        nav_all_date = latest_info['date']
        nav_all_val = latest_info['nav']
        
        if nav_all_date > last_date:
            gap = (nav_all_date - last_date).days
            
            # If gap is small (<= 4 days), we assume it's safe to append.
            # This handles weekends and short holidays.
            if gap <= 4:
                logging.info(f"Appending latest NAV from NAVAll for {scheme_name} ({nav_all_date.date()})")
                new_row = pd.DataFrame([{'Date': nav_all_date, 'NAV': nav_all_val}])
                final_df = pd.concat([existing_df, new_row])
                self._save_data(final_df, filepath, scheme_name)
                return True
                
        return False

    def _update_from_api(self, existing_df, scheme_code, scheme_name, last_date, filepath):
        """Updates data using the AMFI API."""
        end_date = datetime.now()
        
        if last_date:
            start_date = last_date + timedelta(days=1)
            if start_date > end_date:
                logging.info(f"Data for {scheme_name} ({scheme_code}) is already up to date.")
                return True
            logging.info(f"Updating {scheme_name} ({scheme_code}) from {start_date.date()} to {end_date.date()} using API")
        else:
            start_date = end_date - timedelta(days=365 * config.YEARS_BACK)
            logging.info(f"Downloading full history for {scheme_name} ({scheme_code}) from {start_date.date()}")

        # Fetch Data in Chunks
        fetch_ranges = []
        curr = start_date
        while curr <= end_date:
            # AMFI requires strictly less than 5 years. Using 5 years - 7 days to be safe.
            next_end = curr + timedelta(days=365*5 - 7) 
            if next_end > end_date:
                next_end = end_date
            fetch_ranges.append((curr, next_end))
            curr = next_end + timedelta(days=1)
            
        new_records = []
        for s, e in fetch_ranges:
            records = self._fetch_data_chunk(scheme_code, s, e)
            new_records.extend(records)
            
        if not new_records:
            if last_date:
                logging.info(f"No new data found for {scheme_name} since {last_date.date()}.")
                return True
            else:
                logging.warning(f"No data found for {scheme_name} ({scheme_code})")
                return False

        # Process and Merge
        processed_data = []
        for record in new_records:
            processed_data.append({
                "Date": record.get("date"),
                "NAV": record.get("nav")
            })
            
        new_df = pd.DataFrame(processed_data)
        new_df['Date'] = pd.to_datetime(new_df['Date'], format="%Y-%m-%d")
        new_df['NAV'] = pd.to_numeric(new_df['NAV'], errors='coerce')
        new_df = new_df.dropna(subset=['NAV']) # Drop invalid NAVs
        
        if not existing_df.empty:
            final_df = pd.concat([existing_df, new_df])
        else:
            final_df = new_df
            
        self._save_data(final_df, filepath, scheme_name)
        return True
