#!/bin/bash
#
# Thumbnail Generation Cron Script
# This script runs the Django management command to generate missing thumbnails
#
# Usage: 
#   generate_thumbnails_cron.sh [height]
#   height: Optional thumbnail height in pixels (default: 400)
#

# Get thumbnail height from command line argument, default to 400
THUMBNAIL_HEIGHT=${1:-400}

# Validate height parameter
if ! [[ "$THUMBNAIL_HEIGHT" =~ ^[0-9]+$ ]] || [ "$THUMBNAIL_HEIGHT" -lt 50 ] || [ "$THUMBNAIL_HEIGHT" -gt 2000 ]; then
    echo "Error: Height must be a number between 50 and 2000 pixels"
    exit 1
fi

# Set script directory and log file location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${DJANGO_PROJECT_DIR:-/app}"
LOG_FILE="/var/log/find_artek/thumbnail-generation.log"
LOG_DIR="$(dirname "$LOG_FILE")"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Change to project directory
cd "$PROJECT_DIR" || {
    log "ERROR: Could not change to project directory: $PROJECT_DIR"
    exit 1
}

log "Starting thumbnail generation with height: ${THUMBNAIL_HEIGHT}px..."

# Set up environment for Django
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Run the Django management command with specified height as dockeruser
su dockeruser -c "cd '$PROJECT_DIR' && python manage.py generate_thumbnails --verbose --height '$THUMBNAIL_HEIGHT'" 2>&1 | while IFS= read -r line; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $line" >> "$LOG_FILE"
done

# Check exit status
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    log "Thumbnail generation completed successfully"
    exit 0
else
    log "ERROR: Thumbnail generation failed with exit code ${PIPESTATUS[0]}"
    exit 1
fi
