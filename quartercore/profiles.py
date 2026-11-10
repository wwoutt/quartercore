# Temperature (speed) profiles: list, fan and pump curves, create, delete
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Works with OpenLinkHub's graph profiles ("graphProfiles": true in its
# config.json): every profile has a curve of points for the pump (type 0) and
# for the fans (type 1), from temperature (x, °C) to speed (y, %). The
# requests are the same as the OpenLinkHub temperature graph page sends.

import re

from PySide6.QtCore import Property, QObject, Signal, Slot

# Shipped with OpenLinkHub; its web interface doesn't let you edit them either
BUILT_IN = ("Quiet", "Normal", "Performance")
NAME = re.compile(r"^[a-zA-Z0-9]{3,}$")
PUMP, FANS = 0, 1
LIQUID_SENSOR = 2



def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


# Sensors a new profile can use without choosing extra hardware in OpenLinkHub
SENSORS = [
    {"id": 0, "name": N_("CPU")},
    {"id": 1, "name": N_("GPU")},
    {"id": 2, "name": N_("Liquid temperature (AIO)")},
    {"id": 3, "name": N_("Storage temperature")},
    {"id": 5, "name": N_("CPU + GPU")},
    {"id": 10, "name": N_("Power supply")},
]


def clean_points(points):
    """Whole numbers within range, sorted by temperature, one point per temperature."""
    by_temperature = {}
    for p in points:
        x = max(0, min(200, int(round(float(p["x"])))))
        y = max(0, min(100, int(round(float(p["y"])))))
        by_temperature[x] = y
    return [{"x": x, "y": by_temperature[x]} for x in sorted(by_temperature)]


def profile_summary(name, data):
    linear = bool(data.get("linear"))
    steps = data.get("profiles") or []
    # Static profiles are one step over the whole range, see profileStatic in OpenLinkHub
    static = not linear and len(steps) == 1 and steps[0].get("min") == 0 and steps[0].get("max") == 200
    builtin = name in BUILT_IN
    return {
        "name": name,
        "sensor": data.get("sensor", 0),
        "sensorName": data.get("sensorString") or "",
        "zeroRpm": bool(data.get("zeroRpm")),
        "linear": linear,
        "static": static,
        "builtin": builtin,
        "editable": not (builtin or linear or static),
    }


class Profiles(QObject):
    listChanged = Signal()
    selectedChanged = Signal()

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self._list = []
        self._selected = {}

    @property
    def api(self):
        return self.backend.api

    @Property("QVariantList", notify=listChanged)
    def list(self):
        return self._list

    @Property("QVariantMap", notify=selectedChanged)
    def selected(self):
        return self._selected

    @Property("QVariantList", constant=True)
    def sensors(self):
        return [dict(s, name=self.tr(s["name"])) for s in SENSORS]

    @Slot()
    def refresh(self):
        def done(ok, data, error):
            if not ok:
                return
            items = [profile_summary(k, v) for k, v in (data.get("data") or {}).items() if not v.get("Hidden")]
            # Built-in profiles first, in their usual order, then the user's own
            items.sort(key=lambda p: (not p["builtin"], BUILT_IN.index(p["name"]) if p["builtin"] else 0,
                                      p["name"].lower()))
            self._list = items
            self.listChanged.emit()
            names = [p["name"] for p in items]
            name = self._selected.get("name")
            if name and name not in names:
                self._selected = {}
                self.selectedChanged.emit()
                name = None
            if not name and names:
                self.select("Normal" if "Normal" in names else names[0])
        self.api.get("/api/temperatures/", done)

    @Slot(str)
    def select(self, name):
        summary = next((p for p in self._list if p["name"] == name), None)
        if summary is None:
            return

        def done(ok, data, error):
            if not ok:
                self.backend.notify.emit(error, False)
                return
            graph = data.get("data") or {}
            self._selected = dict(
                summary,
                maxTemp=60 if summary["sensor"] == LIQUID_SENSOR else 100,
                pump=list((graph.get(str(PUMP)) or {}).get("points") or []),
                fans=list((graph.get(str(FANS)) or {}).get("points") or []))
            self.selectedChanged.emit()
        self.api.get("/api/temperatures/graph/" + name, done)

    @Slot(str, "QVariantList")
    def saveCurve(self, kind, points):
        """kind: "fans" or "pump"."""
        name = self._selected.get("name")
        if not name or not self._selected.get("editable"):
            return
        points = clean_points(points)
        if len(points) < 2:
            self.backend.notify.emit(self.tr("A curve needs at least two points"), False)
            return

        def done(ok, data, error):
            self.backend.notify.emit(str((data or {}).get("message") or error), ok)
            if ok and self._selected.get("name") == name:
                self.select(name)
        self.api.put("/api/temperatures/updateGraph",
                     {"profile": name, "updateType": FANS if kind == "fans" else PUMP, "points": points}, done)

    @Slot(str, int, bool, bool, bool, str)
    def create(self, name, sensor, zero_rpm, static, linear, storage_key):
        name = name.strip()
        if not NAME.match(name):
            self.backend.notify.emit(self.tr("Use at least 3 letters or digits, without spaces"), False)
            return
        if static and linear:
            self.backend.notify.emit(self.tr("A profile can't be static and linear at the same time"), False)
            return
        body = {"profile": name, "sensor": sensor, "zeroRpm": zero_rpm, "static": static, "linear": linear}
        if sensor == 3:
            if not storage_key:
                self.backend.notify.emit(self.tr("Choose a drive"), False)
                return
            body["hwmonDeviceId"] = storage_key

        def done(ok, data, error):
            self.backend.notify.emit(str((data or {}).get("message") or error), ok)
            if ok:
                self._after_change(select=name)
        self.api.post("/api/temperatures/new", body, done)

    @Slot(str)
    def remove(self, name):
        if name in BUILT_IN:
            return

        def done(ok, data, error):
            self.backend.notify.emit(str((data or {}).get("message") or error), ok)
            if ok:
                if self._selected.get("name") == name:
                    self._selected = {}
                    self.selectedChanged.emit()
                self._after_change()
        self.api.delete("/api/temperatures/delete", {"profile": name}, done)

    def _after_change(self, select=None):
        # The speed profile menus on device pages and in the tray use the same list
        self.backend.refreshSpeedProfiles()

        def done():
            self.listChanged.disconnect(done)
            if select:
                self.select(select)
        if select:
            self.listChanged.connect(done)
        self.refresh()
