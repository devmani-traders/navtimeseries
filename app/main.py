import pandas as pd
import os
import logging
from app import config
from app.services.nav_manager import NavManager
from app.utils.storage import storage
# from app.services.return_calculator import ReturnCalculator # To be implemented

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(master_list_path=None):
    # Setup logging
    setup_logging()
    logging.info("Starting NAV Pipeline...")
    
    if master_list_path is None:
        master_list_path = config.ISIN_MASTER_LIST

    # Initialize Manager
    manager = NavManager()

    # 1. Load and Update Master List
    if not storage.exists(master_list_path):
        print(f"Error: Master list not found at {master_list_path}")
        return

    print("Downloading latest NAVAll.txt...")
    manager.download_nav_all()

    print("Checking ISIN mappings...")
    df = manager.update_master_list_with_codes(master_list_path)
    
    if df.empty:
        print("No ISINs found or error reading master list.")
        return

    # Load NAVAll data for hybrid update
    print("Parsing NAVAll.txt for daily updates...")
    nav_all_data = manager.load_nav_all_data()

    # 2. Update Historical Data
    print("Updating historical data...")
    for index, row in df.iterrows():
        scheme_code = str(row['Scheme Code'])
        scheme_name = row['Scheme Name']
        
        if pd.isna(scheme_code) or scheme_code == 'nan':
            logging.warning(f"Skipping {scheme_name} (No Scheme Code)")
            continue
            
        manager.ensure_data_updated(scheme_code, scheme_name, nav_all_data)

    print("Data update complete.")
    
    # 3. Calculate Returns
    print("Calculating returns...")
    from app.services.return_calculator import ReturnCalculator
    calculator = ReturnCalculator()
    # We need to pass the list of ISINs/Schemes we just processed to the calculator
    # But the calculator currently scans the directory. 
    # For this test, we might want to restrict it, but scanning the dir is fine 
    # as long as we only care about the report being generated.
    results = calculator.compute_all_returns(df, config.HISTORICAL_NAV_DIR)
    
    if not results.empty:
        storage.write_csv(results, config.NAV_RETURNS_REPORT)
        print(f"Returns report saved to {config.NAV_RETURNS_REPORT}")
    else:
        print("No returns calculated.")

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    main(path)
