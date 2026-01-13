import sys
import os
import logging
import pandas as pd
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.setup import create_app, db
from app.database.models import Fund
from app.services.nav_manager import NavManager
from app.utils.storage import storage
from app import config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def populate_master_from_db():
    """
    Populates data/isin_master_list.csv based on funds currently in the database.
    It fetches all ISINs from the 'mf_fund' table and matches them against NAVAll.txt
    to get the latest Scheme Name and Scheme Code.
    """
    app = create_app()
    
    with app.app_context():
        # 1. Fetch all ISINs from DB
        logger.info("Fetching existing ISINs from database...")
        try:
            # Using model query as requested
            funds = db.session.query(Fund.isin).all()
            db_isins = set(f.isin for f in funds)
            
            if not db_isins:
                logger.warning("No funds found in the database! Aborting.")
                return False
                
            logger.info(f"Found {len(db_isins)} distinct ISINs in the database.")
            
        except Exception as e:
            logger.error(f"Error fetching funds from DB: {e}")
            return False

    # 2. Get NAVAll data for metadata lookup
    manager = NavManager()
    if not os.path.exists(config.NAV_ALL_FILE):
        logger.info("NAVAll.txt not found. Downloading...")
        if not manager.download_nav_all():
            logger.error("Failed to download NAVAll.txt")
            return False

    logger.info("Reading NAVAll.txt for metadata lookup...")
    matched_data = []
    
    try:
        with open(config.NAV_ALL_FILE, 'r') as f:
            content = f.read()
            
        for line in content.splitlines():
            line = line.strip()
            if not line or ";" not in line:
                continue
            
            # Format: Scheme Code;ISIN Div Payout/Growth;ISIN Div Reinv;Scheme Name;NAV;Date
            parts = line.split(';')
            if len(parts) >= 6:
                scheme_code = parts[0]
                isin_payout = parts[1]
                isin_reinv = parts[2]
                scheme_name = parts[3]
                
                # Check if this record matches any ISIN in our DB
                matched_isin = None
                
                if isin_payout in db_isins:
                    matched_isin = isin_payout
                elif isin_reinv in db_isins:
                    matched_isin = isin_reinv
                
                if matched_isin:
                    matched_data.append({
                        'ISIN': matched_isin,
                        'Scheme Code': scheme_code,
                        'Scheme Name': scheme_name
                    })
                    # Remove from set to track what we found (optional, but good for reporting missing)
                    # db_isins.discard(matched_isin) # Don't discard if we want to allow duplicates or just track
                    
    except Exception as e:
        logger.error(f"Error parsing NAVAll.txt: {e}")
        return False

    # 3. Write to CSV
    if matched_data:
        df = pd.DataFrame(matched_data)
        # Sort by Scheme Name for better readability
        df = df.sort_values('Scheme Name')
        
        output_path = config.ISIN_MASTER_LIST
        storage.write_csv(df, output_path)
        logger.info(f"Successfully wrote {len(df)} records to {output_path}")
        
        # Check if we missed any
        found_isins = set(df['ISIN'])
        missing_isins = db_isins - found_isins
        if missing_isins:
            logger.warning(f"Warning: {len(missing_isins)} ISINs from DB were NOT found in NAVAll.txt: {missing_isins}")
        
        return True
    else:
        logger.warning("No matching records found in NAVAll.txt for the DB ISINs.")
        return False

if __name__ == "__main__":
    populate_master_from_db()
