#!/bin/bash
set -e

# Function to setup environment (if needed)
setup_env() {
    echo "Starting container..."
    # Ensure log directory exists
    mkdir -p logs
}

setup_env

case "$1" in
    "setup")
        echo "Running Historical Setup..."
        ./scripts/historical_setup.sh
        ;;
    "cron")
        echo "Starting Cron Daemon for Daily Sync..."
        # Dump env vars to a file so cron can see them
        printenv | grep -v "no_proxy" >> /etc/environment
        
        # Ensure log file exists
        touch /var/log/cron.log
        
        # Start cron in foreground
        cron -f
        ;;
    "refresh-master")
        echo "Refreshing ISIN Master List from Database..."
        # This writes directly to GCS if USE_GCS=true (via storage abstraction)
        python3 scripts/populate_master_from_db.py
        ;;
    *)
        # Run arbitrary commands (e.g., bash)
        exec "$@"
        ;;
esac
