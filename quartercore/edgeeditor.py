# XENEON EDGE layout editor: the saved layout, editing it, and widget settings
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Owns ~/.config/Quartercore/xeneon-edge.json (see edgelayout.py) and gives the
# kiosk its widgets. The first time, it takes over the layout of the fork's
# web editor and the widget settings of OpenLinkHub when OpenLinkHub has them;
# otherwise it starts with the upstream default widgets. Changes are a draft
# until they are saved; the kiosk shows them right after saving.
# Modified by wwoutt, 2026-11-11: own HTML widgets (customwidgets/) can be added

import copy
import json
import os

from PySide6.QtCore import Property, QObject, QTimer, QUrl, QUrlQuery, Signal, Slot
from PySide6.QtNetwork import QNetworkRequest

from . import edgelayout as store
from . import sensors
from .edge import WIDGET_DEFAULTS, widget_settings

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


WIDGET_NAMES = {1: N_("Date / Time"), 2: N_("Weather"), 3: N_("Media Player"), 4: N_("Battery Status"),
                5: N_("Calendar"), 6: N_("CPU Temp"), 7: N_("CPU Load"), 8: N_("GPU Temp"), 9: N_("GPU Load"),
                10: N_("Device Temperature"), 11: N_("Device RPM"), 12: N_("Temperature History"),
                13: N_("Cooling Overview"), 14: N_("Profile Shortcuts"), 15: N_("Memory Usage"),
                16: N_("Storage Overview"), 17: N_("Network"), 18: N_("Power"), 19: N_("GPU Details"),
                20: N_("Home Assistant"), 21: N_("Top Processes"), 22: N_("System Info"),
                23: N_("Home Assistant Buttons")}
WATCH_INTERVAL_MS = 3000


def keyed(layout, names=None):
    """The layout items with the fields the editor uses; names: own widget id -> name."""
    items = []
    for item in layout["items"]:
        item = copy.deepcopy(item)
        item["key"] = store.item_key(item)
        item["template"] = item["settings"]["template"]
        if item.get("custom"):
            item["name"] = (names or {}).get(item["custom"], item["custom"])
        else:
            item["custom"] = ""
            item["name"] = WIDGET_NAMES.get(item["widgetId"], item["settings"].get("name", ""))
        items.append(item)
    return items


def stored(item):
    """An editor item as it goes into the layout file."""
    out = {k: copy.deepcopy(item[k]) for k in ("widgetId", "x", "y", "w", "h", "hidden", "settings")}
    if item.get("custom"):
        out["custom"] = item["custom"]
    return out


class EdgeEditor(QObject):
    changed = Signal()
    # Separate from changed, so selecting a widget doesn't rebuild the preview (and stop a drag)
    selectionChanged = Signal()
    savedChanged = Signal()
    choicesChanged = Signal()
    citiesFound = Signal("QVariantList")

    def __init__(self, backend, edge, parent=None, path=None, custom_widgets=None):
        super().__init__(parent or backend)
        self.backend = backend
        self.edge = edge
        self.custom_widgets = custom_widgets
        if custom_widgets is not None:
            custom_widgets.changed.connect(self._custom_changed)
        self.path = path or store.layout_path()
        self.geocoding_url = os.environ.get("QUARTERCORE_GEOCODING_URL") or GEOCODING_URL
        self._saved = None
        self._draft = []
        self._selected = ""
        self._stats = {}
        self._battery = {}
        self._mtime = None
        self._choices_version = 0
        self.watch_timer = QTimer(self, interval=WATCH_INTERVAL_MS, timeout=self._watch)
        self.watch_timer.start()
        layout = store.load(self.path)
        if layout is None:
            self._use(store.default_layout(), write=False)
            self.importFromOpenLinkHub(only_if_new=True)
        else:
            self._use(layout, write=False)

    # --- the saved layout ---

    def _names(self):
        return {w["id"]: w["name"] for w in (self.custom_widgets.widgets if self.custom_widgets else [])}

    def _shown(self, layout):
        items = store.shown_items(layout)
        names = self._names()
        for item in items:
            if item["custom"]:
                item["name"] = names.get(item["custom"], item["custom"])
        return items

    def _custom_changed(self):
        """Own widgets were installed, removed or renamed: new names and add menu."""
        names = self._names()
        for item in self._draft:
            if item.get("custom"):
                item["name"] = names.get(item["custom"], item["custom"])
        if self._saved is not None:
            self.edge.set_items(self._shown(self._saved))
        self.changed.emit()
        self.selectionChanged.emit()

    def _use(self, layout, write=True):
        if write:
            store.save(store.clean(layout), self.path)
            self._mtime = self._file_time()
        self._saved = layout
        self._draft = keyed(layout, self._names())
        self.edge.set_items(self._shown(layout))
        self.edge.set_preview_items([])
        self.changed.emit()
        self.selectionChanged.emit()
        self.savedChanged.emit()

    def _file_time(self):
        try:
            return os.path.getmtime(self.path)
        except OSError:
            return None

    def _watch(self):
        """Another program (or a second Quartercore) changed the file: load it, unless there are edits."""
        current = self._file_time()
        if current is None or current == self._mtime:
            return
        self._mtime = current
        if self.dirty:
            return
        layout = store.load(self.path)
        if layout is not None:
            self._use(layout, write=False)

    # --- properties for QML ---

    @Property("QVariantList", notify=changed)
    def items(self):
        return self._draft

    @Property(bool, notify=changed)
    def dirty(self):
        return self._draft != keyed(self._saved, self._names())

    @Property(str, notify=selectionChanged)
    def selected(self):
        return self._selected

    @Property("QVariantMap", notify=selectionChanged)
    def selectedItem(self):
        return next((i for i in self._draft if i["key"] == self._selected), {})

    @Property("QVariantList", notify=changed)
    def available(self):
        """Widgets that aren't in the layout yet."""
        placed = {i["widgetId"] for i in self._draft}
        own = {i["custom"] for i in self._draft if i.get("custom")}
        return [{"id": k, "custom": "", "name": self.tr(WIDGET_NAMES[k])} for k in sorted(WIDGET_DEFAULTS)
                if k not in placed] + [
            {"id": 0, "custom": w["id"], "name": self.tr("%1 (own widget)").replace("%1", w["name"])}
            for w in (self.custom_widgets.widgets if self.custom_widgets else []) if w["id"] not in own]

    @Property(str, notify=changed)
    def problem(self):
        """The first wrong setting of the draft, empty when it can be saved."""
        for item in self._draft:
            field = store.check_settings(item["settings"])
            if field:
                return self.tr("%1: %2 is not valid").replace("%1", self.tr(item["name"])).replace("%2", self.tr(field))
        return ""

    # --- editing ---

    def _item(self, key):
        return next((i for i in self._draft if i["key"] == key), None)

    def _edited(self):
        self.edge.set_preview_items([i for i in self._draft if not i["hidden"]])
        self.changed.emit()
        self.selectionChanged.emit()

    @Slot(str)
    def select(self, key):
        if key != self._selected:
            self._selected = key
            self.selectionChanged.emit()
            self.refreshChoices()

    @Slot(str, int, int, int, int, result=bool)
    def place(self, key, x, y, w, h):
        """Moves or resizes a widget; refused when it would leave the grid or cover another widget."""
        item = self._item(key)
        if item is None:
            return False
        candidate = dict(item, x=int(x), y=int(y), w=int(w), h=int(h))
        if not store.fits(candidate, self._draft):
            self.changed.emit()      # puts the dragged frame back
            return False
        item.update(x=candidate["x"], y=candidate["y"], w=candidate["w"], h=candidate["h"])
        self._edited()
        return True

    @Slot(str, bool)
    def setHidden(self, key, hidden):
        item = self._item(key)
        if item is None:
            return
        if not hidden and not store.fits(dict(item, hidden=False), self._draft):
            spot = store.free_spot(self._draft, item["w"], item["h"])
            if spot is None:
                self.backend.notify.emit(self.tr("There is no free place for this widget"), False)
                return
            item.update(x=spot["x"], y=spot["y"], w=spot["w"], h=spot["h"])
        item["hidden"] = bool(hidden)
        self._edited()

    @Slot(int)
    def add(self, widget_id):
        if widget_id not in WIDGET_DEFAULTS or self._item("widget:%d" % widget_id):
            return
        spot = store.free_spot(self._draft)
        hidden = spot is None
        if hidden:
            # The grid is full: add it hidden, to show once there is room
            spot = {"x": 0, "y": 0, "w": 4, "h": 4}
            self.backend.notify.emit(self.tr("No free place: the widget is added hidden. Make room and turn it on."),
                                     False)
        settings = widget_settings(widget_id)
        self._draft.append({"widgetId": widget_id, "x": spot["x"], "y": spot["y"], "w": spot["w"],
                            "h": spot["h"], "hidden": hidden, "settings": settings,
                            "key": "widget:%d" % widget_id, "template": settings["template"],
                            "name": WIDGET_NAMES[widget_id]})
        self._selected = "widget:%d" % widget_id
        self._edited()
        self.refreshChoices()

    @Slot(str)
    def addCustom(self, widget_id):
        """Adds an own widget in its default size; its settings show right away."""
        widget = self.custom_widgets.manifest(widget_id) if self.custom_widgets else None
        if widget is None or self._item("custom:" + widget_id):
            return
        spot = store.free_spot(self._draft, widget["size"]["w"], widget["size"]["h"])
        hidden = spot is None
        if hidden:
            spot = {"x": 0, "y": 0, "w": widget["size"]["w"], "h": widget["size"]["h"]}
            self.backend.notify.emit(self.tr("No free place: the widget is added hidden. Make room and turn it on."),
                                     False)
        item = store.custom_item(widget_id, spot["x"], spot["y"], spot["w"], spot["h"], hidden)
        item.update(key="custom:" + widget_id, template="custom", name=widget["name"])
        self._draft.append(item)
        self._selected = item["key"]
        self._edited()

    @Slot(str)
    def remove(self, key):
        self._draft = [i for i in self._draft if i["key"] != key]
        if self._selected == key:
            self._selected = ""
        self._edited()

    @Slot(str, str, "QVariant")
    def setSetting(self, key, name, value):
        item = self._item(key)
        if item is None:
            return
        field = next((f for f in store.fields(item["template"]) if f["name"] == name), None)
        if field and field["kind"] == "int":
            try:
                value = int(value)
            except (TypeError, ValueError):
                pass
        elif field and field["kind"] == "float":
            try:
                value = float(value)
            except (TypeError, ValueError):
                pass
        elif field and field["kind"] == "channel":
            value = int(value or 0)
        item["settings"] = dict(item["settings"], **{name: value})
        self._edited()

    @Slot()
    def save(self):
        problem = self.problem
        if problem:
            self.backend.notify.emit(problem, False)
            return
        layout = {"version": store.VERSION, "columns": store.COLUMNS, "rows": store.ROWS,
                  "items": [stored(i) for i in self._draft]}
        self._use(layout)
        self.backend.notify.emit(self.tr("Layout saved"), True)

    @Slot()
    def revert(self):
        self._draft = keyed(self._saved, self._names())
        self._edited()

    @Slot()
    def resetDefaults(self):
        """A draft with the upstream default widgets; saved only with save()."""
        self._draft = keyed(store.default_layout())
        self._selected = ""
        self._edited()

    @Slot()
    def importFromOpenLinkHub(self, only_if_new=False):
        """Takes over the fork's layout and OpenLinkHub's widget settings."""
        def done(ok, data, error):
            payload = (data or {}).get("data") if ok else None
            if not payload:
                if not only_if_new:
                    self.backend.notify.emit(self.tr("OpenLinkHub has no XENEON EDGE layout"), False)
                return
            serial = payload.get("serial") or ""
            self.backend.api.get("/api/devices/" + serial, lambda ok2, d2, e2: finish(
                payload, ((d2 or {}).get("device") or {}).get("DeviceProfile", {}).get("WidgetAreas") if ok2 else None))

        def finish(payload, profile_areas):
            # Only the first time when the user hasn't saved anything meanwhile
            if only_if_new and self._file_time() is not None:
                return
            layout = store.from_openlinkhub(payload.get("areas") or [], payload.get("layout"), profile_areas)
            if only_if_new:
                self._use(layout)
            else:
                self._draft = keyed(layout)
                self._edited()
            self.backend.notify.emit(self.tr("Layout taken over from OpenLinkHub"), True)
        self.backend.api.get("/api/xeneonLayout", done)

    # --- choices for the settings ---

    @Property(int, notify=choicesChanged)
    def choicesVersion(self):
        return self._choices_version

    def _choices_arrived(self):
        self._choices_version += 1
        self.choicesChanged.emit()

    @Slot()
    def refreshChoices(self):
        """Devices and sensors for the settings form (still from OpenLinkHub)."""
        def stats(ok, data, error):
            self._stats = (data or {}).get("data") or {} if ok else {}
            self._choices_arrived()

        def tray(ok, data, error):
            self._battery = ((data or {}).get("data") or {}).get("battery") or {} if ok else {}
            self._choices_arrived()
        self.backend.api.get("/api/stats/devices", stats)
        self.backend.api.get("/api/systray", tray)

    @Slot(str, str, result="QVariantList")
    def choices(self, kind, device=""):
        products = {d["serial"]: d["product"] for d in self.backend.devices}
        if kind == "device":
            return [{"value": "", "name": self.tr("(none)")}] + [
                {"value": serial, "name": products.get(serial, serial)} for serial in sorted(self._stats)]
        if kind == "profileDevice":
            return [{"value": "", "name": self.tr("(none)")}] + [
                {"value": d["serial"], "name": d["product"]} for d in self.backend.devices]
        if kind == "channel":
            channels = ((self._stats.get(device) or {}).get("Devices") or {})
            return [{"value": int(c), "name": "%s · %s" % (c, v.get("Label") if v.get("Label") not in (None, "", "Set Label")
                                                          else v.get("Device") or "")}
                    for c, v in sorted(channels.items(), key=lambda kv: int(kv[0]))]
        if kind == "battery":
            return [{"value": "", "name": self.tr("All devices")}] + [
                {"value": serial, "name": b.get("Device") or serial} for serial, b in sorted(self._battery.items())]
        if kind == "mount":
            return [{"value": "", "name": self.tr("All file systems")}] + [
                {"value": m["MountPoint"], "name": m["MountPoint"]} for m in sensors.storage_mounts()]
        if kind == "netInterface":
            return [{"value": "", "name": self.tr("All connections")}] + [
                {"value": name, "name": name} for name in sorted(sensors.network_counters())]
        if kind == "psuDevice":
            return [{"value": "", "name": self.tr("The first power supply")}] + [
                {"value": d["serial"], "name": d["product"]} for d in self.backend.devices if d.get("page") == "psu"]
        if kind == "storageSensor":
            return [{"value": "", "name": self.tr("Don't show")}, {"value": "*", "name": self.tr("All drives")}] + [
                {"value": t["Key"], "name": "%s (%s)" % (t["Model"], t["Key"])} for t in sensors.storage_temperatures()]
        return []

    @Slot(str, result="QVariantList")
    def fields(self, template):
        out = []
        for field in store.fields(template):
            f = dict(field, label=self.tr(field["label"]))
            if "choices" in f:
                f["choices"] = [dict(c, name=self.tr(c["name"])) for c in f["choices"]]
            out.append(f)
        return out

    # --- weather city ---

    @Slot(str)
    def searchCity(self, name):
        """Looks a city up with Open-Meteo's geocoding; only when the user asks for it."""
        name = name.strip()
        if len(name) < 2:
            return
        url = QUrl(self.geocoding_url)
        query = QUrlQuery()
        for k, v in (("name", name), ("count", "6"), ("format", "json")):
            query.addQueryItem(k, v)
        url.setQuery(query)
        reply = self.backend.api.manager.get(QNetworkRequest(url))
        reply.finished.connect(lambda: self._cities(reply))

    def _cities(self, reply):
        raw = bytes(reply.readAll())
        reply.deleteLater()
        try:
            results = json.loads(raw).get("results") or []
        except (ValueError, AttributeError):
            results = []
        self.citiesFound.emit([{"name": r.get("name") or "", "country": r.get("country") or "",
                                "admin": r.get("admin1") or "", "latitude": r.get("latitude"),
                                "longitude": r.get("longitude")} for r in results])

    @Slot(str, "QVariantMap")
    def setCity(self, key, city):
        item = self._item(key)
        if item is None:
            return
        item["settings"] = dict(item["settings"], city=city.get("name", ""), country=city.get("country", ""),
                                latitude=float(city.get("latitude") or 0), longitude=float(city.get("longitude") or 0))
        self._edited()
