import os

# Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data Directories
NAV_DATA_DIR = os.path.join(BASE_DIR, "navdata")
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



