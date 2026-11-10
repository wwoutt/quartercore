#!/bin/bash
# Installs OpenLinkHub Desktop for the current user (no root needed)
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Usage: ./install.sh            install or update
#        ./install.sh --remove   uninstall

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/openlinkhub-desktop"
BIN="$HOME/.local/bin/openlinkhub-desktop"
DESKTOP="$HOME/.local/share/applications/openlinkhub-desktop.desktop"
ICON="$HOME/.local/share/icons/hicolor/scalable/apps/openlinkhub-desktop.svg"

if [ "$1" = "--remove" ]; then
  rm -rf "$APP"
  rm -f "$BIN" "$DESKTOP" "$ICON"
  echo "OpenLinkHub Desktop removed."
  exit 0
fi

python3 -c 'import PySide6.QtQuick' 2>/dev/null || {
  echo "PySide6 (Qt for Python) is missing. Fedora: sudo dnf install python3-pyside6" >&2
  exit 1
}

rm -rf "$APP"
mkdir -p "$APP" "$(dirname "$BIN")" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
cp -r "$DIR/openlinkhub_desktop" "$APP/"
find "$APP" -name __pycache__ -prune -exec rm -rf {} +

cat > "$BIN" <<EOF
#!/bin/sh
cd "$APP" && exec python3 -m openlinkhub_desktop "\$@"
EOF
chmod 755 "$BIN"

install -m 644 "$DIR/openlinkhub_desktop/icon.svg" "$ICON"
install -m 644 "$DIR/data/openlinkhub-desktop.desktop" "$DESKTOP"
sed -i "s|^Exec=.*|Exec=$BIN|" "$DESKTOP"
update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true

echo "Installed. Start it from the menu (OpenLinkHub Desktop) or with: $BIN"
