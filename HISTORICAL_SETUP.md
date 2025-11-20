# Historical NAV Data Setup

## Overview
The `historical_setup.sh` script handles initial setup and bulk updates of historical NAV data.

## What It Does

1. **Downloads NAVAll.txt** - Gets latest ISIN to Scheme Code mapping
2. **Smart NAV Data Handling**:
   - For each ISIN in `isin_master_list.csv`:
     - If CSV exists in `navdata/historical_nav/` → Skip download, reuse existing file
     - If CSV missing → Download 10 years of historical data from AMFI API
3. **Uploads to Database** - Bulk uploads all NAV data to `mf_nav_history` table

## Usage

### Initial Setup (First Time)
```bash
./historical_setup.sh
```

### Adding New ISINs
1. Add new ISINs to `navdata/isin_master_list.csv`
2. Run the script:
```bash
./historical_setup.sh
```

The script will:
- Download data only for new ISINs (existing CSVs are reused)
- Upload all data (including new ISINs) to database

### Force Re-download All Data
If you want to refresh all data from scratch:
```bash
# Remove existing CSV files
rm navdata/historical_nav/*.csv

# Run setup
./historical_setup.sh
```

## Logs

Logs are saved to:
```
logs/historical_setup_YYYYMMDD_HHMMSS.log
```

## Monitoring Progress

```bash
# Watch the log in real-time
tail -f logs/historical_setup_$(ls -t logs/historical_setup_*.log | head -1)

# Check how many CSV files were created
ls -l navdata/historical_nav/*.csv | wc -l
```

## Performance

**Estimated Time:**
- **With existing CSVs**: 5-10 minutes (just uploads)
- **Fresh download**: 30-60 minutes for 100 ISINs (API rate limits apply)

**Optimization Tips:**
- Keep existing CSV files for faster re-runs
- Only add new ISINs to master list when needed
- AMFI API has rate limits, so downloads are throttled

## Troubleshooting

**Script fails during download:**
- Check internet connectivity
- Verify ISINs in master list are valid
- Check AMFI API availability
- Review log file for specific errors

**Database upload fails:**
- Verify database connection in `SQL/setup_db.py`
- Check IP whitelist/firewall settings
- Ensure sufficient database storage

**Missing data for some ISINs:**
- Some funds may not have 10 years of history
- AMFI API may not have data for very new funds
- Check log for specific ISIN errors

## Example Workflow

### Scenario 1: Initial Database Setup
```bash
# Step 1: Prepare ISIN list
# Edit navdata/isin_master_list.csv with your ISINs

# Step 2: Run historical setup
./historical_setup.sh

# Step 3: Verify database
python3 -c "
from SQL.setup_db import create_app, db
from SQL.models import NavHistory
app = create_app()
with app.app_context():
    count = NavHistory.query.count()
    print(f'Total NAV records: {count}')
"
```

### Scenario 2: Adding 50 New ISINs
```bash
# Step 1: Add 50 new ISINs to isin_master_list.csv

# Step 2: Run setup (downloads only for new ISINs)
./historical_setup.sh

# Step 3: Existing ISINs are skipped, only new ones downloaded
# All data (old + new) uploaded to database
```

### Scenario 3: Refresh All Data
```bash
# Clear existing CSVs
rm navdata/historical_nav/*.csv

# Download fresh data for all ISINs
./historical_setup.sh
```

## When to Use This vs Daily Sync

**Use `historical_setup.sh` when:**
- First-time database setup
- Adding new ISINs to track
- Need to refresh historical data

**Use `daily_sync.sh` for:**
- Daily updates (automated via cron)
- Incremental NAV updates
- Regular returns calculation

## Directory Structure After Setup

```
navtimeseries/
├── navdata/
│   ├── historical_nav/
│   │   ├── 123456.csv    # Downloaded or existing
│   │   ├── 789012.csv
│   │   └── ...
│   ├── returns/
│   │   └── nav_returns_report.csv
│   └── isin_master_list.csv
└── logs/
    └── historical_setup_*.log
```
