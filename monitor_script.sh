#!/bin/bash
#
# Restart the Vestaboard display service if it isn't running, or if it's
# running but wedged. Intended to be run periodically (e.g. from cron).
#
# The service logs at least once an hour (every 20 min while updating, hourly
# during quiet hours), so a log that has stopped growing means it's stuck.

# Name of the Python script (without the .py extension)
SCRIPT_NAME="vestaboard"

# Resolve the directory this script lives in so it works regardless of cwd
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/$SCRIPT_NAME.log"

# Comfortably above the 1-hour quiet-hours sleep.
STALE_SECS=7200

# Match only the interpreter running this exact script, not test_vestaboard.py
# or an editor that has vestaboard.py open.
PATTERN="^python[0-9.]* (-u )?$SCRIPT_DIR/$SCRIPT_NAME\.py$"

file_mtime() {
    stat -c %Y "$1" 2>/dev/null || stat -f %m "$1"
}

PIDS=$(pgrep -f "$PATTERN")

if [ -n "$PIDS" ] && [ -f "$LOG_FILE" ]; then
    AGE=$(( $(date +%s) - $(file_mtime "$LOG_FILE") ))

    if [ "$AGE" -gt "$STALE_SECS" ]; then
        echo "$SCRIPT_NAME looks hung - log has not grown in ${AGE}s, restarting"
        kill -9 $PIDS
        for _ in $(seq 1 10); do
            pgrep -f "$PATTERN" > /dev/null || break
            sleep 1
        done
        PIDS=""
    fi
fi

if [ -n "$PIDS" ]; then
    echo "$SCRIPT_NAME is running"
else
    echo "$SCRIPT_NAME is not running, starting it"
    cd "$SCRIPT_DIR" || exit 1
    nohup python -u "$SCRIPT_DIR/$SCRIPT_NAME.py" >> "$LOG_FILE" 2>&1 &
fi
