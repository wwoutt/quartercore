# Drags and resizes a widget in the XENEON EDGE editor with simulated mouse events
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run by tests/test_edge.py in its own process (QML needs a QApplication);
# offscreen, against the fake OpenLinkHub. Prints one JSON line with the result.
import json, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
from pathlib import Path
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication([])
import fake_openlinkhub
server, url, state = fake_openlinkhub.start()
state.edge = None
from quartercore.backend import Backend
from quartercore.edge import Edge
from quartercore.edgeeditor import EdgeEditor
from quartercore.settings import Settings
from test_edge import FakeSensors, FakeMedia
from test_backend import wait
backend = Backend(url)
edge = Edge(backend, sensors=FakeSensors, media=FakeMedia())
editor = EdgeEditor(backend, edge)
settings = Settings()
engine = QQmlApplicationEngine()
ctx = engine.rootContext()
for name, obj in (("backend", backend), ("edge", edge), ("edgeEditor", editor), ("settings", settings),
                  ("appVersion", "test"), ("trayAvailable", False), ("languages", [])):
    ctx.setContextProperty(name, obj)
for name in ("profiles", "lighting", "keyboard", "headset"):
    ctx.setContextProperty(name, None)
engine.load(QUrl.fromLocalFile(os.path.join(ROOT, "quartercore", "qml", "Main.qml")))
win = engine.rootObjects()[0]
win.show()
win.setProperty("section", "edge")
backend.start()
wait(lambda: False, 1500)
# Find the canvas: the preview is 2560 wide scaled; locate via the clock tile position
from PySide6.QtQuick import QQuickItem
def find(item, test):
    for child in item.childItems():
        if test(child):
            return child
        r = find(child, test)
        if r: return r
canvas = find(win.property("contentItem"), lambda i: i.width() == 2560 and i.height() == 720)
# Shrink the clock first with the resize handle: select it, then drag the corner
cw, ch = 2560 / 24, 720 / 12
def to_window(cx, cy):
    p = canvas.mapToScene(QPointF(cx, cy))
    return QPoint(int(p.x()), int(p.y()))
start = to_window(4 * cw, 2 * ch)
QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, start)
wait(lambda: False, 300)
selected = editor.selected
# The handle is at the bottom right of the clock (8x4 cells), 32 px in
handle = to_window(8 * cw - 32, 4 * ch - 32)
QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, handle)
for step in range(1, 11):
    QTest.mouseMove(win, to_window(8 * cw - 32 - step * 2 * cw / 10, 4 * ch - 32 - step * ch / 10))
QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, to_window(6 * cw - 32, 3 * ch - 32))
wait(lambda: False, 300)
clock = next(i for i in editor.items if i["widgetId"] == 1)
resized = {k: clock[k] for k in "xywh"}
# Then drag it one cell right... blocked by the ring at x=8? clock now 6 wide, move +2 to x=2 fits
QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, to_window(2 * cw, 1 * ch))
for step in range(1, 11):
    QTest.mouseMove(win, to_window(2 * cw + step * 2 * cw / 10, 1 * ch))
QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, to_window(4 * cw, 1 * ch))
wait(lambda: False, 300)
clock = next(i for i in editor.items if i["widgetId"] == 1)
print(json.dumps({"selected": selected, "resized": resized, "moved": {k: clock[k] for k in "xywh"},
                  "dirty": editor.dirty}))
sys.stdout.flush()
server.shutdown()
os._exit(0)
