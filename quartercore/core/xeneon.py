# XENEON EDGE screen settings: brightness, contrast, backlight and colour tones
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/devices/xeneonedge/xeneonedge.go).
# Every setting is one 65-byte report: 01 0f, the setting at byte 7-8 and the
# value at byte 9; the screen answers with one report. On start the saved
# values are sent (like Init), on stop the values OpenLinkHub sends when it
# stops (setScreenToDefault with Exit set).

import threading
from pathlib import Path

from . import hid

VENDOR, PRODUCT = 0x1B1C, 0x1D0D      # 7437 in OpenLinkHub's device list

BACKLIGHT, CONTRAST, BRIGHTNESS = (0x02, 0x00), (0x02, 0x01), (0x02, 0x02)
COLOR_TONES = ((0x03, 0x01), (0x03, 0x02), (0x03, 0x03))   # red, green, blue
# Default colour tones (dataTypeRed, -Green, -Blue)
TONE_DEFAULTS = (150, 126, 140)
DEFAULTS = {"Brightness": 50, "Contrast": 50, "Backlight": 100,
            "ColorToneRed": TONE_DEFAULTS[0], "ColorToneGreen": TONE_DEFAULTS[1], "ColorToneBlue": TONE_DEFAULTS[2]}
# What OpenLinkHub sends when it stops (the Exit branch of each setter)
ON_STOP = {"Brightness": 50, "Contrast": 100, "Backlight": 50,
           "ColorToneRed": TONE_DEFAULTS[0], "ColorToneGreen": TONE_DEFAULTS[1], "ColorToneBlue": TONE_DEFAULTS[2]}
TONE_NAMES = ("ColorToneRed", "ColorToneGreen", "ColorToneBlue")


def packet(setting, value):
    buf = bytearray(65)
    buf[1], buf[2] = 0x01, 0x0F
    buf[7], buf[8] = setting
    buf[9] = value & 0xFF
    return bytes(buf)


def packets(settings):
    """The reports that set every value, in OpenLinkHub's order (Init)."""
    out = [packet(BRIGHTNESS, settings["Brightness"]), packet(CONTRAST, settings["Contrast"]),
           packet(BACKLIGHT, settings["Backlight"])]
    out += [packet(COLOR_TONES[i], settings[name]) for i, name in enumerate(TONE_NAMES)]
    return out


def usb_serial(usb):
    """The USB serial number, which OpenLinkHub uses as the device id."""
    try:
        return Path("/sys" + usb, "serial").read_text().strip()
    except OSError:
        return ""


class XeneonEdge:
    def __init__(self, info, store, opener=hid.HidDevice, serial=None):
        self.info = info
        self.store = store
        self.opener = opener
        self.product = "XENEON EDGE"
        self.serial = serial or usb_serial(info["usbPath"]) or hid.serial_for(info["usbPath"])
        self.lock = threading.Lock()
        self.device = None
        self.settings = store.load(self.serial, DEFAULTS)
        self.error = ""

    def _hid(self):
        if self.device is None:
            self.device = self.opener(self.info["node"])
        return self.device

    def _send(self, buffers):
        """transfer(): write a report and read one back."""
        try:
            with self.lock:
                device = self._hid()
                for buf in buffers:
                    device.write(buf)
                    device.read(1.0)
            self.error = ""
            return ""
        except OSError as e:
            self.error = str(e)
            return "Unable to change the screen: %s" % e

    def start(self):
        self._send(packets(self.settings))

    def refresh(self):
        pass

    def stop(self):
        self._send(packets(ON_STOP))
        if self.device is not None:
            self.device.close()
            self.device = None

    def _set(self, changes):
        error = self._send([packet(self._setting(name), value) for name, value in changes.items()])
        if not error:
            self.settings.update(changes)
            self.store.save(self.serial, self.settings)
        return error

    @staticmethod
    def _setting(name):
        if name in TONE_NAMES:
            return COLOR_TONES[TONE_NAMES.index(name)]
        return {"Brightness": BRIGHTNESS, "Contrast": CONTRAST, "Backlight": BACKLIGHT}[name]

    def set_value(self, name, value):
        """Brightness and contrast 0-100, backlight 0-100 (the web page's slider)."""
        if not isinstance(value, int) or not 0 <= value <= 100:
            return "Invalid value"
        return self._set({name: value})

    def set_tone(self, kind, value):
        """Colour tone 0-255 for red (0), green (1) or blue (2)."""
        if kind not in (0, 1, 2) or not isinstance(value, int) or not 0 <= value <= 255:
            return "Invalid colour tone"
        return self._set({TONE_NAMES[kind]: value})

    def reset(self):
        """ResetDeviceSettings: the defaults (contrast and brightness 50, backlight 100)."""
        return self._set(dict(DEFAULTS))

    # --- API ---

    def summary(self):
        return {"Product": self.product, "Serial": self.serial, "Template": "xeneonedge.html"}

    def device_json(self):
        return {"serial": self.serial, "product": self.product, "firmware": "n/a", "Template": "xeneonedge.html",
                "DeviceProfile": dict(self.settings, Serial=self.serial, Active=True),
                "userProfiles": {"default": {"Active": True}},
                "DrivenBy": "quartercore-core", "Error": self.error}

    def handle(self, path, body):
        """POST requests of the web page (overview.js); None when this isn't one of them."""
        def number(key):
            try:
                return int(body.get(key))
            except (TypeError, ValueError):
                return -1
        if path == "/api/brightness/gradual":
            return self.set_value("Brightness", number("brightness"))
        if path == "/api/contrast/gradual":
            return self.set_value("Contrast", number("contrast"))
        if path == "/api/backlight/gradual":
            return self.set_value("Backlight", number("backlight"))
        if path == "/api/colortone":
            return self.set_tone(number("colorToneType"), number("colorTone"))
        if path == "/api/resetSettings":
            return self.reset()
        return None


def discover(store, root=hid.SYS_HIDRAW, opener=hid.HidDevice):
    return [XeneonEdge(info, store, opener) for info in hid.find(VENDOR, {PRODUCT}, root)
            if info["interface"] in (0, -1)]
