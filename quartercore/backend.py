# Bridge between the OpenLinkHub API and the QML interface
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Polls OpenLinkHub and exposes plain lists and maps to QML. Device pages call
# the slots below; they send the same requests as the OpenLinkHub web UI.

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from .api import ApiClient
from .headset import TEMPLATES as HEADSET_TEMPLATES, headset_view
from .keyboard import is_keyboard, keyboard_view

SYSTEM_INTERVAL_MS = 2000
DEVICE_LIST_INTERVAL_MS = 15000

# Device pages built into this app, by the OpenLinkHub web template they replace
NATIVE_TEMPLATES = dict({"lsh.html": "linkhub", "psuhid.html": "psu"}, **{t: "headset" for t in HEADSET_TEMPLATES})
NO_LABEL = "Set Label"


def channel_sort_key(channel):
    try:
        return int(channel["channelId"])
    except (TypeError, ValueError):
        return 0


def link_hub_view(device):
    """The LINK System Hub fields the page shows."""
    profile = device.get("DeviceProfile") or {}
    channels = []
    for channel_id, ch in (device.get("devices") or {}).items():
        label = ch.get("label") or ""
        channels.append({
            "channelId": int(channel_id),
            "name": ch.get("name") or "",
            "label": "" if label == NO_LABEL else label,
            "kind": ch.get("description") or "",
            "rpm": ch.get("rpm") or 0,
            "temperature": ch.get("temperatureString") or "",
            "speedProfile": ch.get("profile") or "",
            "rgbProfile": ch.get("rgb") or "",
            "hasSpeed": bool(ch.get("HasSpeed")),
            "isProbe": bool(ch.get("IsTemperatureProbe")),
        })
    channels.sort(key=channel_sort_key)
    return {
        "serial": device.get("serial") or "",
        "product": device.get("product") or "",
        "firmware": device.get("firmware") or "",
        "brightness": int(profile.get("BrightnessSlider") or 0),
        "rgbModes": list(device.get("RGBModes") or []),
        "channels": channels,
    }


def number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def psu_view(device):
    """Power supply measurements grouped like the OpenLinkHub page, plus the fan mode."""
    profile = device.get("DeviceProfile") or {}
    modes = sorted(((int(k), v) for k, v in (device.get("FanModes") or {}).items()), key=lambda kv: kv[0])
    view = {
        "serial": device.get("serial") or "",
        "product": device.get("product") or "",
        "inputVoltage": number(device.get("InputVoltage")),
        "fanMode": int(profile.get("FanMode") or 0),
        "fanModes": [{"value": k, "name": v} for k, v in modes],
        "power": 0.0, "outputPower": 0.0, "fans": [], "temperatures": [], "rails": [],
    }
    channels = sorted((device.get("devices") or {}).values(), key=lambda c: int(c.get("channelId") or 0))
    for ch in channels:
        name = ch.get("name") or ch.get("label") or ""
        if ch.get("MainPSU"):
            view["power"] = number(ch.get("watts"))
        elif ch.get("HasSpeed"):
            view["fans"].append({"name": name, "rpm": int(number(ch.get("rpm")))})
        elif ch.get("HasTemps"):
            view["temperatures"].append({"name": name, "value": ch.get("temperatureString") or ""})
        elif ch.get("HasVolts"):
            view["rails"].append({"name": name, "volts": number(ch.get("volts")),
                                  "amps": number(ch.get("amps")), "watts": number(ch.get("watts"))})
        elif ch.get("HasWatts"):
            view["outputPower"] = number(ch.get("watts"))
    return view


def page_kind(device):
    """Which page shows this device: a native one, or "web" for the OpenLinkHub web interface."""
    kind = NATIVE_TEMPLATES.get(device.get("Template") or "")
    if kind:
        return kind
    return "keyboard" if is_keyboard(device) else "web"


class Backend(QObject):
    connectedChanged = Signal()
    systemChanged = Signal()
    devicesChanged = Signal()
    activeChanged = Signal()
    speedProfilesChanged = Signal()
    serverUrlChanged = Signal()
    # Feedback for the user: text, ok
    notify = Signal(str, bool)

    def __init__(self, base_url, parent=None):
        super().__init__(parent)
        self.api = ApiClient(base_url, self)
        self.base_url = self.api.base_url
        self._connected = False
        self._error = ""
        self._system = {}
        self._devices = []
        self._pages = {}
        self._active_serial = ""
        self._active = {}
        self._speed_profiles = []

        self.system_timer = QTimer(self, interval=SYSTEM_INTERVAL_MS, timeout=self.refresh)
        self.devices_timer = QTimer(self, interval=DEVICE_LIST_INTERVAL_MS, timeout=self.refreshDevices)

    def start(self):
        self.refreshDevices()
        self.refreshSpeedProfiles()
        self.refresh()
        self.system_timer.start()
        self.devices_timer.start()

    # --- properties for QML ---

    @Property(bool, notify=connectedChanged)
    def connected(self):
        return self._connected

    @Property(str, notify=connectedChanged)
    def error(self):
        return self._error

    @Property("QVariantMap", notify=systemChanged)
    def system(self):
        return self._system

    @Property("QVariantList", notify=devicesChanged)
    def devices(self):
        return self._devices

    @Property("QVariantList", notify=devicesChanged)
    def hubs(self):
        """Devices with a native LINK Hub page (for the tray menu)."""
        return [d for d in self._devices if d["page"] == "linkhub"]

    @Property(str, notify=activeChanged)
    def activeSerial(self):
        return self._active_serial

    @Property("QVariantMap", notify=activeChanged)
    def active(self):
        return self._active

    @Property("QVariantList", notify=speedProfilesChanged)
    def speedProfiles(self):
        return self._speed_profiles

    @Property(str, notify=serverUrlChanged)
    def serverUrl(self):
        return self.base_url

    # --- polling ---

    def _set_connected(self, ok, error=""):
        if ok != self._connected or error != self._error:
            self._connected, self._error = ok, error
            self.connectedChanged.emit()

    @Slot()
    def refresh(self):
        self._get_system_value("cpuTemp", "cpuTemp")
        self._get_system_value("cpuLoad", "cpuLoad")
        self._get_system_value("gpuTemp", "gpuTemp")
        self._get_system_value("gpuLoad", "gpuLoad")
        self._get_system_value("stats/memory", "memory")
        self._get_system_value("storageTemp", "storage")
        if self._active_serial:
            self._load_active(self._active_serial)

    def _get_system_value(self, path, key):
        def done(ok, data, error):
            self._set_connected(ok or data is not None, "" if ok or data is not None else error)
            if ok:
                self._system = dict(self._system, **{key: data.get("data")})
                self.systemChanged.emit()
        self.api.get("/api/" + path, done)

    @Slot()
    def refreshDevices(self):
        def done(ok, data, error):
            if not ok:
                self._set_connected(False, error)
                return
            devices = []
            for serial, d in (data.get("devices") or {}).items():
                if d.get("Hidden"):
                    continue
                devices.append({"serial": serial, "product": d.get("Product") or serial})
            devices.sort(key=lambda d: d["product"].lower())
            for d in devices:
                if d["serial"] not in self._pages:
                    self._load_template(d["serial"])
            self._devices = [dict(d, page=self._page(d["serial"])) for d in devices]
            self.devicesChanged.emit()
        self.api.get("/api/devices/", done)

    def _page(self, serial):
        return self._pages.get(serial, "web")

    def _load_template(self, serial):
        def done(ok, data, error):
            if ok:
                self._pages[serial] = page_kind(data.get("device") or {})
                self._devices = [dict(d, page=self._page(d["serial"])) for d in self._devices]
                self.devicesChanged.emit()
        self.api.get("/api/devices/" + serial, done)

    @Slot()
    def refreshSpeedProfiles(self):
        def done(ok, data, error):
            if ok:
                profiles = data.get("data") or {}
                self._speed_profiles = sorted(k for k, v in profiles.items() if not v.get("Hidden"))
                self.speedProfilesChanged.emit()
        self.api.get("/api/temperatures/", done)

    # --- active device ---

    @Slot(str)
    def selectDevice(self, serial):
        if serial == self._active_serial:
            return
        self._active_serial = serial
        self._active = {}
        self.activeChanged.emit()
        if serial:
            self._load_active(serial)

    def _load_active(self, serial):
        def done(ok, data, error):
            if serial != self._active_serial:
                return
            if not ok:
                self.notify.emit(error, False)
                return
            device = data.get("device") or {}
            page = self._pages[serial] = page_kind(device)
            if page == "linkhub":
                view = link_hub_view(device)
            elif page == "psu":
                view = psu_view(device)
            elif page == "keyboard":
                view = keyboard_view(device)
            elif page == "headset":
                view = headset_view(device)
            else:
                view = {"serial": serial, "product": device.get("product") or serial}
            self._active = dict(view, page=page)
            self.activeChanged.emit()
        self.api.get("/api/devices/" + serial, done)

    @Slot()
    def reloadActive(self):
        if self._active_serial:
            self._load_active(self._active_serial)

    def _change(self, path, body, method="post"):
        """Sends a change, reports the result and reloads the active device."""
        serial = self._active_serial

        def done(ok, data, error):
            message = (data or {}).get("message") or error or (self.tr("Done") if ok else self.tr("Failed"))
            self.notify.emit(str(message), ok)
            if serial and serial == self._active_serial:
                self._load_active(serial)
        getattr(self.api, method)(path, body, done)

    @Slot(int, str)
    def setSpeedProfile(self, channel, profile):
        self._change("/api/speed", {"deviceId": self._active_serial, "channelId": channel, "profile": profile})

    @Slot(str)
    def setAllSpeedProfiles(self, profile):
        for ch in self._active.get("channels", []):
            if ch["hasSpeed"]:
                self.setSpeedProfile(ch["channelId"], profile)

    @Slot(str, str)
    def setHubSpeedProfile(self, serial, profile):
        """Speed profile for every fan and pump of a hub, also when it isn't the open page (tray menu)."""
        self._for_all_channels(serial, "/api/speed", profile, lambda ch: ch["hasSpeed"],
                               self.tr("Speed profile %1 set").replace("%1", profile))

    @Slot(str, str)
    def setHubRgbProfile(self, serial, profile):
        """RGB effect for every device on a hub (lighting page)."""
        self._for_all_channels(serial, "/api/color", profile, lambda ch: not ch["isProbe"],
                               self.tr("Effect %1 set").replace("%1", profile))

    def _for_all_channels(self, serial, path, profile, wanted, message):
        def done(ok, data, error):
            if not ok:
                self.notify.emit(error, False)
                return
            view = link_hub_view(data.get("device") or {})
            for ch in view["channels"]:
                if wanted(ch):
                    self.api.post(path, {"deviceId": serial, "channelId": ch["channelId"],
                                         "profile": profile}, report)
            self.notify.emit(message, True)

        def report(ok, data, error):
            if not ok:
                self.notify.emit(str((data or {}).get("message") or error), False)
            elif serial == self._active_serial:
                self._load_active(serial)
        self.api.get("/api/devices/" + serial, done)

    @Slot(int, str)
    def setRgbProfile(self, channel, profile):
        self._change("/api/color", {"deviceId": self._active_serial, "channelId": channel, "profile": profile})

    @Slot(str)
    def setAllRgbProfiles(self, profile):
        for ch in self._active.get("channels", []):
            if not ch["isProbe"]:
                self.setRgbProfile(ch["channelId"], profile)

    @Slot(int, str)
    def setLabel(self, channel, label):
        label = label.strip()
        if not label:
            self.notify.emit(self.tr("A label can't be empty"), False)
            return
        self._change("/api/label", {"deviceId": self._active_serial, "channelId": channel,
                                    "deviceType": 0, "label": label})

    @Slot(int)
    def setBrightness(self, value):
        self._change("/api/brightness/gradual", {"deviceId": self._active_serial,
                                                 "brightness": max(0, min(100, int(value)))})

    # --- keyboards ---

    def _keyboard(self, path, values, method="post"):
        self._change(path, dict({"deviceId": self._active_serial}, **values), method)

    @Slot(str)
    def setKeyboardRgbMode(self, mode):
        self._keyboard("/api/color", {"channelId": 0, "profile": mode})

    @Slot("QVariantList", str)
    def setKeyColors(self, key_ids, color):
        """Colour for the given keys; applies right away, saved with saveKeyboardColorProfile."""
        ids = [int(i) for i in key_ids]
        text = color.lstrip("#")
        if not ids or len(text) != 6:
            return
        rgb = {"red": int(text[0:2], 16), "green": int(text[2:4], 16), "blue": int(text[4:6], 16)}
        # keyOption 3 = the selected keys, like "Selected keys" in the web interface
        self._keyboard("/api/keyboard/color", {"keyId": ids[0], "keyOption": 3, "keys": ids, "color": rgb})

    @Slot(str)
    def setKeyboardColorProfile(self, name):
        self._keyboard("/api/keyboard/profile/change", {"keyboardProfileName": name})

    @Slot()
    def saveKeyboardColorProfile(self):
        self._keyboard("/api/keyboard/profile/save", {"keyboardProfileName": "0", "new": False})

    @Slot(str)
    def saveKeyboardColorProfileAs(self, name):
        name = name.strip()
        if not name:
            self.notify.emit(self.tr("Give the profile a name"), False)
            return
        self._keyboard("/api/keyboard/profile/new", {"keyboardProfileName": name, "new": True}, "put")

    @Slot(str)
    def deleteKeyboardColorProfile(self, name):
        self._keyboard("/api/keyboard/profile/delete", {"keyboardProfileName": name}, "delete")

    @Slot(str)
    def setUserProfile(self, name):
        self._keyboard("/api/userProfile/change", {"userProfileName": name})

    @Slot(str)
    def setKeyboardLayout(self, layout):
        self._keyboard("/api/keyboard/layout", {"keyboardLayout": layout})

    @Slot(int)
    def setKeyboardPollingRate(self, rate):
        self._keyboard("/api/keyboard/pollingRate", {"pollingRate": int(rate)})

    @Slot(int)
    def setKeyboardDial(self, option):
        self._keyboard("/api/keyboard/dial", {"keyboardControlDial": int(option)})

    @Slot(int)
    def setKeyboardDebounceTime(self, value):
        self._keyboard("/api/keyboard/debounceTime", {"debounceTime": int(value)})

    @Slot(int)
    def setPsuFanMode(self, mode):
        self._change("/api/psu/speed", {"deviceId": self._active_serial, "fanMode": int(mode)})

    @Slot(str)
    def setServerUrl(self, url):
        """Connects to another OpenLinkHub address (from the settings page)."""
        self.api.base_url = self.base_url = url.rstrip("/")
        self._pages.clear()
        self._devices, self._active_serial, self._active = [], "", {}
        self._set_connected(False, "")
        self.devicesChanged.emit()
        self.activeChanged.emit()
        self.serverUrlChanged.emit()
        self.refreshDevices()
        self.refreshSpeedProfiles()
        self.refresh()

    @Slot(str)
    def openInBrowser(self, serial):
        url = self.base_url + ("/device/" + serial if serial else "/")
        QDesktopServices.openUrl(QUrl(url))

    @Slot()
    def openXeneonEditor(self):
        QDesktopServices.openUrl(QUrl(self.base_url + "/xeneonLayout"))
