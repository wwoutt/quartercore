# Home Assistant for the XENEON EDGE widgets: entity states and a tap to switch them
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
# Modified by wwoutt, 2026-11-11: per tile a status entity and own rules (state -> colour and text)
#
# Uses Home Assistant's REST API (GET /api/states, POST /api/services/<domain>/<service>)
# with a long-lived access token the user makes in their Home Assistant profile.
# The address and the token are Quartercore settings; they only go to that address.
# Locks and alarm panels can't be switched from the kiosk, on purpose.

import json

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

TIMEOUT_MS = 8000
TOGGLE = {"light", "switch", "input_boolean", "fan", "automation", "siren", "humidifier"}
# domain -> (service domain, service); None: decided by the state
ACTIONS = {"cover": ("cover", "toggle"), "script": ("script", "turn_on"), "scene": ("scene", "turn_on"),
           "button": ("button", "press"), "input_button": ("input_button", "press"),
           "media_player": ("media_player", "media_play_pause")}
ON_STATES = {"on", "open", "opening", "playing", "home", "unlocked"}


def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


# Home Assistant's own state words, shown translated (other states, like numbers, as they are)
STATE_NAMES = {"on": N_("on"), "off": N_("off"), "open": N_("open"), "closed": N_("closed"),
               "opening": N_("opening"), "closing": N_("closing"), "locked": N_("locked"),
               "unlocked": N_("unlocked"), "home": N_("home"), "not_home": N_("away"), "playing": N_("playing"),
               "paused": N_("paused"), "idle": N_("idle"), "unavailable": N_("unavailable"),
               "unknown": N_("unknown")}


# The usual states per kind of entity, as suggestions for the rules
STATE_OPTIONS = {
    "binary_sensor": ["on", "off"], "light": ["on", "off"], "switch": ["on", "off"],
    "input_boolean": ["on", "off"], "fan": ["on", "off"], "automation": ["on", "off"],
    "cover": ["open", "closed", "opening", "closing"], "lock": ["locked", "unlocked", "jammed"],
    "person": ["home", "not_home"], "device_tracker": ["home", "not_home"],
    "media_player": ["playing", "paused", "idle", "off"],
    "alarm_control_panel": ["disarmed", "armed_home", "armed_away", "armed_night", "triggered"],
    "sun": ["above_horizon", "below_horizon"], "sensor": ["> 0", "< 0"],
}


def domain(entity_id):
    return str(entity_id).split(".", 1)[0]


def action(entity_id):
    """(service domain, service) a tap calls, or None when the entity can't be switched from here."""
    d = domain(entity_id)
    if d in TOGGLE:
        return "homeassistant", "toggle"
    return ACTIONS.get(d)


def entity_list(text):
    """"light.desk, sensor.temp" -> ["light.desk", "sensor.temp"] (also one per line)."""
    out = []
    for part in str(text or "").replace("\n", ",").split(","):
        part = part.strip()
        if part and "." in part and part not in out:
            out.append(part)
    return out


def tile_specs(text):
    """The tiles of a Home Assistant widget, from its "entities" setting:
    [{"entity": "button.garage", "status": "binary_sensor.door", "rules": [{"state": "on",
    "color": "#f59e0b", "text": "Open"}]}, ...]. The setting is that list as JSON, or (older,
    and simple lists) "light.desk, sensor.temp" with "a > b" for a status entity."""
    text = str(text or "").strip()
    raw = []
    if text.startswith("["):
        try:
            raw = [t for t in json.loads(text) if isinstance(t, dict)]
        except ValueError:
            raw = []
    else:
        for part in text.replace("\n", ",").split(","):
            entity, _, status = (p.strip() for p in part.partition(">"))
            raw.append({"entity": entity, "status": status})
    out = []
    for t in raw:
        entity = str(t.get("entity") or "").strip()
        status = str(t.get("status") or "").strip()
        if not entity or "." not in entity or entity in [o["entity"] for o in out]:
            continue
        rules = [{"state": str(r.get("state", "")).strip(), "color": str(r.get("color") or ""),
                  "text": str(r.get("text") or "")}
                 for r in (t.get("rules") or []) if isinstance(r, dict) and str(r.get("state", "")).strip()]
        out.append({"entity": entity, "status": status if "." in status else "", "rules": rules})
    return out


def _number(text):
    try:
        return float(str(text).replace(",", "."))
    except ValueError:
        return None


def matches(rule_state, value):
    """Whether a rule's state fits a state: "on" (the same, any case), or for numbers
    "> 25", ">= 25", "< 10", "<= 10"."""
    rule_state = str(rule_state).strip()
    for op in (">=", "<=", ">", "<"):
        if rule_state.startswith(op):
            limit, number = _number(rule_state[len(op):].strip()), _number(value)
            if limit is None or number is None:
                return False
            return {">=": number >= limit, "<=": number <= limit, ">": number > limit, "<": number < limit}[op]
    return rule_state.lower() == str(value).strip().lower()


def tile(entity_id, state, status_id="", status_state=None, rules=()):
    """What a tile shows for one entity; state is Home Assistant's state object or None.
    With a status entity the tile shows that entity's state (a door open or closed), while
    a tap still switches entity_id. The first rule whose state fits the shown state gives
    the tile its colour, and its text instead of the state."""
    shown = _tile(entity_id, state)
    source = state
    if status_id:
        status = _tile(status_id, status_state)
        shown.update(state=status["state"], translate=status.get("translate", False), unit=status["unit"],
                     on=status["on"], statusEntity=status_id)
        source = status_state
    if source:
        value = str(source.get("state", ""))
        for rule in rules or ():
            if matches(rule.get("state", ""), value):
                if rule.get("color"):
                    shown["color"] = rule["color"]
                if rule.get("text"):
                    shown.update(state=rule["text"], translate=False, unit="")
                break
    return shown


def _tile(entity_id, state):
    if not state:
        return {"entity": entity_id, "name": entity_id, "state": "–", "unit": "", "on": False,
                "available": False, "actionable": False}
    attributes = state.get("attributes") or {}
    value = str(state.get("state", ""))
    return {"entity": entity_id, "name": attributes.get("friendly_name") or entity_id,
            "state": STATE_NAMES.get(value, value), "translate": value in STATE_NAMES,
            "unit": attributes.get("unit_of_measurement") or "", "on": value in ON_STATES,
            "available": value not in ("unavailable", "unknown"), "actionable": action(entity_id) is not None,
            "domain": domain(entity_id)}


class HomeAssistant(QObject):
    """Polls the states when asked (the kiosk does that every few seconds) and calls services."""
    statesChanged = Signal()
    statusChanged = Signal()
    testChanged = Signal()

    def __init__(self, settings, parent=None, manager=None):
        super().__init__(parent)
        self.settings = settings
        self.manager = manager or QNetworkAccessManager(self)
        self._states = {}
        self._status = ""
        self._test = ""
        self._busy = False

    @property
    def configured(self):
        return bool(self.settings.haUrl.strip() and self.settings.haToken.strip())

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(str, notify=testChanged)
    def testResult(self):
        return self._test

    def _set_test(self, text):
        self._test = text
        self.testChanged.emit()

    def _set_status(self, text):
        if text != self._status:
            self._status = text
            self.statusChanged.emit()

    def state(self, entity_id):
        return self._states.get(entity_id)

    @Slot(str, result=str)
    def name(self, entity_id):
        """The friendly name of an entity, for the layout editor."""
        s = self._states.get(entity_id) or {}
        return (s.get("attributes") or {}).get("friendly_name") or entity_id

    @Slot(str, result="QStringList")
    def stateOptions(self, entity_id):
        """States an entity can have, for the rules in the layout editor: its own list
        (options, hvac_modes) or the usual ones of its kind, and the state it has now."""
        s = self._states.get(entity_id) or {}
        attributes = s.get("attributes") or {}
        options = list(attributes.get("options") or attributes.get("hvac_modes") or [])
        options += STATE_OPTIONS.get(domain(entity_id), [])
        if s.get("state") not in (None, ""):
            options.insert(0, str(s["state"]))
        return list(dict.fromkeys(str(o) for o in options))

    def _request(self, path):
        request = QNetworkRequest(QUrl(self.settings.haUrl.strip().rstrip("/") + path))
        request.setRawHeader(b"Authorization", b"Bearer " + self.settings.haToken.strip().encode())
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        request.setTransferTimeout(TIMEOUT_MS)
        return request

    def _finish(self, reply, done):
        error = ""
        data = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            error = self.tr("Home Assistant refused the token") if code == 401 else reply.errorString()
        else:
            try:
                data = json.loads(bytes(reply.readAll()).decode() or "null")
            except ValueError:
                error = self.tr("Home Assistant gave an answer that isn't JSON")
        reply.deleteLater()
        done(data, error)

    @Slot()
    def refresh(self):
        """GET /api/states: all states in one request."""
        if not self.configured:
            self._set_status(self.tr("Set the Home Assistant address and token in the settings"))
            return
        if self._busy:
            return
        self._busy = True
        reply = self.manager.get(self._request("/api/states"))

        def done(data, error):
            self._busy = False
            if error:
                self._set_status(error)
                return
            self._states = {s.get("entity_id"): s for s in data or [] if isinstance(s, dict)}
            self._set_status("")
            self.statesChanged.emit()
        reply.finished.connect(lambda: self._finish(reply, done))

    @Slot(str)
    def activate(self, entity_id):
        """A tap on a tile: toggle, press or start, then read the states again."""
        service = action(entity_id)
        if service is None or not self.configured:
            return
        body = json.dumps({"entity_id": entity_id}).encode()
        reply = self.manager.post(self._request("/api/services/%s/%s" % service), body)

        def done(data, error):
            if error:
                self._set_status(error)
            self.refresh()
        reply.finished.connect(lambda: self._finish(reply, done))

    @Slot(result="QVariantList")
    def entities(self):
        """Every known entity for the editor: [{"value": id, "name": "Friendly name (id)"}]."""
        rows = []
        for entity_id, s in sorted(self._states.items()):
            name = (s.get("attributes") or {}).get("friendly_name") or entity_id
            rows.append({"value": entity_id, "name": "%s (%s)" % (name, entity_id)})
        return rows

    @Slot()
    def test(self):
        """Settings page: check the address and token."""
        if not self.configured:
            self._set_test(self.tr("Fill in the address and the token first"))
            return
        self._set_test(self.tr("Connecting…"))
        reply = self.manager.get(self._request("/api/"))

        def done(data, error):
            self._set_test(error or self.tr("Connected to Home Assistant"))
            if not error:
                self.refresh()
        reply.finished.connect(lambda: self._finish(reply, done))
