#!/bin/bash
#
# Generates missing report thumbnails (management command generate_thumbnails).
#
# Run by cron as dockeruser (/etc/cron.d/find_artek_thumbnails, 02:00 daily when
# ENABLE_CRON=true), or by hand:
#   docker exec webapp-find-artek generate_thumbnails_cron.sh [height]
#
# height: thumbnail height in pixels (50-2000); default $THUMBNAIL_HEIGHT, else 400.
#
# Output goes to stdout/stderr, each line prefixed with a timestamp and "[thumbnails]". The
# cron line sends it to PID 1's stdout/stderr, i.e. to `docker logs`. There is no log file.
#
# Environment: cron gives its jobs an almost empty environment. Every process docker starts
# (docker run / docker exec) gets the image's ENV, including DJANGO_PROJECT_DIR; a cron job
# doesn't. If DJANGO_PROJECT_DIR is missing, the script loads the container's environment from
# /proc/1/environ (PID 1 runs as dockeruser, the file is readable only by that user and root).
# That file is NUL-separated, so values with spaces, quotes, '$' or newlines arrive unchanged,
# and no copy of the secrets is written anywhere. Nothing from it is printed.

set -u

log() {
    printf '%s [thumbnails] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

if [ "$(id -u)" -eq 0 ]; then
    log "ERROR: run this as dockeruser, not root (thumbnails on the share must belong to uid 30000)"
    exit 1
fi

# One run at a time: the first run after cron was enabled may work through a large backlog
# and last longer than a day. The lock is released when this process exits.
exec 9>/tmp/find_artek_thumbnails.lock
if ! flock -n 9; then
    log "another thumbnail run is still active, skipping this one"
    exit 0
fi

if [ -z "${DJANGO_PROJECT_DIR:-}" ]; then
    if [ ! -r /proc/1/environ ]; then
        log "ERROR: no container environment: /proc/1/environ is not readable by $(id -un)"
        exit 1
    fi
    while IFS= read -r -d '' kv; do
        name=${kv%%=*}
        case $name in
            # not a valid name, or bash-internal/read-only variables
            ''|[0-9]*|*[!A-Za-z0-9_]*|BASH|BASH_*|BASHOPTS|SHELLOPTS|UID|EUID|PPID) continue ;;
        esac
        export "$kv"
    done < /proc/1/environ
fi

PROJECT_DIR="${DJANGO_PROJECT_DIR:-/app}"
THUMBNAIL_HEIGHT="${1:-${THUMBNAIL_HEIGHT:-400}}"

if ! [[ "$THUMBNAIL_HEIGHT" =~ ^[0-9]+$ ]] || [ "$THUMBNAIL_HEIGHT" -lt 50 ] || [ "$THUMBNAIL_HEIGHT" -gt 2000 ]; then
    log "ERROR: height must be a number between 50 and 2000 pixels"
    exit 1
fi

cd "$PROJECT_DIR" || {
    log "ERROR: could not change to project directory: $PROJECT_DIR"
    exit 1
}

log "Starting thumbnail generation with height ${THUMBNAIL_HEIGHT}px"

python manage.py generate_thumbnails --verbose --height "$THUMBNAIL_HEIGHT" 2>&1 | while IFS= read -r line || [ -n "$line" ]; do
    log "$line"
done
rc=${PIPESTATUS[0]}

if [ "$rc" -eq 0 ]; then
    log "Thumbnail generation completed successfully"
else
    log "ERROR: thumbnail generation failed with exit code $rc"
fi
exit "$rc"
