#!/bin/bash
# Grabs the app window offscreen against a running OpenLinkHub, for checking pages
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Usage: tools/screenshot.sh <output.png> [device-serial]

cd "$(dirname "$0")/.." || exit 1
QT_QPA_PLATFORM=offscreen timeout 30 python3 -m openlinkhub_desktop \
  --screenshot "$1" ${2:+--page "$2"} 2>&1 | grep -v '^qt.qpa'
