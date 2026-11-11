# The own widgets for QML: list, web view addresses, settings and the store
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Context property "customWidgets". Store requests go to GitHub, so they run
# in a thread; their results arrive as signals in the main thread.

import sys
import threading

from PySide6.QtCore import Property, QObject, Qt, QTimer, Signal, Slot

from .library import Library
from .server import WidgetServer
from .store import Store, StoreError

WATCH_INTERVAL_MS = 3000


class CustomWidgets(QObject):
    changed = Signal()
    storeListed = Signal(str, "QVariantList", str)    # kind, widgets, error
    storePreviewed = Signal("QVariantMap", str)       # preview, error
    storeDone = Signal(str, str, str)                 # "install" or "uninstall", widget id, error
    _finished = Signal(object)                        # from a store thread to the main thread

    def __init__(self, parent=None, library=None, web_views=True):
        super().__init__(parent)
        self.library = library or Library(log=lambda message: print(message, file=sys.stderr))
        imported = self.library.import_openlinkhub()
        if imported:
            print("own widgets taken over from OpenLinkHub: " + ", ".join(imported), file=sys.stderr)
        self.server = WidgetServer(self.library).start()
        self.store = Store(str(self.library.dir), str(self.library.secrets_file), self.library.forget)
        self._web_views = bool(web_views)
        self._widgets = self.library.list()
        self._snapshot = self.library.snapshot()
        self._finished.connect(self._deliver, Qt.QueuedConnection)
        self.watch_timer = QTimer(self, interval=WATCH_INTERVAL_MS, timeout=self._watch)
        self.watch_timer.start()

    # --- the widgets ---

    def _watch(self):
        """A widget was added, removed or edited (by hand or by the store)."""
        snapshot = self.library.snapshot()
        if snapshot != self._snapshot:
            self.reload()

    @Slot()
    def reload(self):
        self._widgets = self.library.list()
        self._snapshot = self.library.snapshot()
        self.changed.emit()

    @Property("QVariantList", notify=changed)
    def widgets(self):
        return self._widgets

    @Property(bool, constant=True)
    def webViews(self):
        """False when QtWebEngine isn't installed: the kiosk then shows a placeholder."""
        return self._web_views

    def manifest(self, widget_id):
        return next((w for w in self._widgets if w["id"] == widget_id), None)

    @Slot(str, result="QVariantMap")
    def widget(self, widget_id):
        return self.manifest(widget_id) or {}

    @Slot(str, result=str)
    def frameUrl(self, widget_id):
        widget = self.manifest(widget_id)
        return self.server.frame_url(widget_id, widget["modified"]) if widget else ""

    @Slot(str, result=bool)
    def isOwnPage(self, url):
        """Web views may only show the widget server's pages."""
        return str(url).startswith(self.server.base_url)

    # --- settings (gear button) ---

    @Slot(str, result="QVariantList")
    def fields(self, widget_id):
        widget = self.manifest(widget_id)
        return widget["settings"] if widget else []

    @Slot(str, result="QVariantMap")
    def values(self, widget_id):
        return self.library.public_settings(widget_id)

    @Slot(str, "QVariantMap", result=str)
    def saveSettings(self, widget_id, values):
        """Empty on success, else the reason."""
        try:
            self.library.save_settings(widget_id, {k: v for k, v in values.items()})
        except (OSError, ValueError) as e:
            return str(e)
        return ""

    # --- the store ---

    def _run(self, work, done):
        """work() in a thread, then done(value, error) in the main thread."""
        def run():
            try:
                result = (work(), "")
            except (StoreError, OSError, ValueError) as e:
                result = (None, str(e))
            self._finished.emit((done, result))
        threading.Thread(target=run, daemon=True).start()

    def _deliver(self, finished):
        done, (value, error) = finished
        done(value, error)

    @Slot(str, str)
    def storeList(self, kind, query):
        self._run(lambda: self.store.list(kind, query),
                  lambda value, error: self.storeListed.emit(kind, value or [], error))

    @Slot(str, str)
    def storePreview(self, kind, ref):
        self._run(lambda: self.store.preview(kind, ref),
                  lambda value, error: self.storePreviewed.emit(value or {}, error))

    @Slot(str, str, str, bool)
    def storeInstall(self, kind, ref, commit, confirmed):
        def done(value, error):
            self.reload()
            self.storeDone.emit("install", (value or {}).get("id", ""), error)
        self._run(lambda: self.store.install(kind, ref, commit or None, bool(confirmed)), done)

    @Slot(str)
    def storeUninstall(self, widget_id):
        def done(value, error):
            self.reload()
            self.storeDone.emit("uninstall", widget_id, error)
        self._run(lambda: self.store.uninstall(widget_id), done)
