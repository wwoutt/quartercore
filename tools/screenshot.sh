#!/bin/bash
# Grabs the app window offscreen, for checking pages
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Usage: tools/screenshot.sh <output.png> [device-serial[:tab[:key id]]|settings|edge|kiosk|profiles[:name]|lighting[:effect]] [--fake]
#   keyboard tabs: colours, keys, macros, settings (e.g. KB1:keys:10)
#   --fake  uses tests/fake_openlinkhub.py instead of the real OpenLinkHub

cd "$(dirname "$0")/.." || exit 1
url=()
if [ "$3" = "--fake" ]; then
  python3 tests/fake_openlinkhub.py 27099 >/dev/null &
  fake=$!
  sleep 1
  url=(--url http://127.0.0.1:27099)
  export QUARTERCORE_WEATHER_URL=http://127.0.0.1:27099/weather
  export QUARTERCORE_GEOCODING_URL=http://127.0.0.1:27099/geocoding
  # Never write the fake layout or settings into the real ~/.config
  export XDG_CONFIG_HOME="$(mktemp -d)"
  mkdir -p "$XDG_CONFIG_HOME/Quartercore"
  cp ~/.config/Quartercore/Quartercore.conf "$XDG_CONFIG_HOME/Quartercore/" 2>/dev/null
fi
QT_QPA_PLATFORM=offscreen timeout 30 python3 -m quartercore "${url[@]}" \
  --screenshot "$1" ${2:+--page "$2"} 2>&1 | grep -v -e '^qt.qpa' -e 'does not support raise'
[ -n "$fake" ] && kill "$fake"
exit 0
