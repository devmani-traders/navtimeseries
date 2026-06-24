#!/bin/bash

# Daily NAV Pipeline Script
# This script:
# 1. Downloads NAVAll data
# 2. Updates NAV data incrementally
# 3. Calculates returns
# 4. Syncs to database

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Go up one level to project root
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Set up logging
LOG_DIR="$PROJECT_ROOT/logs"
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
# We need to set PYTHONPATH to include the current directory so python can find the 'app' module
export PYTHONPATH=$PROJECT_ROOT
/usr/local/bin/python -m app.main >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    handle_error "Main pipeline failed"
fi
log "Main pipeline completed successfully"

# Step 2: Sync to database (daily mode - NAV + returns from returns report)
log "Step 2: Syncing to database..."
/usr/local/bin/python -m app.database.sync --daily >> "$LOG_FILE" 2>&1
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
