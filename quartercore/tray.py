# Tray icon: temperatures at a glance and quick actions
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# On KDE Plasma this shows up in the system tray (StatusNotifierItem).
# Left click shows or hides the window.

from PySide6.QtCore import QCoreApplication, QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def tr(text):
    return QCoreApplication.translate("Tray", text)


class Tray(QObject):
    def __init__(self, backend, icon, show_window, quit_app, parent=None, settings=None):
        super().__init__(parent)
        self.backend = backend
        self.settings = settings
        self.show_window = show_window
        self.icon = QSystemTrayIcon(QIcon(icon), self)
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.build_menu)
        self.quit_app = quit_app
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self.on_activated)
        backend.systemChanged.connect(self.update_tooltip)
        backend.connectedChanged.connect(self.update_tooltip)
        self.build_menu()
        self.update_tooltip()

    def show(self):
        self.icon.show()

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window(toggle=True)

    def temperatures(self):
        system = self.backend.system or {}
        parts = []
        if system.get("cpuTemp"):
            parts.append(tr("CPU") + " " + system["cpuTemp"])
        if system.get("gpuTemp"):
            parts.append(tr("GPU") + " " + system["gpuTemp"])
        return "  ·  ".join(parts)

    def update_tooltip(self):
        status = self.temperatures() if self.backend.connected else tr("Not connected to OpenLinkHub")
        self.icon.setToolTip("Quartercore\n" + status)

    def build_menu(self):
        """Rebuilt each time it opens, so temperatures, devices and the language are current."""
        menu = self.menu
        menu.clear()
        menu.addAction(QIcon.fromTheme("window"), tr("Open Quartercore"), lambda: self.show_window())

        info = menu.addAction(self.temperatures() if self.backend.connected
                              else tr("Not connected to OpenLinkHub"))
        info.setEnabled(False)
        menu.addSeparator()

        for hub in self.backend.hubs:
            sub = menu.addMenu(QIcon.fromTheme("preferences-system"), hub["product"])
            sub.addSection(tr("Speed profile for all fans and pump"))
            for profile in self.backend.speedProfiles:
                action = QAction(profile, sub)
                action.triggered.connect(lambda _=False, s=hub["serial"], p=profile:
                                         self.backend.setHubSpeedProfile(s, p))
                sub.addAction(action)
            sub.addSeparator()
            sub.addAction(tr("Open page"), lambda s=hub["serial"]: self.open_device(s))

        if self.settings is not None:
            kiosk = menu.addAction(QIcon.fromTheme("video-display"), tr("Kiosk on the XENEON EDGE"))
            kiosk.setCheckable(True)
            kiosk.setChecked(self.settings.edgeKiosk)
            kiosk.toggled.connect(lambda on: setattr(self.settings, "edgeKiosk", on))
        menu.addAction(QIcon.fromTheme("video-display"), tr("XENEON EDGE layout"), self.backend.openXeneonEditor)
        menu.addAction(QIcon.fromTheme("internet-web-browser"), tr("OpenLinkHub web interface"),
                       lambda: self.backend.openInBrowser(""))
        menu.addSeparator()
        menu.addAction(QIcon.fromTheme("application-exit"), tr("Quit"), self.quit_app)

    def open_device(self, serial):
        self.backend.selectDevice(serial)
        self.show_window()
