# Starts OpenLinkHub Desktop
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Usage: python3 -m openlinkhub_desktop [--url http://127.0.0.1:27003]
#        [--screenshot file.png [--page serial]]   (grab the window and exit, for tests)

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from . import __version__
from .api import DEFAULT_URL
from .backend import Backend

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(prog="openlinkhub-desktop")
    parser.add_argument("--url", default=os.environ.get("OLH_URL", DEFAULT_URL))
    parser.add_argument("--screenshot", help=argparse.SUPPRESS)
    parser.add_argument("--page", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # The KDE style when it is installed (Plasma), otherwise Fusion
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        QQuickStyle.setStyle("org.kde.desktop")
        QQuickStyle.setFallbackStyle("Fusion")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("OpenLinkHub Desktop")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("openlinkhub-desktop")
    app.setWindowIcon(QIcon(str(HERE / "icon.svg")))

    backend = Backend(args.url)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("appVersion", __version__)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    backend.start()

    if args.screenshot:
        if args.page:
            QTimer.singleShot(1500, lambda: backend.selectDevice(args.page))
        window = engine.rootObjects()[0]

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
