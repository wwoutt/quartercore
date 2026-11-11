# Home Assistant for the XENEON EDGE widgets: entity states and a tap to switch them
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
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


def tile(entity_id, state):
    """What a tile shows for one entity; state is Home Assistant's state object or None."""
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
