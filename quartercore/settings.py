# User settings and autostart
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Settings live in ~/.config/Quartercore/Quartercore.conf (QSettings).
# Autostart is a desktop entry in ~/.config/autostart, the XDG standard that
# KDE Plasma, GNOME and others read at login.

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QSettings, Signal

from .api import DEFAULT_URL

AUTOSTART_NAME = "quartercore.desktop"


def config_home():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def autostart_file():
    return config_home() / "autostart" / AUTOSTART_NAME


def launch_command():
    """The command that starts this installation of Quartercore."""
    installed = shutil.which("quartercore") or str(Path.home() / ".local/bin/quartercore")
    if os.access(installed, os.X_OK):
        return installed
    package_parent = Path(__file__).resolve().parent.parent
    return "sh -c 'cd \"%s\" && exec \"%s\" -m quartercore \"$@\"' quartercore" % (package_parent, sys.executable)


class Settings(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = QSettings("Quartercore", "Quartercore")

    def _get(self, key, default, kind=str):
        value = self.store.value(key, default)
        if kind is bool:
            return value in (True, "true", "1", 1)
        return kind(value)

    def _set(self, key, value):
        if self.store.contains(key) and self._get(key, value, type(value)) == value:
            return
        self.store.setValue(key, value)
        self.store.sync()
        self.changed.emit()

    @Property(str, notify=changed)
    def serverUrl(self):
        return self._get("serverUrl", DEFAULT_URL)

    @serverUrl.setter
    def serverUrl(self, value):
        self._set("serverUrl", value.strip().rstrip("/") or DEFAULT_URL)

    # "system" follows the desktop language
    @Property(str, notify=changed)
    def language(self):
        return self._get("language", "system")

    @language.setter
    def language(self, value):
        self._set("language", value)

    @Property(bool, notify=changed)
    def closeToTray(self):
        return self._get("closeToTray", True, bool)

    @closeToTray.setter
    def closeToTray(self, value):
        self._set("closeToTray", bool(value))

    @Property(bool, notify=changed)
    def startMinimized(self):
        """Autostart opens only the tray icon, not the window."""
        return self._get("startMinimized", True, bool)

    @startMinimized.setter
    def startMinimized(self, value):
        self._set("startMinimized", bool(value))
        if self.autostart:
            self._write_autostart()

    @Property(bool, notify=changed)
    def autostart(self):
        return autostart_file().exists()

    @autostart.setter
    def autostart(self, value):
        if value:
            self._write_autostart()
        else:
            autostart_file().unlink(missing_ok=True)
        self.changed.emit()

    def _write_autostart(self):
        path = autostart_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        args = " --minimized" if self.startMinimized else ""
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Quartercore\n"
            "Comment=Control your Corsair devices on Linux through OpenLinkHub\n"
            "Exec=%s%s\n"
            "Icon=quartercore\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n" % (launch_command(), args))
