# NAV Time Series Pipeline

A comprehensive Python pipeline for downloading, processing, and managing Indian mutual fund NAV (Net Asset Value) data with historical tracking, returns calculation, and database integration.

## 🌟 Features

- 📥 **Automated NAV Data Download** - Downloads historical NAV data from AMFI India
- 🔄 **Hybrid Update Strategy** - Efficient daily updates using NAVAll.txt with API fallback
- 📊 **Returns Calculation** - Computes absolute and CAGR returns for multiple time periods
- 🗄️ **PostgreSQL Integration** - Stores NAV history and returns in a relational database
- ⚡ **Incremental Updates** - Only downloads missing data, never redundant API calls
- 🤖 **Automated Daily Sync** - Cron-ready scripts for automated daily operations
- 📝 **Comprehensive Logging** - Detailed logs for monitoring and debugging

## 📋 Requirements

- Python 3.9+
- PostgreSQL database
- Internet connection (for AMFI API access)

## 🚀 Installation

### 1. Clone and Setup

```bash
git clone <repository-url>
cd navtimeseries
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Database

Edit `app/config.py` and set your database URL:

```python
DB_URL = 'postgresql://username:password@host:port/database'
```

### 4. Prepare ISIN List

Create or edit `data/isin_master_list.csv` with your funds:

```csv
ISIN,Scheme Name,Scheme Code
INF174K01419,HDFC Balanced Advantage Fund,
INF090I01239,ICICI Prudential Equity & Debt Fund,
```
### 5. Generate Master List (Optional)
Instead of manually creating the ISIN list, you can generate it by filtering for specific fund houses:

```bash
# Generate list for "Quant" funds
python scripts/generate_master_list.py Quant

# Generate list for multiple fund houses
python scripts/generate_master_list.py Quant HDFC SBI

# Generate list for compound names (use quotes)
python scripts/generate_master_list.py "PARAG PARIKH" "Mirae Asset"

# Save to a custom file
python scripts/generate_master_list.py Quant -o data/my_list.csv
```

## 📖 Usage

### Initial Setup (One-Time)

Download historical NAV data and populate the database:

```bash
./scripts/historical_setup.sh
```

**What it does:**

- Downloads NAVAll.txt for ISIN mapping
- Downloads 10 years of NAV data (skips if CSV exists)
- Uploads all historical data to database

### Daily Updates (Automated)

Run daily to update latest NAV and returns:

```bash
./scripts/daily_sync.sh
```

**What it does:**

1. Downloads latest NAVAll.txt
2. Updates NAV data incrementally
3. Calculates returns for all periods
4. Syncs to database

### Manual Execution

If you prefer to run the Python modules directly:

**1. Run Pipeline (Download & Calculate):**

```bash
python -m app.main
```

**2. Sync to Database:**

```bash
python -m app.database.sync --daily
```

## 📁 Project Structure

```
navtimeseries/
├── app/                        # Main Application Package
│   ├── config.py               # Configuration
│   ├── main.py                 # Pipeline Entry Point
│   ├── services/               # Core Business Logic
│   │   ├── nav_manager.py      # NAV Download & Management
│   │   └── return_calculator.py# Returns Calculation
│   ├── database/               # Database Layer
│   │   ├── models.py           # SQLAlchemy Models
│   │   ├── setup.py            # DB Connection Setup
│   │   └── sync.py             # DB Sync Operations
│   └── utils/                  # Utilities
│       └── legacy.py           # Bulk Import Helpers
│
├── data/                       # Data Storage
│   ├── historical_nav/         # Raw NAV CSV files
│   ├── returns/                # Generated Return Reports
│   └── isin_master_list.csv    # Master List of Funds
│
├── scripts/                    # Automation Scripts
│   ├── daily_sync.sh           # Daily Cron Script
│   └── historical_setup.sh     # Initial Setup Script
│
├── logs/                       # Operation Logs
└── requirements.txt
```

## 🔧 Configuration (`app/config.py`)

```python
# Data Directories
NAV_DATA_DIR = "data"
HISTORICAL_NAV_DIR = "data/historical_nav"
OUTPUT_DIR = "data/returns"

# Database
DB_URL = 'postgresql://user:pass@host:port/database'
```

## 📊 Database Schema

**`mf_fund`** - Mutual fund metadata

- `isin` (PK) - ISIN code
- `scheme_name` - Fund name
- `amc_name` - AMC name

**`mf_nav_history`** - NAV time series

- `isin` (FK) - Links to mf_fund
- `date` - NAV date
- `nav` - NAV value

**`mf_returns`** - Calculated returns

- `isin` (FK) - Links to mf_fund
- `return_1m`, `return_1y`, `return_3y`, etc.
- `return_3y_carg`, `return_5y_carg`, etc.

## Data Flow

### Daily Update Mode (Hybrid Strategy)

```
NAVAll.txt → Parse → Check Gap
                         ↓
        Gap ≤ 4 days: Use NAVAll (fast)
        Gap > 4 days: Use AMFI API (fallback)
                         ↓
                   Update CSV → Calculate Returns → Sync to DB
```

## 🤝 Contributing

When adding new ISINs:

1. Add to `data/isin_master_list.csv`
2. Run `./scripts/historical_setup.sh`

## 📞 Support

For issues and questions:

- Check logs in `logs/` directory
- Verify configuration in `app/config.py`
