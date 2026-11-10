#!/bin/bash
# Installs Quartercore for the current user (no root needed)
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Usage: ./install.sh            install or update
#        ./install.sh --remove   uninstall

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/quartercore"
BIN="$HOME/.local/bin/quartercore"
DESKTOP="$HOME/.local/share/applications/quartercore.desktop"
ICON="$HOME/.local/share/icons/hicolor/scalable/apps/quartercore.svg"
CORE_BIN="$HOME/.local/bin/quartercore-core"
CORE_UNIT="$HOME/.config/systemd/user/quartercore-core.service"

if [ "$1" = "--remove" ]; then
  systemctl --user disable --now quartercore-core 2>/dev/null || true
  rm -rf "$APP"
  rm -f "$BIN" "$DESKTOP" "$ICON" "$CORE_BIN" "$CORE_UNIT"
  echo "Quartercore removed."
  exit 0
fi

python3 -c 'import PySide6.QtQuick' 2>/dev/null || {
  echo "PySide6 (Qt for Python) is missing. Fedora: sudo dnf install python3-pyside6" >&2
  exit 1
}

rm -rf "$APP"
mkdir -p "$APP" "$(dirname "$BIN")" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
cp -r "$DIR/quartercore" "$APP/"
find "$APP" -name __pycache__ -prune -exec rm -rf {} +

cat > "$BIN" <<EOF
#!/bin/sh
cd "$APP" && exec python3 -m quartercore "\$@"
EOF
chmod 755 "$BIN"

install -m 644 "$DIR/quartercore/icon.svg" "$ICON"
install -m 644 "$DIR/data/quartercore.desktop" "$DESKTOP"
sed -i "s|^Exec=.*|Exec=$BIN|" "$DESKTOP"
update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true

# The core service (roadmap part 2); it only runs once you enable it
cat > "$CORE_BIN" <<EOF
#!/bin/sh
cd "$APP" && exec python3 -m quartercore.core "\$@"
EOF
chmod 755 "$CORE_BIN"
mkdir -p "$(dirname "$CORE_UNIT")"
install -m 644 "$DIR/data/systemd/quartercore-core.service" "$CORE_UNIT"
systemctl --user daemon-reload 2>/dev/null || true
if systemctl --user is-active --quiet quartercore-core 2>/dev/null; then
  systemctl --user restart quartercore-core
fi

echo "Installed. Start it from the menu (Quartercore) or with: $BIN"
