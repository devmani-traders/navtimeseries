import pandas as pd
import os
import logging
import sys
from datetime import datetime
from utils import get_all_filenames, process_nav_data
from sqlalchemy import text


# Add parent directory to path to enable imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from setup_db import db, create_app
from SQL.data.models import Fund, FundFactSheet, FundReturns, FundHolding, NavHistory, BSEScheme

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_existing_isins():
    """Fetches all valid ISINs from the mf_fund table."""
    try:
        result = db.session.execute(text("SELECT isin FROM mf_fund"))
        return {row[0] for row in result}
    except Exception as e:
        logger.error(f"Error fetching ISINs from mf_fund: {e}")
        return set()


def import_returns_data(df, existing_isins=None ,clear_existing=False):
        """
        Import fund returns data from DataFrame using bulk upsert strategy
        
        Args:
            df: DataFrame containing returns data
            existing_isins (set): Set of ISINs that exist in the database for validation
            clear_existing (bool): Whether to clear existing data before import
            
        Returns:
            dict: Statistics about the import operation
        """
        logger.info(f"Importing returns data with {len(df)} records")

        try:
            # Clean data
            df = df.dropna(subset=['ISIN'])

            if clear_existing and len(df) > 0:
                # Get list of ISINs to clear
                isins = df['ISIN'].unique().tolist()

                # Delete existing returns for these ISINs
                FundReturns.query.filter(FundReturns.isin.in_(isins)).delete(
                    synchronize_session=False)

                db.session.commit()
                logger.info(
                    f"Cleared existing returns data for {len(isins)} ISINs")

            # Track statistics
            stats = {
                'returns_created': 0,
                'returns_updated': 0,
                'funds_not_found': 0,
                'total_rows_processed': len(df)
            }

            # Get all valid fund ISINs for validation
            valid_fund_isins = existing_isins

            # Prepare records for bulk upsert
            returns_records = []

            for _, row in df.iterrows():
                isin = str(row['ISIN']).strip()

                if not isin or isin.lower() == 'nan':
                    continue

                # Skip if fund doesn't exist
                if isin not in valid_fund_isins:
                    logger.warning(
                        f"Skipping returns for {isin}: Fund not found in database"
                    )
                    stats['funds_not_found'] += 1
                    continue

                # Create returns record
                returns_record = {
                    'isin':
                    isin,
                    'return_1m':
                    float(row.get('1M Return', 0))
                    if not pd.isna(row.get('1M Return')) else None,
                    'return_3m':
                    float(row.get('3M Return', 0))
                    if not pd.isna(row.get('3M Return')) else None,
                    'return_6m':
                    float(row.get('6M Return', 0))
                    if not pd.isna(row.get('6M Return')) else None,
                    'return_ytd':
                    float(row.get('YTD Return', 0))
                    if not pd.isna(row.get('YTD Return')) else None,
                    'return_1y':
                    float(row.get('1Y Return', 0))
                    if not pd.isna(row.get('1Y Return')) else None,
                    'return_3y':
                    float(row.get('3Y Return', 0))
                    if not pd.isna(row.get('3Y Return')) else None,
                    'return_5y':
                    float(row.get('5Y Return', 0))
                    if not pd.isna(row.get('5Y Return')) else None,
                    'return_3y_carg':
                    float(row.get('3Y CAGR', 0))
                    if not pd.isna(row.get('3Y CAGR')) else None,
                    'return_5y_carg':
                    float(row.get('5Y CAGR', 0))
                    if not pd.isna(row.get('5Y CAGR')) else None,
                    'return_10y_carg':
                    float(row.get('10Y CAGR', 0))
                    if not pd.isna(row.get('10Y CAGR')) else None,
                    'return_since_inception':
                    float(row.get('Inception Return', 0))
                    if not pd.isna(row.get('Inception Return')) else None,
                    'return_since_inception_carg':
                    float(row.get('Inception CAGR', 0))
                    if not pd.isna(row.get('Inception CAGR')) else None
                }
                returns_records.append(returns_record)

            # Bulk upsert returns using PostgreSQL
            if returns_records:
                from sqlalchemy.dialects.postgresql import insert

                stmt = insert(FundReturns.__table__).values(returns_records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['isin'],
                    set_=dict(return_1m=stmt.excluded.return_1m,
                              return_3m=stmt.excluded.return_3m,
                              return_6m=stmt.excluded.return_6m,
                              return_ytd=stmt.excluded.return_ytd,
                              return_1y=stmt.excluded.return_1y,
                              return_3y=stmt.excluded.return_3y,
                              return_5y=stmt.excluded.return_5y,
                              return_3y_carg=stmt.excluded.return_3y_carg,
                              return_5y_carg=stmt.excluded.return_5y_carg,
                              return_10y_carg=stmt.excluded.return_10y_carg,
                              return_since_inception=stmt.excluded.return_since_inception,
                              return_since_inception_carg=stmt.excluded.return_since_inception_carg))
                db.session.execute(stmt)
                stats['returns_created'] = len(returns_records)

            # Commit all changes
            db.session.commit()
            logger.info(f"Returns import completed: {stats}")

            return stats

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error importing returns data: {e}")
            raise

def import_nav_data_upsert(df, clear_existing=False, existing_isins=None, batch_size=10000):
        """
        Import NAV data from DataFrame using bulk upsert strategy
        
        Args:
            df: DataFrame containing NAV data
            clear_existing (bool): Whether to clear existing data before import
            existing_isins (set): Set of ISINs that exist in the database for validation
            batch_size (int): Number of records to process in each batch
            
        Returns:
            dict: Statistics about the import operation
        """
        logger.info(f"Importing NAV data with {len(df)} records")

        try:
            if clear_existing and len(df) > 0:
                # Clear all existing NAV data
                NavHistory.query.delete()
                db.session.commit()
                logger.info("Cleared existing NAV data")

            # Track statistics
            stats = {
                'nav_records_created': 0,
                'total_rows_processed': len(df),
                'batch_size_used': batch_size,
                'missing_funds_skipped': 0

            }

            batch_count = 0

            # Process data in batches
            total_batches = (len(df) + batch_size - 1) // batch_size
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(df))
                batch_df = df.iloc[start_idx:end_idx]
                
                logger.info(f"Processing NAV batch {batch_num + 1}/{total_batches} (rows {start_idx + 1}-{end_idx})")
                
                nav_records = []
                
                for _, row in batch_df.iterrows():
                    try:
                        isin = str(row.get('ISIN', '')).strip()
                        if not isin or isin.lower() == 'nan' or len(isin) < 8:
                            continue

                        if isin not in existing_isins:
                          stats['missing_funds_skipped'] += 1
                          continue

                        # Parse date
                        date_str = str(row.get('Date', ''))
                        if pd.notna(row.get('Date')):
                            if isinstance(row.get('Date'), datetime):
                                nav_date = row.get('Date').date()
                            else:
                                nav_date = pd.to_datetime(date_str).date()
                        else:
                            continue

                        nav_value = float(row.get('NAV', 0)) if pd.notna(
                            row.get('NAV')) else None
                        if nav_value is None:
                            continue

                        nav_record = {
                            'isin': isin,
                            'date': nav_date,
                            'nav': nav_value
                        }
                        nav_records.append(nav_record)

                    except Exception as e:
                        logger.error(f"Error processing NAV row: {e}")
                        continue
                
                # Bulk upsert NAV records using PostgreSQL
                if nav_records:
                    from sqlalchemy.dialects.postgresql import insert
                    
                    stmt = insert(NavHistory.__table__).values(nav_records)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['isin', 'date'],
                        set_=dict(nav=stmt.excluded.nav)
                    )
                    db.session.execute(stmt)
                    stats['nav_records_created'] += len(nav_records)
                    
                # Commit batch
                db.session.commit()

            logger.info(f"NAV import completed: {stats}")

            return stats

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error importing NAV data: {e}")
            raise