#!/bin/bash
# Checks the tray icon and the single instance in the real desktop session
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Usage: tools/tray-check.sh   (starts Quartercore minimized, checks, then stops it)

cd "$(dirname "$0")/.." || exit 1
python3 -m quartercore --minimized >/tmp/quartercore-check.log 2>&1 &
pid=$!
sleep 4

items="$(busctl --user get-property org.kde.StatusNotifierWatcher /StatusNotifierWatcher \
  org.kde.StatusNotifierWatcher RegisteredStatusNotifierItems 2>/dev/null)"
ours=no
for name in $(echo "$items" | grep -o '":[0-9.]*/[^"]*"' | tr -d '"' | cut -d/ -f1); do
  p="$(busctl --user status --no-pager "$name" 2>/dev/null | sed -n 's/^PID=//p')"
  [ "$p" = "$pid" ] && ours=yes
done
echo "tray icon registered: $ours"

start=$(date +%s%N)
timeout 10 python3 -m quartercore >/dev/null 2>&1
code=$?
echo "second start exits: code $code after $(( ($(date +%s%N) - start) / 1000000 )) ms"
kill -0 "$pid" 2>/dev/null && echo "first instance still running: yes"

kill "$pid"
wait "$pid" 2>/dev/null
grep -v '^qt.qpa' /tmp/quartercore-check.log
