#!/bin/bash
#
# Restart the Vestaboard display service if it isn't running.
# Intended to be run periodically (e.g. from cron).

# Name of the Python script (without the .py extension)
SCRIPT_NAME="vestaboard"

# Resolve the directory this script lives in so it works regardless of cwd
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if pgrep -f "$SCRIPT_NAME.py" > /dev/null
then
    echo "$SCRIPT_NAME is running"
else
    echo "$SCRIPT_NAME is not running, starting it"
    cd "$SCRIPT_DIR" || exit 1
    nohup python "$SCRIPT_DIR/$SCRIPT_NAME.py" >> "$SCRIPT_DIR/$SCRIPT_NAME.log" 2>&1 &
fi
