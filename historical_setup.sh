#!/bin/bash

# Historical NAV Data Setup Script
# This script:
# 1. Checks for existing NAV CSV files for each ISIN
# 2. Downloads historical data if CSV doesn't exist
# 3. Uploads all NAV data to database

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set up logging
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/historical_setup_$(date +%Y%m%d_%H%M%S).log"

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to handle errors
handle_error() {
    log "ERROR: $1"
    log "Historical setup failed. Check log: $LOG_FILE"
    exit 1
}

log "=========================================="
log "Starting Historical NAV Data Setup"
log "=========================================="

# Step 1: Download NAVAll for ISIN mapping
log "Step 1: Downloading NAVAll.txt for ISIN mapping..."
python3 -c "
from nav_manager import NavManager
manager = NavManager()
manager.download_nav_all()
manager.update_master_list_with_codes('navdata/isin_master_list.csv')
" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    handle_error "Failed to update ISIN mappings"
fi
log "ISIN mappings updated successfully"

# Step 2: Download missing NAV data or use existing
log "Step 2: Ensuring NAV data is available..."
python3 main.py navdata/isin_master_list.csv >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    handle_error "Failed to download/update NAV data"
fi
log "NAV data download/update completed successfully"

# Step 3: Upload to database
log "Step 3: Uploading historical NAV data to database..."
python3 sync_to_db.py --historical >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    handle_error "Failed to upload NAV data to database"
fi
log "Historical NAV data uploaded successfully"

log "=========================================="
log "Historical NAV Data Setup Completed"
log "Total ISINs processed: Check log for details"
log "Log saved to: $LOG_FILE"
log "=========================================="

exit 0
