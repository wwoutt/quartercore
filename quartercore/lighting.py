# Lighting: the RGB effects of a device and their colours, speed and direction
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Every device has its own set of effects (RGB profiles). Which options an
# effect has follows the OpenLinkHub RGB editor (static/js/rgb.js), and saving
# sends the same PUT /api/color/change request.

from PySide6.QtCore import Property, QObject, Signal, Slot

# Effects with their own editor in OpenLinkHub, or that have nothing to set
HIDDEN = {"keyboard", "mouse", "stand", "mousepad", "headset", "custom", "off", "led"}
FIXED_SPEED = {"cpu-temperature", "gpu-temperature", "liquid-temperature", "static", "storm", "off"}
THREE_SPEEDS = {"tlk", "tlr", "spiralrainbow", "rainbowwave", "rain", "visor", "colorwave"}
ALTERNATING = {"colorpulse", "colorshift", "tlk", "tlr", "rain", "visor", "colorwave", "watercolor"}
TEMPERATURE = {"cpu-temperature", "gpu-temperature", "liquid-temperature"}
PROBE = "probe-temperature"


def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


DIRECTIONS = [
    {"value": 1, "name": N_("Top to bottom")},
    {"value": 2, "name": N_("Bottom to top")},
    {"value": 4, "name": N_("Left to right")},
    {"value": 5, "name": N_("Right to left")},
]


def to_hex(c):
    c = c or {}
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c.get(k) or 0)))) for k in ("red", "green", "blue"))


def from_hex(text, temperature=0.0):
    text = (text or "#000000").lstrip("#")
    if len(text) != 6:
        raise ValueError("invalid colour")
    r, g, b = (int(text[i:i + 2], 16) for i in (0, 2, 4))
    return {"red": r, "green": g, "blue": b, "temperature": float(temperature)}


def preview(data):
    """Two colours for the swatch in the effect list."""
    stops = sorted((data.get("gradients") or {}).values(), key=lambda c: float(c.get("position") or 0))
    if stops:
        return [to_hex(stops[0]), to_hex(stops[-1])]
    return [to_hex(data.get("start")), to_hex(data.get("end"))]


def color_mode(key, data):
    if data.get("gradients") is not None:
        return "gradient"
    if key in TEMPERATURE:
        return "temperature"
    return "two"


def effect_view(key, data):
    """What the editor shows for one effect."""
    speed_min, speed_max, speed_step = (1, 3, 1) if key in THREE_SPEEDS else (1, 10, 0.1)
    gradient = sorted(((data.get("gradients") or {}).items()), key=lambda kv: int(kv[0]))
    return {
        "key": key,
        "name": data.get("profileName") or key,
        "colorMode": color_mode(key, data),
        "start": {"color": to_hex(data.get("start")), "temperature": (data.get("start") or {}).get("temperature", 0)},
        "middle": {"color": to_hex(data.get("middle")), "temperature": (data.get("middle") or {}).get("temperature", 0)},
        "end": {"color": to_hex(data.get("end")), "temperature": (data.get("end") or {}).get("temperature", 0)},
        "gradient": [{"color": to_hex(c), "position": float(c.get("position") or 0),
                      "brightness": float(c.get("brightness") or 1)} for _, c in gradient],
        "speed": max(speed_min, min(speed_max, float(data.get("speed") or speed_min))),
        "speedFixed": key in FIXED_SPEED,
        "speedMin": speed_min,
        "speedMax": speed_max,
        "speedStep": speed_step,
        "direction": int(data.get("rgbDirection") or 0),
        "alternating": key in ALTERNATING,
        "alternateColors": bool(data.get("alternateColors")),
        "probe": key == PROBE,
        "minTemp": float(data.get("minTemp") or 0),
        "maxTemp": float(data.get("maxTemp") or 0),
    }


def change_request(serial, effect, values):
    """The PUT /api/color/change body for the editor values; raises ValueError when invalid."""
    mode = effect["colorMode"]
    start = values.get("start") or effect["start"]
    middle = values.get("middle") or effect["middle"]
    end = values.get("end") or effect["end"]
    speed = float(values.get("speed", effect["speed"]))
    if effect["speedFixed"]:
        speed = effect["speed"]
    if not 1 <= speed <= 10:
        raise ValueError("speed")
    body = {
        "deviceId": serial,
        "profile": effect["key"],
        "startColor": from_hex(start["color"], start.get("temperature", 0)),
        "middleColor": from_hex(middle["color"], middle.get("temperature", 0)),
        "endColor": from_hex(end["color"], end.get("temperature", 0)),
        "speed": round(speed, 1),
        "alternateColors": bool(values.get("alternateColors", effect["alternateColors"])) and effect["alternating"],
        "rgbDirection": int(values.get("direction", effect["direction"])) if effect["direction"] else 0,
    }
    if mode == "temperature":
        temps = [body["startColor"]["temperature"], body["middleColor"]["temperature"], body["endColor"]["temperature"]]
        if temps != sorted(temps) or not all(0 <= t <= 150 for t in temps):
            raise ValueError("temperatures")
    if mode == "gradient":
        stops = sorted(values.get("gradient") or effect["gradient"], key=lambda s: float(s["position"]))
        if len(stops) < 2:
            raise ValueError("gradient")
        zones = {}
        for i, s in enumerate(stops):
            c = from_hex(s["color"])
            del c["temperature"]
            zones[str(i)] = dict(c, brightness=round(float(s.get("brightness", 1)), 2),
                                 position=round(max(0.0, min(1.0, float(s["position"]))), 2), Hex=s["color"])
        body["colorZones"] = zones
    if effect["probe"]:
        lo, hi = float(values.get("minTemp", effect["minTemp"])), float(values.get("maxTemp", effect["maxTemp"]))
        if not (0 <= lo <= hi <= 100):
            raise ValueError("probe temperatures")
        body["rgbMinTemp"], body["rgbMaxTemp"] = lo, hi
    return body


class Lighting(QObject):
    devicesChanged = Signal()
    effectsChanged = Signal()
    selectedChanged = Signal()

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self._devices = []
        self._serial = ""
        self._effects = []
        self._raw = {}
        self._selected = {}
        self._auto = True
        self._signature = None
        backend.devicesChanged.connect(self.refreshDevices)

    @property
    def api(self):
        return self.backend.api

    @Property("QVariantList", notify=devicesChanged)
    def devices(self):
        return self._devices

    @Property(str, notify=effectsChanged)
    def serial(self):
        return self._serial

    @Property("QVariantList", notify=effectsChanged)
    def effects(self):
        return self._effects

    @Property("QVariantMap", notify=selectedChanged)
    def selected(self):
        return self._selected

    @Property("QVariantList", constant=True)
    def directions(self):
        return [dict(d, name=self.tr(d["name"])) for d in DIRECTIONS]

    @Slot()
    def refreshDevices(self):
        """Keeps the devices that have RGB effects (OpenLinkHub answers the others with an error)."""
        candidates = list(self.backend.devices)
        # The device list is refreshed every few seconds; only check again when it changed
        signature = [(d["serial"], d["page"]) for d in candidates]
        if signature == self._signature:
            return
        self._signature = signature
        found = {}

        def check(device):
            def done(ok, data, error):
                if ok and (data.get("data") or {}).get("profiles"):
                    found[device["serial"]] = device
                    self._devices = [d for d in candidates if d["serial"] in found]
                    self.devicesChanged.emit()
                    # Until the user picks one: the first device, or better a LINK System Hub
                    current = next((d for d in self._devices if d["serial"] == self._serial), None)
                    if self._auto and (current is None or (current["page"] != "linkhub" and device["page"] == "linkhub")):
                        self._select(device["serial"])
            self.api.get("/api/color/" + device["serial"], done)
        for device in candidates:
            check(device)

    @Slot(str)
    def selectDevice(self, serial):
        """Chosen by the user."""
        self._auto = False
        self._select(serial)

    def _select(self, serial):
        def done(ok, data, error):
            if serial != self._serial:
                return
            if not ok:
                self.backend.notify.emit(error, False)
                return
            self._raw = (data.get("data") or {}).get("profiles") or {}
            self._effects = sorted(
                ({"key": k, "name": v.get("profileName") or k, "preview": preview(v)}
                 for k, v in self._raw.items() if k not in HIDDEN),
                key=lambda e: e["name"].lower())
            self.effectsChanged.emit()
            keys = [e["key"] for e in self._effects]
            key = self._selected.get("key")
            if key not in keys:
                key = "static" if "static" in keys else (keys[0] if keys else None)
            if key:
                self.selectEffect(key)
        if serial != self._serial:
            self._serial = serial
            self._selected = {}
            self.effectsChanged.emit()
            self.selectedChanged.emit()
        self.api.get("/api/color/" + serial, done)

    @Slot(str)
    def selectEffect(self, key):
        data = self._raw.get(key)
        if data is None or key in HIDDEN:
            return
        self._selected = effect_view(key, data)
        self.selectedChanged.emit()

    @Slot("QVariantMap")
    def save(self, values):
        if not self._selected:
            return
        try:
            body = change_request(self._serial, self._selected, values)
        except (ValueError, KeyError, TypeError):
            self.backend.notify.emit(self.tr("Check the colours, temperatures and speed"), False)
            return
        serial, key = self._serial, self._selected["key"]

        def done(ok, data, error):
            self.backend.notify.emit(str((data or {}).get("message") or error), ok)
            if ok and serial == self._serial:
                self._selected = {"key": key}
                self._select(serial)
        self.api.put("/api/color/change", body, done)

    @Slot(str)
    def applyToHub(self, key):
        """Uses the effect on every fan and device of a LINK System Hub."""
        self.backend.setHubRgbProfile(self._serial, key)
