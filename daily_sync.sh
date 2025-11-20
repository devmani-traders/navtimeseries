#!/bin/bash

# Daily NAV Pipeline Script
# This script:
# 1. Downloads NAVAll data
# 2. Updates NAV data incrementally
# 3. Calculates returns
# 4. Syncs to database

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set up logging
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_sync_$(date +%Y%m%d_%H%M%S).log"

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to handle errors
handle_error() {
    log "ERROR: $1"
    log "Daily sync failed. Check log: $LOG_FILE"
    exit 1
}

log "=========================================="
log "Starting Daily NAV Pipeline"
log "=========================================="

# Step 1: Run main pipeline (downloads NAVAll, updates NAV, calculates returns)
log "Step 1: Running main pipeline..."
python3 main.py navdata/isin_master_list.csv >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    handle_error "Main pipeline failed"
fi
log "Main pipeline completed successfully"

# Step 2: Sync to database (daily mode - NAV + returns from returns report)
log "Step 2: Syncing to database..."
python3 sync_to_db.py --daily >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    handle_error "Database sync failed"
fi
log "Database sync completed successfully"

log "=========================================="
log "Daily NAV Pipeline completed successfully"
log "Log saved to: $LOG_FILE"
log "=========================================="

# Clean up old logs (keep last 30 days)
find "$LOG_DIR" -name "daily_sync_*.log" -mtime +30 -delete

exit 0
