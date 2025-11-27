import os

# Base Directory (Parent of app/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Data Directories
NAV_DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORICAL_NAV_DIR = os.path.join(NAV_DATA_DIR, "historical_nav")
OUTPUT_DIR = os.path.join(NAV_DATA_DIR, "returns")

# Files
ISIN_MASTER_LIST = os.path.join(NAV_DATA_DIR, "isin_master_list.csv")
NAV_ALL_FILE = os.path.join(NAV_DATA_DIR, "NAVAll.txt")
NAV_RETURNS_REPORT = os.path.join(OUTPUT_DIR, "nav_returns_report.csv")

# URLs
AMFI_NAV_ALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
AMFI_NAV_HISTORY_URL = "https://www.amfiindia.com/api/nav-history"

# Settings
YEARS_BACK = 10

# Database
DB_URL = 'postgresql://postgres:mutual%40fund%40pro12@34.57.196.130:5432/mutualfundpro'


# Storage Configuration
USE_GCS = os.getenv('USE_GCS', 'False').lower() == 'true'
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'nav-timeseries-data')

# If using GCS, these paths become prefixes
if USE_GCS:
    NAV_DATA_DIR = ""  # Root of bucket
    HISTORICAL_NAV_DIR = "historical_nav"
    OUTPUT_DIR = "returns"
    ISIN_MASTER_LIST = "isin_master_list.csv"
    NAV_ALL_FILE = "NAVAll.txt"
    NAV_RETURNS_REPORT = "returns/nav_returns_report.csv"
