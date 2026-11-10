# Checks that a window made with create_window survives QML garbage collection
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run by tests/test_edge.py in its own process. Without the kept component the
# XENEON EDGE kiosk window was deleted about a second after the editor opened.
import json, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import shiboken6
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
app = QGuiApplication([])
from quartercore.__main__ import create_window
engine = QQmlApplicationEngine()
qml = Path(tempfile.mkdtemp()) / "W.qml"
qml.write_text("import QtQuick\nWindow { width: 10; height: 10 }\n")
keep = []
window = create_window(engine, engine.rootContext(), qml, keep)
for _ in range(3):
    engine.collectGarbage()
    app.processEvents()
    app.sendPostedEvents(None, 0)
print(json.dumps({"made": window is not None, "alive": window is not None and shiboken6.isValid(window),
                  "kept": len(keep)}))
