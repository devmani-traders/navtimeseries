# NAV Pipeline Cron Job Setup

## Daily Sync Script
The `daily_sync.sh` script automates the daily workflow:
1. Downloads NAVAll data
2. Updates NAV data incrementally
3. Calculates returns
4. Syncs to database

## Setting up Cron Job

### Option 1: Using crontab (Recommended)

1. **Edit crontab:**
```bash
crontab -e
```

2. **Add the following line** (runs daily at 6:00 PM after market close):
```bash
0 18 * * * cd /Users/njp60/Documents/code/navtimeseries && ./daily_sync.sh
```

**Common Schedules:**
```bash
# Daily at 6:00 PM (after market close)
0 18 * * * cd /Users/njp60/Documents/code/navtimeseries && ./daily_sync.sh

# Daily at 8:00 PM
0 20 * * * cd /Users/njp60/Documents/code/navtimeseries && ./daily_sync.sh

# Monday to Friday at 6:30 PM (weekdays only)
30 18 * * 1-5 cd /Users/njp60/Documents/code/navtimeseries && ./daily_sync.sh
```

3. **Verify cron job:**
```bash
crontab -l
```

### Option 2: Using macOS launchd (Alternative for Mac)

1. **Create plist file:**
```bash
nano ~/Library/LaunchAgents/com.navpipeline.daily.plist
```

2. **Add configuration:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.navpipeline.daily</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/Users/njp60/Documents/code/navtimeseries/daily_sync.sh</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>18</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/Users/njp60/Documents/code/navtimeseries/logs/launchd.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/njp60/Documents/code/navtimeseries/logs/launchd.error.log</string>
    
    <key>WorkingDirectory</key>
    <string>/Users/njp60/Documents/code/navtimeseries</string>
</dict>
</plist>
```

3. **Load the job:**
```bash
launchctl load ~/Library/LaunchAgents/com.navpipeline.daily.plist
```

4. **Verify:**
```bash
launchctl list | grep navpipeline
```

5. **Unload if needed:**
```bash
launchctl unload ~/Library/LaunchAgents/com.navpipeline.daily.plist
```

## Manual Testing

Test the script manually before setting up cron:
```bash
cd /Users/njp60/Documents/code/navtimeseries
./daily_sync.sh
```

## Logs

Logs are saved to:
```
/Users/njp60/Documents/code/navtimeseries/logs/daily_sync_YYYYMMDD_HHMMSS.log
```

Old logs (>30 days) are automatically cleaned up.

## Monitoring

To check if the cron job is running:
```bash
# View recent logs
ls -lt logs/daily_sync_*.log | head -5

# View latest log
tail -f logs/daily_sync_$(ls -t logs/daily_sync_*.log | head -1)

# Check cron job status (on macOS)
log show --predicate 'eventMessage contains "cron"' --last 1h
```

## Troubleshooting

**Cron job not running:**
1. Check cron service is running: `sudo launchctl list | grep cron`
2. Check system logs: `grep cron /var/log/system.log`
3. Ensure script has execute permissions: `ls -l daily_sync.sh`

**Script fails:**
1. Check logs in `logs/` directory
2. Test manually: `./daily_sync.sh`
3. Verify Python paths and dependencies

**Database connection issues:**
1. Check database connectivity
2. Verify `SQL/setup_db.py` configuration
3. Check firewall/IP whitelist settings
