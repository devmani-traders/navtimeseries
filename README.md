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

Edit `config.py` and set your database URL:

```python
DB_URL = 'postgresql://username:password@host:port/database'
```

### 4. Prepare ISIN List

Create or edit `navdata/isin_master_list.csv` with your funds:

```csv
ISIN,Scheme Name,Scheme Code
INF174K01419,HDFC Balanced Advantage Fund,
INF090I01239,ICICI Prudential Equity & Debt Fund,
```

## 📖 Usage

### Initial Setup (One-Time)

Download historical NAV data and populate the database:

```bash
./historical_setup.sh
```

**What it does:**
- Downloads NAVAll.txt for ISIN mapping
- Downloads 10 years of NAV data (skips if CSV exists)
- Uploads all historical data to database

### Daily Updates (Automated)

Run daily to update latest NAV and returns:

```bash
./daily_sync.sh
```

**What it does:**
1. Downloads latest NAVAll.txt
2. Updates NAV data incrementally
3. Calculates returns for all periods
4. Syncs to database

### Set Up Cron Job

For automated daily updates at 6:00 PM:

```bash
crontab -e
```

Add this line:
```bash
0 18 * * * cd /Users/njp60/Documents/code/navtimeseries && ./daily_sync.sh
```

See [CRON_SETUP.md](CRON_SETUP.md) for detailed instructions.

## 📁 Project Structure

```
navtimeseries/
├── config.py                   # Configuration (paths, URLs, DB)
├── main.py                     # Main pipeline orchestrator
├── nav_manager.py              # NAV data download & management
├── return_calculator.py        # Returns calculation logic
├── sync_to_db.py              # Database sync operations
├── legacy_funcations.py       # Bulk import utilities
│
├── daily_sync.sh              # Daily automation script
├── historical_setup.sh        # Initial setup script
│
├── SQL/
│   ├── setup_db.py            # Database setup & connection
│   └── models.py              # SQLAlchemy models (user-managed)
│
├── navdata/
│   ├── historical_nav/        # NAV CSV files (scheme_code.csv)
│   ├── returns/               # Returns reports
│   ├── isin_master_list.csv   # ISINs to track
│   └── NAVAll.txt            # Latest AMFI data
│
└── logs/                      # Operation logs
```

## 🔧 Configuration (`config.py`)

```python
# Data Directories
NAV_DATA_DIR = "navdata"
HISTORICAL_NAV_DIR = "navdata/historical_nav"
OUTPUT_DIR = "navdata/returns"

# Files
ISIN_MASTER_LIST = "navdata/isin_master_list.csv"
NAV_RETURNS_REPORT = "navdata/returns/nav_returns_report.csv"

# API URLs
AMFI_NAV_ALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
AMFI_NAV_HISTORY_URL = "https://www.amfiindia.com/api/nav-history"

# Settings
YEARS_BACK = 10  # Years of historical data to download

# Database
DB_URL = 'postgresql://user:pass@host:port/database'
```

## 📊 Database Schema

### Key Tables (in `SQL/models.py`)

**`mf_fund`** - Mutual fund metadata
- `isin` (PK) - ISIN code
- `scheme_name` - Fund name
- `amc_name` - AMC name
- `fund_type` - Fund category

**`mf_nav_history`** - NAV time series
- `isin` (FK) - Links to mf_fund
- `date` - NAV date
- `nav` - NAV value
- Unique constraint on (isin, date)

**`mf_returns`** - Calculated returns
- `isin` (FK) - Links to mf_fund
- `return_1m`, `return_3m`, `return_6m`, `return_ytd`
- `return_1y`, `return_3y`, `return_5y`
- `return_3y_carg`, `return_5y_carg`, `return_10y_carg`
- `return_since_inception`, `return_since_inception_carg`

## 🛠️ Scripts Overview

### Daily Operations

**`daily_sync.sh`**
- **Purpose**: Daily automated updates
- **Frequency**: Daily (via cron at 6:00 PM)
- **What it does**:
  1. Downloads NAVAll.txt
  2. Updates NAV data incrementally
  3. Calculates returns
  4. Syncs to database (daily mode)
- **Usage**: `./daily_sync.sh`

### Initial Setup

**`historical_setup.sh`**
- **Purpose**: Initial data load or adding new ISINs
- **Frequency**: One-time or as needed
- **What it does**:
  1. Maps ISINs to Scheme Codes
  2. Downloads historical data (10 years)
  3. Uploads to database (historical mode)
- **Usage**: `./historical_setup.sh`

### Python Scripts

**`main.py`** - Pipeline orchestrator
```bash
python3 main.py navdata/isin_master_list.csv
```

**`sync_to_db.py`** - Database sync
```bash
python3 sync_to_db.py --daily       # Sync latest NAV + returns
python3 sync_to_db.py --historical  # Sync all historical NAV
```

## 📈 Returns Calculation

Calculates returns for the following periods:

| Period | Absolute Return | CAGR |
|--------|----------------|------|
| 1 Day | ✅ | - |
| 1 Month | ✅ | - |
| 3 Months | ✅ | - |
| 6 Months | ✅ | - |
| YTD | ✅ | - |
| 1 Year | ✅ | ✅ |
| 2 Years | ✅ | ✅ |
| 3 Years | ✅ | ✅ |
| 5 Years | ✅ | ✅ |
| 10 Years | ✅ | ✅ |
| Inception | ✅ | ✅ |

## 🔄 Data Flow

### Daily Update Mode (Hybrid Strategy)

```
NAVAll.txt → Parse → Check Gap
                         ↓
        Gap ≤ 4 days: Use NAVAll (fast)
        Gap > 4 days: Use AMFI API (fallback)
                         ↓
                   Update CSV → Calculate Returns → Sync to DB
```

### Historical Mode

```
ISIN List → Check CSV Exists?
                ↓              ↓
              YES             NO
                ↓              ↓
           Skip Download   Download API
                ↓              ↓
                └──→ Combine ←─┘
                        ↓
                  Upload to DB
```

## 🐛 Troubleshooting

### Database Connection Issues

**Error**: `Cannot connect to database`

**Solution**:
1. Check `config.py` DB_URL is correct
2. Verify database is running
3. Check IP whitelist/firewall settings
4. Test connection: `psql -h host -U user -d database`

### NAV Download Failures

**Error**: `API returned 400/500`

**Solution**:
1. Check AMFI API availability
2. Verify date ranges (must be < 5 years per API call)
3. Check internet connectivity
4. Review logs in `logs/` directory

### Missing Data for ISINs

**Issue**: Some ISINs have no data

**Causes**:
- ISIN is invalid or not found in NAVAll.txt
- Scheme is very new (< 10 years history)
- AMFI API doesn't have data for this scheme

**Solution**:
1. Verify ISIN in NAVAll.txt manually
2. Check scheme_code mapping in `isin_master_list.csv`
3. Review logs for specific errors

### Cron Job Not Running

**Issue**: Daily sync not executing

**Solution**:
1. Check cron service: `sudo launchctl list | grep cron`
2. Verify crontab entry: `crontab -l`
3. Check script permissions: `ls -l daily_sync.sh`
4. Review system logs: `grep cron /var/log/system.log`

## 📝 Logs

All operations are logged to the `logs/` directory:

```
logs/
├── daily_sync_20251120_180000.log      # Daily sync logs
├── historical_setup_20251115_100000.log # Historical setup logs
└── pipeline.log                         # General pipeline logs
```

Logs older than 30 days are automatically cleaned up.

## 🤝 Contributing

When adding new ISINs:

1. Add to `navdata/isin_master_list.csv`
2. Run `./historical_setup.sh`
3. Verify data in database

When modifying database schema:

- Edit `SQL/models.py` (user-managed)
- Do NOT modify other files under `SQL/`

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- AMFI India for providing NAV data APIs
- Data sources: https://www.amfiindia.com

## 📞 Support

For issues and questions:
- Check logs in `logs/` directory
- Review documentation in `CRON_SETUP.md` and `HISTORICAL_SETUP.md`
- Verify configuration in `config.py`

---

**Last Updated**: 2025-11-20
