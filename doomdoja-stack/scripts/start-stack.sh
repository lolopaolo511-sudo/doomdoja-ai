#!/bin/bash
# Start Colima + doomdoja-stack containers.
# Called by launchd at login.

set -euo pipefail

LOG="$HOME/doomdoja-stack/logs/autostart.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] autostart triggered" >> "$LOG"

# Wait for network to be available (up to 30s)
for i in $(seq 1 15); do
    if /sbin/ping -c1 -W1 1.1.1.1 >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

# Start Colima if not running
if ! /opt/homebrew/bin/colima status 2>/dev/null | grep -q "Running"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] starting colima..." >> "$LOG"
    /opt/homebrew/bin/colima start --cpu 4 --memory 7 --disk 60 >> "$LOG" 2>&1
    sleep 5
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] colima already running" >> "$LOG"
fi

# Start stack
echo "[$(date '+%Y-%m-%d %H:%M:%S')] starting docker compose stack..." >> "$LOG"
cd "$HOME/doomdoja-stack"
/opt/homebrew/bin/docker compose up -d >> "$LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] done" >> "$LOG"
