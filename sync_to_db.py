import pandas as pd
import os
import logging
from datetime import datetime
from legacy_funcations import import_returns_data, import_nav_data_upsert, get_existing_isins
from SQL.setup_db import create_app, db
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sync_daily_data(clear_existing=False):
    """
    Quick daily sync: Uploads current NAV and returns data from the returns report.
    The returns report already contains the latest NAV data, so we extract both from it.
    
    Args:
        clear_existing: Whether to clear existing data before import
    """
    app = create_app()
    
    with app.app_context():
        logger.info("=" * 60)
        logger.info("DAILY SYNC: Latest NAV + Returns")
        logger.info("=" * 60)
        
        # Get existing ISINs from database
        logger.info("Fetching existing ISINs from database...")
        existing_isins = get_existing_isins()
        logger.info(f"Found {len(existing_isins)} ISINs in database")
        
        returns_report_path = config.NAV_RETURNS_REPORT
        if not os.path.exists(returns_report_path):
            logger.error(f"Returns report not found: {returns_report_path}")
            return
        
        try:
            returns_df = pd.read_csv(returns_report_path)
            
            # 1. Extract and sync latest NAV data
            logger.info("Syncing latest NAV data from returns report...")
            nav_df = returns_df[['ISIN', 'Date', 'NAV']].copy()
            nav_df = nav_df.dropna(subset=['ISIN', 'Date', 'NAV'])
            
            if len(nav_df) > 0:
                nav_stats = import_nav_data_upsert(
                    nav_df,
                    clear_existing=False,  # Never clear for daily sync
                    existing_isins=existing_isins
                )
                logger.info(f"NAV sync completed: {nav_stats}")
            else:
                logger.warning("No NAV data found in returns report")
            
            # 2. Sync returns data
            logger.info("Syncing returns data...")
            
            # Map column names from our generated report to expected format
            column_mapping = {
                '1M_Abs': '1M Return',
                '3M_Abs': '3M Return',
                '6M_Abs': '6M Return',
                'YTD_Abs': 'YTD Return',
                '1Y_Abs': '1Y Return',
                '3Y_Abs': '3Y Return',
                '5Y_Abs': '5Y Return'
            }
            
            returns_data = returns_df.rename(columns=column_mapping)
            
            returns_stats = import_returns_data(
                returns_data,
                existing_isins=existing_isins,
                clear_existing=False  # Never clear for daily sync
            )
            logger.info(f"Returns sync completed: {returns_stats}")
            
        except Exception as e:
            logger.error(f"Error during daily sync: {e}")
            raise
        
        logger.info("=" * 60)
        logger.info("DAILY SYNC COMPLETE")
        logger.info("=" * 60)

def sync_historical_nav(isin_master_list_path=None, clear_existing=False):
    """
    Historical sync: Uploads all historical NAV data from CSV files.
    Use this for initial data load or full refresh.
    
    Args:
        isin_master_list_path: Path to ISIN master list CSV
        clear_existing: Whether to clear existing NAV data before import
    """
    if isin_master_list_path is None:
        isin_master_list_path = config.ISIN_MASTER_LIST
    
    app = create_app()
    
    with app.app_context():
        logger.info("=" * 60)
        logger.info("HISTORICAL SYNC: All NAV Data")
        logger.info("=" * 60)
        
        # Get existing ISINs from database
        logger.info("Fetching existing ISINs from database...")
        existing_isins = get_existing_isins()
        logger.info(f"Found {len(existing_isins)} ISINs in database")
        
        try:
            master_df = pd.read_csv(isin_master_list_path)
        except Exception as e:
            logger.error(f"Failed to read master list: {e}")
            return
        
        # Collect all NAV data from CSV files
        all_nav_data = []
        for index, row in master_df.iterrows():
            isin = row.get('ISIN')
            scheme_code = row.get('Scheme Code')
            
            if pd.isna(scheme_code) or pd.isna(isin):
                continue
            
            nav_filepath = os.path.join(config.HISTORICAL_NAV_DIR, f"{int(float(scheme_code))}.csv")
            if not os.path.exists(nav_filepath):
                logger.warning(f"NAV file not found: {nav_filepath}")
                continue
            
            try:
                nav_df = pd.read_csv(nav_filepath)
                nav_df['ISIN'] = isin  # Add ISIN column
                all_nav_data.append(nav_df)
                logger.info(f"Loaded {len(nav_df)} NAV records for {isin}")
            except Exception as e:
                logger.error(f"Error reading NAV file {nav_filepath}: {e}")
        
        if all_nav_data:
            # Combine all NAV data
            combined_nav_df = pd.concat(all_nav_data, ignore_index=True)
            logger.info(f"Total NAV records to sync: {len(combined_nav_df)}")
            
            # Use legacy function to import
            nav_stats = import_nav_data_upsert(
                combined_nav_df, 
                clear_existing=clear_existing,
                existing_isins=existing_isins
            )
            logger.info(f"NAV sync completed: {nav_stats}")
        else:
            logger.warning("No NAV data found to sync")
        
        logger.info("=" * 60)
        logger.info("HISTORICAL SYNC COMPLETE")
        logger.info("=" * 60)

if __name__ == "__main__":
    import sys
    
    mode = "daily"  # Default mode
    clear_existing = False
    
    # Parse command line arguments
    for arg in sys.argv[1:]:
        if arg == "--historical":
            mode = "historical"
        elif arg == "--daily":
            mode = "daily"
        elif arg == "--clear":
            clear_existing = True
    
    if mode == "daily":
        logger.info("Running in DAILY mode (latest NAV + returns from returns report)")
        sync_daily_data(clear_existing=clear_existing)
    elif mode == "historical":
        logger.info("Running in HISTORICAL mode (all NAV data from CSV files)")
        sync_historical_nav(clear_existing=clear_existing)
