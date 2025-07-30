#!/bin/bash
#
# Docker Entrypoint Script with Cron Support
# This script starts cron and then runs the main application
#

# Ensure the media directory has the correct permissions
if [ -d "/mnt/shared-project-data" ]; then
    echo "Updating permissions for /mnt/shared-project-data..."
    chown -R dockeruser:dockeruser /mnt/shared-project-data
fi

# Function to start cron if enabled
start_cron() {
    if [ "$ENABLE_CRON" = "true" ]; then
        echo "Setting up cron for thumbnail generation..."
        /usr/local/bin/setup_cron.sh
        echo "Cron setup completed."
    else
        echo "Cron disabled. Set ENABLE_CRON=true to enable automatic thumbnail generation."
    fi
}

# Function to handle shutdown gracefully
shutdown() {
    echo "Shutting down..."
    if [ "$ENABLE_CRON" = "true" ]; then
        service cron stop
    fi
    exit 0
}

# Set up signal handlers
trap shutdown SIGTERM SIGINT

# Start cron if enabled
start_cron

# Execute the main command as dockeruser
exec gosu dockeruser "$@"
