# Starts Quartercore
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Usage: python3 -m quartercore [--url http://127.0.0.1:27003] [--minimized]
#        [--screenshot file.png [--page serial|settings|profiles[:name]|lighting[:effect]]]   (grab the window and exit, for tests)

import argparse
import getpass
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from . import __version__, i18n
from .backend import Backend
from .edge import Edge, find_edge_screen
from .edgeeditor import EdgeEditor
from .headset import Headset
from .keyboard import Keyboard
from .lighting import Lighting
from .profiles import Profiles
from .settings import Settings
from .tray import Tray

HERE = Path(__file__).resolve().parent
INSTANCE = "quartercore-" + getpass.getuser()


def already_running():
    """Asks a running Quartercore to show its window; True when there is one."""
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE)
    if not socket.waitForConnected(300):
        return False
    socket.write(b"show\n")
    socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


def main():
    parser = argparse.ArgumentParser(prog="quartercore")
    parser.add_argument("--url", help="OpenLinkHub address, overrides the setting")
    parser.add_argument("--minimized", action="store_true", help="start with only the tray icon")
    parser.add_argument("--screenshot", help=argparse.SUPPRESS)
    parser.add_argument("--page", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # The KDE style when it is installed (Plasma), otherwise Fusion
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        QQuickStyle.setStyle("org.kde.desktop")
        QQuickStyle.setFallbackStyle("Fusion")

    app = QApplication(sys.argv)
    app.setApplicationName("Quartercore")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("quartercore")
    icon = str(HERE / "icon.svg")
    app.setWindowIcon(QIcon(icon))

    if not args.screenshot and already_running():
        return 0

    settings = Settings()
    translator = i18n.JsonTranslator(app)
    translator.set_language(i18n.resolve(settings.language))
    app.installTranslator(translator)

    backend = Backend(args.url or os.environ.get("OLH_URL") or settings.serverUrl)
    tray_available = QSystemTrayIcon.isSystemTrayAvailable() and not args.screenshot

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("backend", backend)
    context.setContextProperty("settings", settings)
    profiles = Profiles(backend)
    context.setContextProperty("profiles", profiles)
    lighting = Lighting(backend)
    context.setContextProperty("lighting", lighting)
    keyboard = Keyboard(backend)
    context.setContextProperty("keyboard", keyboard)
    headset = Headset(backend)
    context.setContextProperty("headset", headset)
    edge = Edge(backend)
    context.setContextProperty("edge", edge)
    edge_editor = EdgeEditor(backend, edge)
    context.setContextProperty("edgeEditor", edge_editor)
    context.setContextProperty("appVersion", __version__)
    context.setContextProperty("languages", [{"code": "system", "name": ""}]
                               + [{"code": k, "name": v} for k, v in i18n.LANGUAGES.items()])
    context.setContextProperty("trayAvailable", tray_available)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]

    def show_window(toggle=False):
        if toggle and window.isVisible():
            window.hide()
            return
        window.show()
        window.raise_()
        window.requestActivate()

    def apply_language():
        code = i18n.resolve(settings.language)
        texts = i18n.load(code)
        if translator.texts != texts:
            translator.texts = texts
            engine.retranslate()

    settings.changed.connect(apply_language)

    # Keep running in the tray when the window is closed (see onClosing in Main.qml)
    app.setQuitOnLastWindowClosed(not tray_available)
    if tray_available:
        def open_edge_editor():
            window.setProperty("section", "edge")
            show_window()
        tray = Tray(backend, icon, show_window, app.quit, app, settings, open_edge_editor)
        tray.show()

    # A second start shows this window instead of opening another one
    server = QLocalServer(app)
    if not args.screenshot:
        QLocalServer.removeServer(INSTANCE)
        server.listen(INSTANCE)
        server.newConnection.connect(lambda: (server.nextPendingConnection().close(), show_window()))

    # The native XENEON EDGE kiosk, made when it is first turned on
    edge_window = []

    def edge_screen():
        screen = find_edge_screen(app.screens())
        edge.set_screen_name(screen.name() if screen else "")
        return screen

    def update_edge():
        screen = edge_screen()
        wanted = settings.edgeKiosk and screen is not None and not args.screenshot
        if wanted and not edge_window:
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(HERE / "qml" / "EdgeWindow.qml")))
            created = component.create(context)
            if created is None:
                print(component.errorString(), file=sys.stderr)
                return
            edge_window.append(created)
        if not edge_window:
            return
        win = edge_window[0]
        if wanted:
            win.setScreen(screen)
            win.setGeometry(screen.geometry())
            win.showFullScreen()
        else:
            win.hide()

    settings.changed.connect(update_edge)
    app.screenAdded.connect(lambda _s: update_edge())
    app.screenRemoved.connect(lambda _s: update_edge())
    update_edge()

    backend.start()
    if not (args.minimized and tray_available):
        show_window()

    if args.screenshot:
        # profiles:<name> opens that profile
        section, _, profile = args.page.partition(":")
        if section in ("settings", "profiles", "lighting", "edge"):
            QTimer.singleShot(1500, lambda: window.setProperty("section", section))
            if profile and section == "profiles":
                QTimer.singleShot(3000, lambda: profiles.select(profile))
            elif profile and section == "lighting":
                QTimer.singleShot(3000, lambda: lighting.selectEffect(profile))
            elif profile and section == "edge":
                # edge:<widget id> selects that widget in the editor
                QTimer.singleShot(3000, lambda: edge_editor.select("widget:" + profile))
        elif args.page == "kiosk":
            # Renders the kiosk at 2560 x 720, also without a XENEON EDGE screen
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(HERE / "qml" / "EdgeWindow.qml")))
            edge_window.append(component.create(context))
            if edge_window[0] is None:
                print(component.errorString(), file=sys.stderr)
                return 1
            edge_window[0].show()
            window = edge_window[0]
        elif args.page:
            # <serial>:<tab>[:<key id>] opens a keyboard tab, e.g. KB1:keys:10
            serial, _, rest = args.page.partition(":")
            tab, _, key_id = rest.partition(":")
            QTimer.singleShot(1500, lambda: backend.selectDevice(serial))
            if tab:
                QTimer.singleShot(3000, lambda: keyboard.tabRequested.emit(tab, int(key_id or -1)))

        def grab():
            window.grabWindow().save(args.screenshot)
            app.quit()
        QTimer.singleShot(5000, grab)

    code = app.exec()
    # Delete the QML first, so its bindings don't read a deleted backend
    del engine
    return code


if __name__ == "__main__":
    sys.exit(main())
