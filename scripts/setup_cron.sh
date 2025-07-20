#!/bin/bash
#
# Cron Setup Script for Thumbnail Generation
# This script sets up cron jobs inside the Docker container
#

# Default thumbnail height (can be overridden by environment variable)
THUMBNAIL_HEIGHT=${THUMBNAIL_HEIGHT:-400}

# Create cron job for thumbnail generation
# Run every night at 2 AM
CRON_JOB="0 2 * * * /usr/local/bin/generate_thumbnails_cron.sh $THUMBNAIL_HEIGHT"

# Add the cron job to the dockeruser's crontab
echo "$CRON_JOB" | crontab -u dockeruser -

# Ensure cron service is running
service cron start

echo "Cron job installed for dockeruser:"
echo "  Schedule: Every night at 2 AM"
echo "  Command: /usr/local/bin/generate_thumbnails_cron.sh $THUMBNAIL_HEIGHT"
echo "  Thumbnail height: ${THUMBNAIL_HEIGHT}px"
echo ""
echo "Cron service started successfully."
echo ""
echo "To view current cron jobs: crontab -u dockeruser -l"
echo "To view cron logs: tail -f /var/log/find_artek/thumbnail-generation.log"
