# Headsets (tested on the HS80 MAX WIRELESS): lighting, equalizer, sidetone, sleep, buttons
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Requests copied from upstream static/js/headset.js and overview.js (user
# profiles, brightness, RGB profile); the server checks are in
# src/server/requests/requests.go.

from PySide6.QtCore import Property, QObject, Signal, Slot

from .keyboard import hex_to_rgb, key_list, options, to_hex

TEMPLATES = {"hs80maxW.html"}
EQ_MIN, EQ_MAX = -12, 12


def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


# Names OpenLinkHub gives the sleep modes and switches, shown translated
SLEEP_NAMES = {0: N_("Off"), 1: N_("1 minute"), 5: N_("5 minutes"), 10: N_("10 minutes"),
               15: N_("15 minutes"), 30: N_("30 minutes"), 60: N_("1 hour")}
# Assignment types of the HS80 MAX WIRELESS (KeyAssignmentTypes)
BUTTON_TYPES = {0: N_("None"), 1: N_("Media keys"), 3: N_("Keyboard"), 9: N_("Mouse"),
                10: N_("Macro"), 11: N_("Profile switch")}


def sorted_ids(mapping):
    return sorted((int(k), v) for k, v in (mapping or {}).items())


def headset_view(device):
    profile = device.get("DeviceProfile") or {}
    user_profiles = device.get("userProfiles") or {}
    order = [p for p in device.get("profileOrder") or [] if p in user_profiles]
    order += sorted(p for p in user_profiles if p not in order)
    buttons = []
    for key_id, b in sorted_ids(device.get("KeyAssignment")):
        buttons.append({
            "keyId": key_id, "name": b.get("name") or "",
            "enabled": bool(b.get("default")), "pressAndHold": bool(b.get("actionHold")),
            "onRelease": bool(b.get("onRelease")), "type": int(b.get("actionType") or 0),
            "value": int(b.get("actionCommand") or 0),
        })
    return {
        "serial": device.get("serial") or "",
        "product": device.get("product") or "",
        "firmware": device.get("firmware") or "",
        "connected": bool(device.get("Connected")),
        "battery": int(device.get("BatteryLevel") or 0),
        "userProfile": next((k for k, v in user_profiles.items() if v.get("Active")), ""),
        "userProfiles": order,
        "brightness": int(profile.get("BrightnessSlider") or 0),
        "rgbModes": list(device.get("RGBModes") or []),
        "rgbMode": profile.get("RGBProfile") or "",
        "zones": [{"id": k, "name": z.get("Name") or "", "color": to_hex(z.get("Color"))}
                  for k, z in sorted_ids(profile.get("ZoneColors"))],
        "sleepModes": [{"value": o["value"], "name": SLEEP_NAMES.get(o["value"], o["name"])}
                       for o in options(device.get("SleepModes"))],
        "sleepMode": int(profile.get("SleepMode") or 0),
        "hasMicLed": bool(device.get("MuteIndicators")),
        "micLedOff": bool(profile.get("DisableMicIndicator")),
        "hasSidetone": bool(device.get("SideToneModes")),
        "sidetone": bool(profile.get("SideTone")),
        "sidetoneValue": int(profile.get("SideToneValue") or 0),
        "equalizer": [{"id": k, "name": e.get("Name") or "", "value": int(round(float(e.get("Value") or 0)))}
                      for k, e in sorted_ids(profile.get("Equalizers"))],
        "buttons": buttons,
        "buttonTypes": [{"value": k, "name": BUTTON_TYPES.get(k, v)}
                        for k, v in sorted_ids(device.get("KeyAssignmentTypes"))],
    }


def button_body(serial, key_id, form):
    """POST /api/headset/updateKeyAssignment, as .saveKeyAssignment in headset.js sends it."""
    return {
        "deviceId": serial, "keyIndex": int(key_id),
        "enabled": bool(form.get("enabled")), "pressAndHold": bool(form.get("pressAndHold")),
        "keyAssignmentType": int(form.get("type") or 0),
        "keyAssignmentValue": int(form.get("value") or 0),
        "onRelease": bool(form.get("onRelease")),
    }


def equalizer_body(serial, bands):
    """POST /api/headset/equalizer: all ten bands, clamped to -12..12 like the sliders."""
    return {"deviceId": serial,
            "equalizers": {str(int(k)): max(EQ_MIN, min(EQ_MAX, int(v))) for k, v in bands.items()}}


class Headset(QObject):
    """Changes for the open headset page; the data comes from backend.active."""
    valuesChanged = Signal()

    def __init__(self, backend, parent=None):
        super().__init__(parent or backend)
        self.backend = backend
        self._loaded_for = ""
        self._values = {}
        backend.activeChanged.connect(self._active_changed)

    @Property("QVariantMap", notify=valuesChanged)
    def buttonValues(self):
        """Choices for a button assignment by type: media keys, keys, mouse buttons, macros."""
        return self._values

    def _active_changed(self):
        serial = self.serial
        if serial == self._loaded_for:
            return
        self._loaded_for = serial
        self._values = {}
        self.valuesChanged.emit()
        if not serial:
            return
        for kind, path in (("1", "/api/input/media"), ("3", "/api/input/keyboard"), ("9", "/api/input/mouse")):
            self.backend.api.get(path, self._store(kind, serial, key_list))
        self.backend.api.get("/api/macro/", self._store("10", serial, lambda d: [
            {"value": int(m.get("id", k)), "name": m.get("name") or ""}
            for k, m in sorted((d or {}).items(), key=lambda kv: int(kv[0]))]))

    def _store(self, kind, serial, convert):
        def done(ok, data, error):
            if ok and serial == self._loaded_for:
                self._values = dict(self._values, **{kind: convert(data.get("data"))})
                self.valuesChanged.emit()
        return done

    @property
    def serial(self):
        active = self.backend.active
        return active.get("serial", "") if active.get("page") == "headset" else ""

    def _send(self, path, body, method="post"):
        if self.serial:
            self.backend._change(path, dict({"deviceId": self.serial}, **body), method)

    def _problem(self, text):
        self.backend.notify.emit(self.tr(text), False)

    @Slot(str)
    def setRgbMode(self, mode):
        # The web page sends channel 0 with the profile (value "0;<mode>")
        self._send("/api/color", {"channelId": 0, "profile": mode})

    @Slot(int)
    def setBrightness(self, value):
        self._send("/api/brightness/gradual", {"brightness": max(0, min(100, int(value)))})

    @Slot("QVariantMap")
    def setZoneColors(self, colors):
        zones = {}
        for z in self.backend.active.get("zones", []):
            rgb = hex_to_rgb(colors.get(str(z["id"]), z["color"]))
            if rgb:
                zones[str(z["id"])] = rgb
        self._send("/api/headset/zoneColors", {"colorZones": zones})

    @Slot(int)
    def setSleepMode(self, minutes):
        self._send("/api/headset/sleep", {"sleepMode": int(minutes)})

    @Slot(bool)
    def setMicLedOff(self, off):
        self._send("/api/headset/muteIndicator", {"muteIndicator": 1 if off else 0})

    @Slot(bool)
    def setSidetone(self, on):
        self._send("/api/headset/sidetone", {"sideTone": 1 if on else 0})

    @Slot(int)
    def setSidetoneValue(self, value):
        if not 0 <= value <= 100:
            self._problem(N_("Sidetone goes from 0 to 100 %"))
            return
        self._send("/api/headset/sidetoneValue", {"sideToneValue": int(value)})

    @Slot("QVariantMap")
    def setEqualizer(self, bands):
        current = {str(b["id"]): b["value"] for b in self.backend.active.get("equalizer", [])}
        current.update({str(k): v for k, v in bands.items()})
        if self.serial:
            self.backend._change("/api/headset/equalizer", equalizer_body(self.serial, current))

    @Slot()
    def resetEqualizer(self):
        self.setEqualizer({str(b["id"]): 0 for b in self.backend.active.get("equalizer", [])})

    @Slot(int, "QVariantMap")
    def setButton(self, key_id, form):
        if form.get("onRelease") and form.get("pressAndHold"):
            self._problem(N_("Press and hold doesn't work together with \"on release\""))
            return
        if self.serial:
            self.backend._change("/api/headset/updateKeyAssignment", button_body(self.serial, key_id, form))

    # --- user profiles ---

    @Slot(str)
    def setUserProfile(self, name):
        self._send("/api/userProfile/change", {"userProfileName": name})

    @Slot(str)
    def saveUserProfile(self, name):
        name = name.strip()
        if len(name) < 3:
            self._problem(N_("A profile name needs at least 3 characters"))
            return
        if not name.isascii() or not name.isalnum():
            self._problem(N_("Use only letters and digits"))
            return
        self._send("/api/userProfile", {"userProfileName": name}, "put")

    @Slot(str)
    def deleteUserProfile(self, name):
        if name == "default":
            self._problem(N_("The default profile can't be deleted"))
            return
        self._send("/api/userProfile/delete", {"userProfileName": name}, "delete")
