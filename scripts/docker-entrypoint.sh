#!/bin/bash
#
# Entrypoint of the find_artek image (runs as dockeruser).
#
# ENABLE_CRON=true: start the cron daemon through sudo (as monitoring_db does). The daemon runs
# as root and runs the jobs in /etc/cron.d as dockeruser; the only job is the nightly thumbnail
# generation (/etc/cron.d/find_artek_thumbnails, 02:00). Unset or anything else: no cron.
#
# Then run the container's command ("$@", gunicorn by default) as PID 1, unchanged.

ts() { date '+%Y-%m-%d %H:%M:%S'; }

if [ "${ENABLE_CRON:-false}" = "true" ]; then
    # sudo resets the environment, so the cron daemon carries none of the container's secrets.
    if sudo -n /usr/sbin/service cron start >/dev/null 2>&1; then
        echo "$(ts) - Cron enabled: cron daemon started; thumbnails are generated daily at 02:00 (/etc/cron.d/find_artek_thumbnails), output in this log."
    else
        # The web app still starts: thumbnails are not worth an outage. The cron post-check
        # (cron process running) catches this.
        echo "$(ts) - ERROR: ENABLE_CRON=true, but the cron daemon could not be started." >&2
    fi
else
    echo "$(ts) - Cron disabled. Set ENABLE_CRON=true to enable automatic thumbnail generation."
fi

exec "$@"
