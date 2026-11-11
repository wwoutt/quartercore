# Opens the XENEON EDGE layout page while a device that refreshes is open, in the real app
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run by tests/test_edge.py in its own process, offscreen, against the fake
# OpenLinkHub. The page used to jump back to the device after its first refresh.
# Prints one JSON line with the section after a few refreshes.
import json, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
import fake_openlinkhub
server, url, state = fake_openlinkhub.start()
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import quartercore.__main__ as m
m.INSTANCE = "quartercore-section-check-%d" % os.getpid()     # never the running app
result = {}
started = []


def main_window():
    return next(w for w in QApplication.instance().topLevelWindows() if w.property("section") is not None)


def check():
    result["after"] = main_window().property("section")


original = m.Backend.start


def start(self):
    original(self)
    if not started:
        started.append(self)
        QTimer.singleShot(1000, lambda: self.selectDevice("HUB1"))
        QTimer.singleShot(2500, lambda: main_window().setProperty("section", "edge"))
        QTimer.singleShot(7500, check)            # the hub page refreshes every two seconds
        QTimer.singleShot(8000, lambda: (self.selectDevice("KB1"),
                                         result.__setitem__("opened", main_window().property("section"))))
        QTimer.singleShot(8500, lambda: QApplication.instance().quit())


m.Backend.start = start
sys.argv = ["quartercore", "--url", url]
try:
    m.main()
except SystemExit:
    pass
print(json.dumps(result), flush=True)
os._exit(0)
