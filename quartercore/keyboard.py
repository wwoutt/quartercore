# Keyboards: key layout, colours, settings, key assignments, macros, performance, dial colours
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# OpenLinkHub describes a keyboard as rows of keys. Every key has a width and
# a "left" distance to the key before it, so a row is laid out from left to
# right. Light bars at the sides are keys too (css "left-led-N", "right-led-N");
# they are drawn as strips along the edges.

import re
from collections import Counter

from PySide6.QtCore import Property, QObject, Signal, Slot

LED = re.compile(r"(left|right)-led-(\d+)")
KEY_HEIGHT = 70
STRIP_WIDTH = 10


def to_hex(c):
    c = c or {}
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c.get(k) or 0))) for k in ("red", "green", "blue"))


def most_common(values, default):
    values = list(values)
    return Counter(values).most_common(1)[0][0] if values else default


def options(mapping):
    """{"1": "Volume"} -> [{"value": 1, "name": "Volume"}], sorted by value."""
    return [{"value": k, "name": v} for k, v in sorted(((int(k), v) for k, v in (mapping or {}).items()))]


def assignment(k):
    """What a key does, from the key data OpenLinkHub keeps per colour profile."""
    return {
        "enabled": bool(k.get("default")),
        "pressAndHold": bool(k.get("actionHold")),
        "retainOriginal": bool(k.get("retainOriginal")),
        "modifier": int(k.get("modifierKey") or 0),
        "type": int(k.get("actionType") or 0),
        "value": int(k.get("actionCommand") or 0),
        "valueString": k.get("deviceId") or "",
        "toggleDelay": int(k.get("toggleDelay") or 0),
    }


def layout_keys(keyboard):
    """Positions every key: returns (keys, width, height) in OpenLinkHub's pixels."""
    keys, strips = [], []
    y_cursor = 0
    rows = sorted((keyboard.get("row") or {}).items(), key=lambda kv: int(kv[0]))
    for row_id, row in rows:
        row_keys = sorted((row.get("keys") or {}).items(), key=lambda kv: int(kv[0]))
        regular = [(int(i), k) for i, k in row_keys if not LED.search(k.get("css") or "")]
        for i, k in row_keys:
            led = LED.search(k.get("css") or "")
            if led:
                strips.append((int(i), led.group(1), int(led.group(2)), k))
        if not regular:
            continue
        top = most_common((k.get("top") or 0 for _, k in regular if (k.get("top") or 0) >= 0), 0)
        height = min(KEY_HEIGHT, most_common((k.get("height") or KEY_HEIGHT for _, k in regular), KEY_HEIGHT))
        y = y_cursor + top
        y_cursor = y + height
        # Rows below the top light bar leave room for the strip at the left edge
        x = STRIP_WIDTH if int(row_id) > 0 and strips else 0
        for key_id, k in regular:
            x += k.get("left") or 0
            width = k.get("width") or 65
            keys.append({
                "keyId": key_id, "row": int(row_id), "name": k.get("keyName") or "",
                "x": x, "y": y, "w": width,
                # Tall keys (numpad + and Enter) reach into the next row
                "h": k.get("height") if (k.get("height") or 0) > KEY_HEIGHT else height,
                "color": to_hex(k.get("color")),
                "light": bool(k.get("onlyColor")), "noColor": bool(k.get("noColor")),
                "assignment": assignment(k),
            })
            x += width
    width = max((k["x"] + k["w"] for k in keys), default=0)
    height = y_cursor
    # A tall key in the last row (numpad Enter) reaches below the rows
    bottom = max((k["y"] + k["h"] for k in keys), default=0)
    if strips:
        width += 4 + STRIP_WIDTH
        count = max(n for _, _, n, _ in strips)
        first = min((k["y"] for k in keys if k["row"] > 0), default=0)
        pitch = (height - first) / count
        for key_id, side, n, k in strips:
            keys.append({
                "keyId": key_id, "row": -1, "name": "",
                "x": 0 if side == "left" else width - STRIP_WIDTH,
                "y": first + (n - 1) * pitch, "w": STRIP_WIDTH, "h": pitch - 4,
                "color": to_hex(k.get("color")), "light": True, "noColor": False,
                "assignment": assignment(k),
            })
    return keys, width, max(height, bottom)


def keyboard_view(device):
    profile = device.get("DeviceProfile") or {}
    name = profile.get("Profile") or "default"
    keyboard = (profile.get("Keyboards") or {}).get(name) or {}
    keys, width, height = layout_keys(keyboard)
    user_profiles = device.get("userProfiles") or {}
    return {
        "serial": device.get("serial") or "",
        "product": device.get("product") or "",
        "firmware": device.get("firmware") or "",
        "keys": keys, "keysWidth": width, "keysHeight": height,
        "rgbModes": list(device.get("RGBModes") or []),
        "rgbMode": profile.get("RGBProfile") or "",
        "colorProfile": name,
        "colorProfiles": list(profile.get("Profiles") or []),
        "userProfile": next((k for k, v in user_profiles.items() if v.get("Active")), ""),
        "userProfiles": sorted(user_profiles),
        "layouts": list(device.get("Layouts") or []),
        "layout": profile.get("Layout") or "",
        "pollingRates": options(device.get("PollingRates")),
        "pollingRate": int(profile.get("PollingRate") or 0),
        "dialOptions": options(device.get("ControlDialOptions")),
        "dial": int(profile.get("ControlDial") or 0),
        "debounceTimes": options(device.get("DebounceTimes")),
        "debounceTime": int(profile.get("DebounceTime") or 0),
    }


def is_keyboard(device):
    return bool(((device.get("DeviceProfile") or {}).get("Keyboards")))


# --- key assignments, macros, performance and dial colours ---
#
# The requests are copied from upstream static/js/overview.js (key assignments
# with a modifier, performance, control dial colours) and static/js/macros.js.

def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


# Assignment types of the K100 (ProcessGetKeyAssignmentTypes); names shown translated
ASSIGNMENT_TYPES = {
    0: N_("None"), 1: N_("Media keys"), 2: N_("DPI +"), 3: N_("Keyboard"), 4: N_("DPI -"),
    8: N_("Sniper"), 9: N_("Mouse"), 10: N_("Macro"), 13: N_("Scroll up"), 14: N_("Scroll down"),
    15: N_("Zoom in"), 16: N_("Zoom out"), 17: N_("Screen brightness +"), 18: N_("Screen brightness -"),
    21: N_("Change profile"), 22: N_("Profile switch"),
}
# Types whose value is a text (mouse serial or profile name) instead of a number
STRING_TYPES = {2, 4, 8, 21}
MACRO_TYPE, SNIPER_TYPE = 10, 8

# Macro steps (macros.html): keyboard key, mouse button, delay, text, mouse position
MACRO_KEY, MACRO_MEDIA, MACRO_DELAY, MACRO_TEXT, MACRO_MOUSE, MACRO_POSITION = 3, 1, 5, 6, 9, 20
MACRO_STEP_TYPES = {
    MACRO_KEY: N_("Keyboard"), MACRO_MOUSE: N_("Mouse"), MACRO_DELAY: N_("Delay"),
    MACRO_TEXT: N_("Text"), MACRO_POSITION: N_("Mouse position"),
}
MACRO_TYPE_NAMES = dict(MACRO_STEP_TYPES)
MACRO_TYPE_NAMES[MACRO_MEDIA] = N_("Media keys")

PERFORMANCE = {
    "perf_winKey": N_("Disable Win key"),
    "perf_shiftTab": N_("Disable Shift + Tab"),
    "perf_altTab": N_("Disable Alt + Tab"),
    "perf_altF4": N_("Disable Alt + F4"),
}

DIAL_NAMES = {
    1: N_("Volume Control"), 2: N_("Brightness"), 3: N_("Vertical Scroll"), 4: N_("Zoom"),
    5: N_("Screen Brightness"), 6: N_("Media Control"), 7: N_("Horizontal Scroll"),
}

# Qt reports X11/xkb key codes, which are the Linux evdev codes plus 8
XKB_OFFSET = 8


def key_list(data):
    """/api/input/keyboard and friends: {"30": {"Name": "A", "CommandCode": 30}} -> sorted options."""
    items = []
    for index, value in (data or {}).items():
        name = value.get("Name") if isinstance(value, dict) else value
        if int(index) == 0 or not name:
            continue
        items.append({"value": int(index), "name": name,
                      "code": int(value.get("CommandCode") or 0) if isinstance(value, dict) else 0})
    return sorted(items, key=lambda o: o["value"])


def text_options(data):
    """{"serial": "product"} (mice) or ["profile", ...] -> options with text values."""
    if isinstance(data, dict):
        return sorted(({"value": k, "name": v} for k, v in data.items()), key=lambda o: o["name"].lower())
    return [{"value": v, "name": v} for v in sorted(data or [])]


def macro_list(data, names):
    """GET /api/macro/ -> macros sorted by id, each with its steps in order."""
    macros = []
    for macro_id, m in (data or {}).items():
        steps = []
        for index, a in sorted(((int(i), a) for i, a in (m.get("actions") or {}).items())):
            kind = int(a.get("actionType") or 0)
            command = int(a.get("actionCommand") or 0)
            steps.append({
                "index": index, "type": kind, "value": command,
                "valueName": (names.get(kind) or {}).get(command, ""),
                "delay": int(a.get("actionDelay") or 0), "text": a.get("actionText") or "",
                "pressAndHold": bool(a.get("actionHold")),
                "repeat": int(a.get("actionRepeat") or 0), "repeatDelay": int(a.get("actionRepeatDelay") or 0),
                "x": int(a.get("mousePositionX") or 0), "y": int(a.get("mousePositionY") or 0),
                "absolute": bool(a.get("mousePositionAbsolute")),
            })
        macros.append({"id": int(m.get("id", macro_id)), "name": m.get("name") or "",
                       "repeat": int(m.get("repeat") or 0), "repeatDelay": int(m.get("repeatDelay") or 0),
                       "steps": steps, "gapsAllowed": bool(m.get("gapsAllowed"))})
    return sorted(macros, key=lambda m: m["id"])


def assignment_body(serial, key_id, form):
    """POST /api/keyboard/updateKeyAssignment, as openKeyAssignmentsWithModifier sends it."""
    kind = int(form.get("type") or 0)
    body = {
        "deviceId": serial, "keyIndex": int(key_id),
        "enabled": bool(form.get("enabled")), "pressAndHold": bool(form.get("pressAndHold")),
        "keyAssignmentOriginal": bool(form.get("retainOriginal")),
        "keyAssignmentModifier": int(form.get("modifier") or 0),
        "keyAssignmentType": kind,
    }
    if kind in STRING_TYPES:
        body["keyAssignmentValueString"] = str(form.get("value") or "")
    else:
        body["keyAssignmentValue"] = int(form.get("value") or 0)
    body["toggleDelay"] = int(form.get("toggleDelay") or 0)
    return body


def macro_step_body(macro_id, form):
    """POST /api/macro/newValue, with the same fields as #addMacroValue in macros.js."""
    kind = int(form.get("type") or 0)
    position = kind == MACRO_POSITION
    return {
        "macroId": int(macro_id), "macroType": kind,
        "macroValue": int(form.get("value") or 0), "macroDelay": int(form.get("delay") or 0),
        "macroText": str(form.get("text") or ""),
        "mousePositionX": int(form.get("x") or 0) if position else 0,
        "mousePositionY": int(form.get("y") or 0) if position else 0,
        "mousePositionAbsolute": bool(form.get("absolute")) if position else False,
    }


def macro_step_problem(form):
    """The checks macros.js does before adding a step; None when the step is fine."""
    kind = int(form.get("type") or 0)
    if kind not in MACRO_STEP_TYPES:
        return N_("Choose what the step does")
    if kind in (MACRO_KEY, MACRO_MOUSE) and int(form.get("value") or 0) == 0:
        return N_("Choose a key")
    if kind == MACRO_DELAY and int(form.get("delay") or 0) < 1:
        return N_("A delay needs at least 1 ms")
    if kind == MACRO_TEXT and not str(form.get("text") or ""):
        return N_("Type the text")
    return None


def recorded_steps(events, keys, with_delays=True):
    """Key presses recorded in the window -> macro steps.

    events: [{"code": xkb key code, "time": ms}], keys: key_list of /api/input/keyboard.
    Returns (steps, skipped): keyboard steps, with a delay step for the pause
    between two presses, and the number of keys OpenLinkHub doesn't know.
    """
    by_code = {}
    for k in keys:
        by_code.setdefault(k["code"], k["value"])
    steps, skipped, last = [], 0, None
    for e in events:
        index = by_code.get(int(e.get("code") or 0) - XKB_OFFSET)
        if index is None:
            skipped += 1
            continue
        time = int(e.get("time") or 0)
        if with_delays and last is not None and time - last >= 1:
            steps.append({"type": MACRO_DELAY, "delay": min(time - last, 10000)})
        steps.append({"type": MACRO_KEY, "value": index})
        last = time
    return steps, skipped


def hex_to_rgb(color):
    text = str(color or "").lstrip("#")
    if len(text) != 6:
        return None
    try:
        return {"red": int(text[0:2], 16), "green": int(text[2:4], 16), "blue": int(text[4:6], 16)}
    except ValueError:
        return None


class Keyboard(QObject):
    """Key assignments, macros, performance and dial colours of the open keyboard."""
    dataChanged = Signal()
    macrosChanged = Signal()
    recordingSaved = Signal()
    # Asks the page to open a tab (and select a key), for screenshots
    tabRequested = Signal(str, int)

    def __init__(self, backend, parent=None):
        super().__init__(parent or backend)
        self.backend = backend
        self._serial = ""
        self._data = {}
        self._lists = {}
        self._macros = []
        self._raw_macros = {}
        backend.activeChanged.connect(self._active_changed)
        self.refreshMacros()

    @property
    def api(self):
        return self.backend.api

    # --- properties for QML ---

    @Property("QVariantList", notify=dataChanged)
    def assignmentTypes(self):
        return self._data.get("types", [])

    @Property("QVariantList", notify=dataChanged)
    def modifiers(self):
        return self._data.get("modifiers", [])

    @Property("QVariantMap", notify=dataChanged)
    def assignmentValues(self):
        """Choices for the value of a key assignment, by type ("1", "3", ...)."""
        lists = self._lists
        macros = [{"value": m["id"], "name": m["name"]} for m in self._macros]
        mice = lists.get("mice", [])
        return {"1": lists.get("media", []), "3": lists.get("keys", []), "9": lists.get("buttons", []),
                "10": macros, "2": mice, "4": mice, "8": mice, "21": lists.get("profiles", [])}

    @Property("QVariantList", notify=dataChanged)
    def performance(self):
        return self._data.get("performance", [])

    @Property("QVariantList", notify=dataChanged)
    def dialColors(self):
        return self._data.get("dialColors", [])

    @Property("QVariantList", notify=macrosChanged)
    def macros(self):
        return self._macros

    @Property("QVariantList", constant=True)
    def macroStepTypes(self):
        return [{"value": k, "name": self.tr(v)} for k, v in MACRO_STEP_TYPES.items()]

    @Property("QVariantMap", notify=dataChanged)
    def macroValues(self):
        return {"3": self._lists.get("keys", []), "9": self._lists.get("buttons", [])}

    @Slot(int, result=str)
    def macroTypeName(self, kind):
        return self.tr(MACRO_TYPE_NAMES.get(kind, "n/a"))

    # --- loading ---

    def _active_changed(self):
        active = self.backend.active
        serial = active.get("serial", "") if active.get("page") == "keyboard" else ""
        if serial == self._serial:
            return
        self._serial = serial
        self._data, self._lists = {}, {}
        self.dataChanged.emit()
        if serial:
            self.reload()

    @Slot()
    def reload(self):
        serial = self._serial
        if not serial:
            return
        self._get("/api/keyboard/assignmentsTypes/" + serial, serial, "types", lambda d: [
            {"value": int(k), "name": self.tr(ASSIGNMENT_TYPES[int(k)]) if int(k) in ASSIGNMENT_TYPES else v}
            for k, v in sorted((d or {}).items(), key=lambda kv: int(kv[0]))])
        self._get("/api/keyboard/assignmentsModifiers/" + serial, serial, "modifiers", lambda d: [
            {"value": int(k), "name": self.tr("None") if int(k) == 0 else v}
            for k, v in sorted((d or {}).items(), key=lambda kv: int(kv[0]))])
        self._get("/api/keyboard/getPerformance/" + serial, serial, "performance", lambda d: [
            {"internal": p.get("internal") or "", "value": bool(p.get("value")),
             "name": self.tr(PERFORMANCE[p["internal"]]) if p.get("internal") in PERFORMANCE else p.get("name") or ""}
            for p in (d or []) if p.get("type", "checkbox") == "checkbox"])
        self._get("/api/keyboard/dial/getColors/" + serial, serial, "dialColors", lambda d: [
            {"id": int(c.get("Id") or 0), "color": to_hex(c.get("Color")),
             "name": self.tr(DIAL_NAMES[int(c.get("Id") or 0)]) if int(c.get("Id") or 0) in DIAL_NAMES else c.get("Name") or ""}
            for c in (d or [])])
        self._get("/api/input/media", serial, "media", key_list, self._lists)
        self._get("/api/input/keyboard", serial, "keys", key_list, self._lists)
        self._get("/api/input/mouse", serial, "buttons", key_list, self._lists)
        self._get("/api/devices/mouse", serial, "mice", text_options, self._lists)
        self._get("/api/device/profiles/" + serial, serial, "profiles", text_options, self._lists)
        self.refreshMacros()

    def _get(self, path, serial, key, convert, target=None):
        def done(ok, data, error):
            if serial != self._serial or not ok:
                return
            (self._data if target is None else target)[key] = convert(data.get("data"))
            if target is self._lists:
                self._macros = macro_list(self._raw_macros, self._names())
                self.macrosChanged.emit()
            self.dataChanged.emit()
        self.api.get(path, done)

    def _names(self):
        """Value names for macro steps: {type: {value: name}}."""
        lists = self._lists
        return {MACRO_KEY: {o["value"]: o["name"] for o in lists.get("keys", [])},
                MACRO_MOUSE: {o["value"]: o["name"] for o in lists.get("buttons", [])},
                MACRO_MEDIA: {o["value"]: o["name"] for o in lists.get("media", [])}}

    @Slot()
    def refreshMacros(self):
        def done(ok, data, error):
            if ok:
                self._raw_macros = data.get("data") or {}
                self._macros = macro_list(self._raw_macros, self._names())
                self.macrosChanged.emit()
                self.dataChanged.emit()
        self.api.get("/api/macro/", done)

    def _send(self, method, path, body, then=None):
        def done(ok, data, error):
            message = (data or {}).get("message") or error or (self.tr("Done") if ok else self.tr("Failed"))
            self.backend.notify.emit(str(message), ok)
            if then:
                then(ok)
        getattr(self.api, method)(path, body, done)

    def _problem(self, text):
        self.backend.notify.emit(self.tr(text), False)

    # --- key assignments ---

    @Slot(int, "QVariantMap")
    def setKeyAssignment(self, key_id, form):
        if not self._serial:
            return
        self._send("post", "/api/keyboard/updateKeyAssignment", assignment_body(self._serial, key_id, form),
                   lambda ok: self.backend.reloadActive())

    # --- performance and dial colours ---

    @Slot("QVariantMap")
    def setPerformance(self, values):
        if not self._serial:
            return
        body = {"deviceId": self._serial}
        for p in self.performance:
            body[p["internal"]] = bool(values.get(p["internal"], p["value"]))
        self._send("post", "/api/keyboard/setPerformance", body, lambda ok: self.reload())

    @Slot("QVariantMap")
    def setDialColors(self, colors):
        if not self._serial:
            return
        zones = {}
        for c in self.dialColors:
            rgb = hex_to_rgb(colors.get(str(c["id"]), c["color"]))
            if rgb:
                zones[str(c["id"])] = rgb
        self._send("post", "/api/keyboard/dial/setColors", {"deviceId": self._serial, "colorZones": zones},
                   lambda ok: self.reload())

    # --- macros ---

    @Slot(str)
    def newMacro(self, name):
        name = name.strip()
        if len(name) < 3:
            self._problem(N_("A macro name needs at least 3 characters"))
            return
        if not name.isascii() or not name.isalnum():
            self._problem(N_("Use only letters and digits"))
            return
        self._send("put", "/api/macro/new", {"macroName": name}, lambda ok: self.refreshMacros())

    @Slot(int)
    def deleteMacro(self, macro_id):
        self._send("delete", "/api/macro/profile", {"macroId": int(macro_id)}, lambda ok: self.refreshMacros())

    @Slot(int, bool, int, int)
    def setMacroSettings(self, macro_id, loop, repeat, delay):
        if (not loop and repeat < 0) or delay < 0:
            self._problem(N_("Repeat and delay can't be negative"))
            return
        self._send("post", "/api/macro/updateSettings", {
            "macroId": int(macro_id), "macroRepeat": -1 if loop else int(repeat), "macroRepeatDelay": int(delay)},
            lambda ok: self.refreshMacros())

    @Slot(int, "QVariantMap")
    def addMacroStep(self, macro_id, form):
        problem = macro_step_problem(form)
        if problem:
            self._problem(problem)
            return
        self._send("post", "/api/macro/newValue", macro_step_body(macro_id, form), lambda ok: self.refreshMacros())

    @Slot(int, int, "QVariantMap")
    def updateMacroStep(self, macro_id, index, form):
        self._send("post", "/api/macro/updateValue", {
            "macroId": int(macro_id), "macroIndex": int(index),
            "pressAndHold": bool(form.get("pressAndHold")),
            "actionRepeatValue": int(form.get("repeat") or 0),
            "actionRepeatDelay": int(form.get("repeatDelay") or 0),
            "mousePositionX": int(form.get("x") or 0), "mousePositionY": int(form.get("y") or 0),
            "mousePositionAbsolute": bool(form.get("absolute")),
        }, lambda ok: self.refreshMacros())

    @Slot(int, int)
    def deleteMacroStep(self, macro_id, index):
        self._send("delete", "/api/macro/value", {"macroId": int(macro_id), "macroIndex": int(index)},
                   lambda ok: self.refreshMacros())

    @Slot(int, "QVariantList", bool)
    def saveRecording(self, macro_id, events, with_delays):
        """Adds recorded key presses to a macro, one request after the other so the order stays."""
        steps, skipped = recorded_steps(events, self._lists.get("keys", []), with_delays)
        if not steps:
            self._problem(N_("Nothing recorded"))
            return
        pending = list(steps)

        def next_step(ok=True):
            if not ok or not pending:
                self.refreshMacros()
                if ok:
                    text = self.tr("%1 steps added").replace("%1", str(len(steps)))
                    if skipped:
                        text += " · " + self.tr("%1 keys skipped").replace("%1", str(skipped))
                    self.backend.notify.emit(text, True)
                    self.recordingSaved.emit()
                return

            def done(ok, data, error):
                if not ok:
                    self.backend.notify.emit(str((data or {}).get("message") or error), False)
                next_step(ok)
            self.api.post("/api/macro/newValue", macro_step_body(macro_id, pending.pop(0)), done)
        next_step()
