# Daily Portfolio Updates - Quick Guide

## How It Works

The portfolio time series **automatically updates** when you run the daily sync:

```bash
./daily_sync.sh
```

### What Happens Daily:

1. **NAV Sync** → Latest NAV added to `mf_nav_history` table
2. **Returns Calc** → Returns calculated with new NAV
3. **Portfolio Reports** → Time series regenerated for all clients

### No Separate Update Needed!

The time series reads directly from `mf_nav_history`, so:
- ✅ New NAV data → Time series automatically includes new date
- ✅ No manual update required
- ✅ Always shows latest data

## Daily Sync Process

```
6:00 PM Daily (Cron)
    ↓
Download NAVAll.txt
    ↓
Update mf_nav_history table (new date added)
    ↓
Generate portfolio reports
    ↓
Reports include new date automatically!
```

## Generated Reports

After daily sync, these files are updated in `reports/` directory:

```
reports/
├── timeseries_CLIENT001.csv    # Daily portfolio values (updated)
├── timeseries_CLIENT002.csv
├── monthly_CLIENT001.csv        # Monthly aggregates (updated)
├── monthly_CLIENT002.csv
├── holdings_CLIENT001.csv       # Current holdings snapshot
└── holdings_CLIENT002.csv
```

## Verify Daily Update

```bash
# Check latest report date
tail -1 reports/timeseries_CLIENT123.csv

# Should show today's date with latest portfolio value
```

## Manual Update (If Needed)

```bash
# Regenerate all portfolio reports
python3 portfolio_calculator.py

# Or for specific client
python3 portfolio_calculator.py CLIENT123
```

## Configure Daily Reports

### Option 1: All Clients (Default)

The updated `daily_sync.sh` automatically generates reports for all clients.

### Option 2: Specific Clients Only

Edit `daily_sync.sh` and modify the client list:

```bash
# Line ~50, change:
clients = ['CLIENT001', 'CLIENT002', 'CLIENT003']  # Add your clients
```

### Option 3: Disable Portfolio Reports

Comment out Step 3 in `daily_sync.sh`:

```bash
# Step 3: Generate portfolio reports (optional - uncomment if needed)
# Comment lines 42-87 if you don't need daily portfolio reports
```

## Email Reports (Optional)

Add email notification to `daily_sync.sh`:

```bash
# After portfolio reports generation
if [ -f "reports/timeseries_CLIENT123.csv" ]; then
    # Email latest report
    echo "Portfolio updated" | mail -s "Daily Portfolio Report" \
        -a "reports/timeseries_CLIENT123.csv" \
        client@email.com
fi
```

## API Access (Real-time)

For real-time access, use the Python API:

```python
from portfolio_calculator import PortfolioCalculator

calc = PortfolioCalculator()

# Always gets latest data from database
timeseries = calc.calculate_portfolio_timeseries('CLIENT123')

# Latest date automatically included
print(f"Latest date: {timeseries['date'].max()}")
print(f"Latest value: {timeseries['total_value'].iloc[-1]}")
```

## Monitoring

Check if daily updates are working:

```bash
# View latest sync log
tail -f logs/daily_sync_$(ls -t logs/daily_sync_*.log | head -1)

# Check portfolio reports timestamp
ls -lh reports/timeseries_*.csv

# Should match today's date if sync ran successfully
```

## Troubleshooting

**Reports not updating:**
- Check daily_sync.sh ran successfully: `crontab -l`
- Check logs: `tail logs/daily_sync_*.log`
- Run manually: `./daily_sync.sh`

**Missing dates in time series:**
- Weekends/holidays won't have NAV data
- This is normal - only trading days have NAV

**Old data in reports:**
- Verify cron job is running: `crontab -l`
- Check last sync time: `ls -l reports/`
- Run manual sync: `./daily_sync.sh`

## Summary

✅ **Automatic**: Time series updates when NAV data syncs  
✅ **Daily**: Run `./daily_sync.sh` via cron at 6 PM  
✅ **No extra work**: Reports regenerate automatically  
✅ **Always current**: Reads latest data from database  

**Just ensure daily_sync.sh runs and everything updates automatically!**
