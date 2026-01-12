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
    *)
        # Run arbitrary commands (e.g., bash)
        exec "$@"
        ;;
esac
