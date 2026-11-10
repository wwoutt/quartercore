# HS80 MAX WIRELESS headset and its USB dongle
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/devices/hs80maxdongle and
# src/devices/hs80maxW). The dongle passes 65-byte reports on: byte 1 is 0x02,
# byte 2 the endpoint (0x08 the dongle, 0x09 the headset), then the command.
# The dongle and headset go to software mode on start and back to hardware
# mode on stop. Events (battery, button, mute, headset on/off) arrive on the
# same interface; a second handle listens for them, like upstream.
#
# Differences with upstream, on purpose:
# - the sleep timer can be set to "Off" (upstream saves 15 minutes instead);
# - the CPU and GPU temperature effects get real temperatures (upstream 0);
# - the equalizer is saved but not applied: OpenLinkHub applies it with its own
#   audio module only, which is off by default;
# - the mic mute only changes the mic LED; upstream also toggles the default
#   PulseAudio source, which a system service can't reach;
# - the button does "Profile switch"; media keys, keys, mouse buttons and
#   macros need uinput and come with step E of the roadmap.

import copy
import json
import re
import struct
import threading
import time

from . import hid, rgb, temperatures
from .xeneon import usb_serial

VENDOR = 0x1B1C
# Dongle product id -> (interface, headset product id, fixed headset serial or None)
DONGLES = {0x0A97: (4, 2710, None), 10767: (4, 10766, "10766"), 10764: (3, 10763, "10763")}

DONGLE, HEADSET = 0x08, 0x09
SOFTWARE_MODE = (0x01, 0x03, 0x00, 0x02)
HARDWARE_MODE = (0x01, 0x03, 0x00, 0x01)
HEARTBEAT = (0x12,)
GET_FIRMWARE = (0x02, 0x13)
WRITE_COLOR = (0x06, 0x00)
OPEN_COLOR_ENDPOINT = (0x0D, 0x00, 0x22)
OPEN_SLEEP_ENDPOINT = (0x01, 0x0D, 0x00)
OPEN_WRITE_ENDPOINT = (0x0D, 0x01, 0x02)
SLEEP = (0x01, 0x0E, 0x00)
BATTERY = (0x02, 0x0F)
MIC_STATUS = (0x02, 0xA6)
SIDETONE_MODE = (0x01, 0x46, 0x00)
SIDETONE = (0x01, 0x47, 0x00)
SET_COLOR = (0x12, 0x00)
COLOR_LENGTH = 8
KEEP_ALIVE = 10          # seconds between heartbeats
FRAME = 0.04             # seconds between frames of an effect

RGB_MODES = ["colorpulse", "colorshift", "colorwarp", "cpu-temperature", "flickering", "gpu-temperature",
             "gradient", "headset", "off", "rainbow", "pastelrainbow", "rotator", "static", "storm",
             "watercolor", "wave"]
SLEEP_MODES = {0: "Off", 1: "1 minute", 5: "5 minutes", 10: "10 minutes", 15: "15 minutes", 30: "30 minutes",
               60: "1 hour"}
KEY_TYPES = {0: "None", 1: "Media Keys", 3: "Keyboard", 9: "Mouse", 10: "Macro", 11: "Profile Switch"}
WORKING_TYPES = {0, 11}
BANDS = ["32", "64", "125", "250", "500", "1K", "2K", "4K", "8K", "16K"]
NAME = re.compile(r"^[a-zA-Z0-9]+$")


def zone(red, green, blue, indexes, name):
    return {"Color": {"red": red, "green": green, "blue": blue, "brightness": 1,
                      "Hex": "#%02x%02x%02x" % (red, green, blue)}, "ColorIndex": indexes, "Name": name}


def default_zones():
    return {"0": zone(255, 255, 0, [0, 1, 2], "Logo"), "1": zone(0, 255, 255, [3, 4, 5], "Microphone")}


def default_profile(serial):
    """saveDeviceProfile for a new device."""
    return {"Active": True, "Product": "HS80 MAX WIRELESS", "Serial": serial, "Brightness": 0,
            "RGBProfile": "headset", "BrightnessSlider": 100, "OriginalBrightness": 100, "Label": "Headset",
            "Profile": 0, "ZoneColors": default_zones(),
            "Equalizers": {str(i + 1): {"Name": n, "Value": 0} for i, n in enumerate(BANDS)},
            "SleepMode": 15, "DisableMicIndicator": 0, "SideTone": 0, "SideToneValue": 0,
            "KeyAssignmentHash": "", "RgbOff": False}


def complete(profile, serial):
    """The checks of saveDeviceProfile on a loaded profile."""
    base = default_profile(serial)
    out = {k: profile.get(k, v) for k, v in base.items()}
    if len(out["ZoneColors"] or {}) != 2:
        out["ZoneColors"] = default_zones()
    if not out["Equalizers"]:
        out["Equalizers"] = base["Equalizers"]
    if out["BrightnessSlider"] is None:
        out["BrightnessSlider"] = 100
    return out


def default_buttons():
    return {"1": {"name": "Scroll Press", "default": True, "actionType": 0, "actionCommand": 0,
                  "actionHold": False, "onRelease": False}}


def packet(endpoint, command, data=b""):
    buf = bytearray(65)
    buf[1], buf[2] = 0x02, endpoint
    body = bytes(command) + bytes(data)
    buf[3:3 + len(body)] = body
    return bytes(buf)


def color_data(data):
    """writeColor: length, the colour data type and the colours of the zones."""
    return struct.pack("<H", len(data)) + bytes(2) + bytes(SET_COLOR) + bytes(data)


def zone_bytes(profile, frame):
    """Puts the colours of the LEDs in the places of the zones (ColorIndex)."""
    buf = bytearray(COLOR_LENGTH)
    m = 0
    for key in sorted(profile["ZoneColors"], key=int):
        for index in profile["ZoneColors"][key]["ColorIndex"]:
            if m >= len(frame):
                break
            buf[index] = frame[m]
            m += 1
    return buf


def read_openlinkhub(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Hs80:
    def __init__(self, info, store, opener=hid.HidDevice, serial=None, clock=time.monotonic,
                 sleep=time.sleep, temps=None):
        self.info = info
        self.store = store
        self.opener = opener
        self.clock = clock
        self.sleep = sleep
        self.temps = temps or temperatures.Temperatures()
        interface, self.headset_id, fixed = DONGLES[info["product"]]
        self.dongle_serial = serial or usb_serial(info["usbPath"]) or hid.serial_for(info["usbPath"])
        self.serial = fixed or self.dongle_serial + "W"
        self.product = "HS80 MAX WIRELESS"
        self.lock = threading.RLock()
        self.device = None
        self.listener = None
        self.error = ""
        self.firmware = "n/a"
        self.dongle_firmware = "n/a"
        self.connected = False
        self.battery = 0
        self.mute = 0
        self.buttons_down = 0
        self.exit = threading.Event()
        self.effect_stop = None
        self.effect_thread = None
        self.listen_thread = None
        self.last_beat = 0
        self.profiles = None        # loaded on first use, so OpenLinkHub's settings are taken over when switching

    # --- settings ---

    def _load(self):
        saved = self.store.load(self.serial, {"profiles": None, "buttons": None, "rgb": None})
        if saved["profiles"] is None:
            saved = self._from_openlinkhub()
        self.profiles = {n: complete(p, self.serial) for n, p in (saved["profiles"] or {}).items()}
        if "default" not in self.profiles:
            self.profiles["default"] = default_profile(self.serial)
        if not any(p["Active"] for p in self.profiles.values()):
            self.profiles["default"]["Active"] = True
        self.buttons = saved["buttons"] or default_buttons()
        self.rgb = dict(rgb.default_profiles(), **(saved["rgb"] or {}))
        self._save()

    def _ensure(self):
        if self.profiles is None:
            self._load()

    def _from_openlinkhub(self):
        """The first time: OpenLinkHub's profiles, button file and RGB profiles of this headset."""
        database = self.store.openlinkhub_profiles.parent
        profiles = {}
        folder = database / "profiles"
        try:
            names = sorted(p.name for p in folder.iterdir())
        except OSError:
            names = []
        for name in names:
            stem = name[:-5] if name.endswith(".json") else ""
            if stem == self.serial:
                key = "default"
            elif stem.startswith(self.serial + "-"):
                key = stem.split("-", 1)[1]
            else:
                continue
            data = read_openlinkhub(folder / name)
            if isinstance(data, dict) and data.get("Serial") == self.serial:
                profiles[key] = data
        active = next((p for p in profiles.values() if p.get("Active")), {})
        hashed = active.get("KeyAssignmentHash") or ""
        buttons = read_openlinkhub(database / "key-assignments" / ("%s.json" % (hashed or "hs80maxW")))
        if isinstance(buttons, dict):
            buttons = {k: {f: b.get(f) for f in ("name", "default", "actionType", "actionCommand",
                                                 "actionHold", "onRelease")} for k, b in buttons.items()}
        rgb_file = read_openlinkhub(database / "rgb" / ("%s.json" % self.serial)) or {}
        own = {k: v for k, v in (rgb_file.get("profiles") or {}).items() if k in rgb.default_profiles()}
        return {"profiles": profiles or None, "buttons": buttons if isinstance(buttons, dict) else None,
                "rgb": own or None}

    def _save(self):
        self.store.save(self.serial, {"profiles": self.profiles, "buttons": self.buttons, "rgb": self.rgb})

    @property
    def active_name(self):
        self._ensure()
        return next((n for n, p in self.profiles.items() if p["Active"]), "default")

    @property
    def profile(self):
        name = self.active_name          # loads the settings first
        return self.profiles[name]

    # --- HID ---

    def _open(self):
        if self.device is None:
            self.device = self.opener(self.info["node"])
        if self.listener is None:
            self.listener = self.opener(self.info["node"])

    def _transfer(self, endpoint, command, data=b"", timeout=None):
        """Writes one report and returns the reply; events (0x03 ...) on the way are skipped."""
        if timeout is None:
            timeout = 1.0 if endpoint == DONGLE else 0.1
        with self.lock:
            self._open()
            while self.device.read(0):          # stale replies
                pass
            self.device.write(packet(endpoint, command, data))
            deadline = self.clock() + timeout
            while True:
                remaining = deadline - self.clock()
                if remaining <= 0:
                    raise TimeoutError("no reply from the headset dongle")
                reply = self.device.read(remaining)
                if reply and reply[0] != 0x03:
                    return reply

    def _try(self, endpoint, command, data=b"", timeout=None):
        try:
            reply = self._transfer(endpoint, command, data, timeout)
            self.error = ""
            return reply
        except OSError as e:
            self.error = str(e)
            return None

    # --- start, stop ---

    def start(self):
        self._ensure()
        self.exit.clear()
        reply = self._try(DONGLE, GET_FIRMWARE)
        if reply:
            self.dongle_firmware = "%d.%d.%d" % (reply[4], reply[5], reply[6])
        self._try(DONGLE, SOFTWARE_MODE)
        self.last_beat = self.clock()
        self.listen_thread = threading.Thread(target=self._listen, daemon=True)
        self.listen_thread.start()
        threading.Thread(target=self._first_connect, daemon=True).start()

    def _first_connect(self):
        """initAvailableDevices: when the headset answers, it is on."""
        if self._try(HEADSET, HEARTBEAT, timeout=1.0) is not None and not self.exit.is_set():
            self.sleep(1.0)
            self.connect()

    def refresh(self):
        if self.clock() - self.last_beat >= KEEP_ALIVE:
            self.last_beat = self.clock()
            self._try(DONGLE, HEARTBEAT)
            self._try(HEADSET, HEARTBEAT)

    def stop(self):
        self.exit.set()
        self._stop_effect()
        if self.connected:
            self._try(HEADSET, HARDWARE_MODE)
        self._try(DONGLE, HARDWARE_MODE)
        self.release()

    def release(self):
        """Lets go without sending anything (OpenLinkHub drives the headset again)."""
        self.exit.set()
        self._stop_effect()
        if self.listen_thread is not None:
            self.listen_thread.join(1.0)
            self.listen_thread = None
        with self.lock:
            for name in ("device", "listener"):
                handle = getattr(self, name)
                if handle is not None:
                    handle.close()
                    setattr(self, name, None)
        self.connected = False

    # --- headset ---

    def connect(self):
        if self.connected or self.exit.is_set():
            return
        self.connected = True
        reply = self._try(HEADSET, GET_FIRMWARE)
        if reply:
            self.firmware = "%d.%d.%d" % (reply[4], reply[5], reply[6])
        reply = self._try(HEADSET, MIC_STATUS)
        if reply:
            self.mute = reply[4]
        self._try(HEADSET, SOFTWARE_MODE)
        reply = self._try(HEADSET, BATTERY)
        if reply:
            self.battery = struct.unpack_from("<H", reply, 4)[0] // 10
        self._try(HEADSET, OPEN_COLOR_ENDPOINT)
        self.set_color()
        self.configure()

    def disconnect(self):
        if self.connected:
            self._stop_effect()
            self.connected = False
            self.sleep(1.0)

    def configure(self):
        """configureHeadset: sidetone (on with its level, or off) and the button endpoint."""
        p = self.profile
        if p["SideTone"] == 1:
            p["SideToneValue"] = max(0, min(100, int(p["SideToneValue"])))
            if self._try(HEADSET, SIDETONE_MODE, b"\x00") is None:
                return
            if self._try(HEADSET, SIDETONE, struct.pack("<H", p["SideToneValue"] * 10)) is None:
                return
        elif self._try(HEADSET, SIDETONE_MODE, b"\x01") is None:
            return
        self._try(HEADSET, OPEN_WRITE_ENDPOINT)

    def set_sleep_timer(self):
        minutes = self.profile["SleepMode"]
        if minutes == 0:
            return self._try(HEADSET, OPEN_SLEEP_ENDPOINT, b"\x00") is not None
        if self._try(HEADSET, OPEN_SLEEP_ENDPOINT, b"\x01") is None:
            return False
        return self._try(HEADSET, SLEEP, struct.pack("<I", minutes * 60 * 1000)) is not None

    # --- colours ---

    def write_color(self, data):
        if self.exit.is_set():
            return
        data = bytearray(data)
        if self.mute == 1:
            data[3:6] = b"\xff\x00\x00"
        elif self.profile["DisableMicIndicator"] == 1:
            data[3:6] = b"\x00\x00\x00"
        self._try(HEADSET, WRITE_COLOR, color_data(data))

    def _stop_effect(self):
        if self.effect_stop is not None:
            self.effect_stop.set()
            if self.effect_thread is not None and self.effect_thread is not threading.current_thread():
                self.effect_thread.join(1.0)
        self.effect_stop = None
        self.effect_thread = None

    def set_color(self):
        """setDeviceColor: off, the zone colours, the static colour, or an effect at 25 frames a second."""
        self._stop_effect()
        if not self.connected:
            return
        p = self.profile
        brightness = p["BrightnessSlider"] / 100
        mode = p["RGBProfile"]
        if p["RgbOff"] or mode == "off":
            self.write_color(bytes(COLOR_LENGTH))
            return
        if mode == "headset":
            frame = []
            for key in sorted(p["ZoneColors"], key=int):
                c = rgb.Color.from_json(p["ZoneColors"][key]["Color"])
                c.brightness = brightness
                c = rgb.modify_brightness(c)
                frame += [int(c.red), int(c.green), int(c.blue)]
            self.write_color(zone_bytes(p, frame))
            return
        if mode == "static":
            c = rgb.Color.from_json(self.rgb["static"]["start"])
            c.brightness = brightness
            c = rgb.modify_brightness(c)
            self.write_color(zone_bytes(p, [int(c.red), int(c.green), int(c.blue)] * 2))
            return
        stop = threading.Event()
        self.effect_stop = stop
        self.effect_thread = threading.Thread(target=self._run_effect, args=(stop, mode), daemon=True)
        self.effect_thread.start()

    def _run_effect(self, stop, mode):
        animation = rgb.Animation(self.clock)
        while not stop.is_set() and not self.exit.is_set():
            p = self.profile
            cpu = self.temps.cpu() if mode == "cpu-temperature" else 0
            gpu = self.temps.gpu() if mode == "gpu-temperature" else 0
            frame = animation.frame(mode, self.rgb.get(mode), 2, p["BrightnessSlider"] / 100, cpu, gpu)
            self.write_color(zone_bytes(p, frame))
            stop.wait(FRAME)

    # --- events ---

    def _listen(self):
        while not self.exit.is_set():
            try:
                with self.lock:
                    self._open()
                    listener = self.listener
                data = listener.read(0.1)
            except (OSError, AttributeError):
                self.sleep(0.5)
                continue
            if data:
                self.event(data)

    def event(self, data):
        if len(data) < 7:
            return
        if data[0] == 0x03 and data[1] == 0x01 and data[3] == 0x0F:
            level = struct.unpack_from("<H", data, 5)[0] // 10
            if level > 0:
                self.battery = level
        if data[0] == 0x03 and data[1] == 0x01 and data[2] == 0x02:
            self.trigger(data[3])
        if data[1] == 0x00 and data[3] == 0x36:
            if data[5] == 0x00:
                self.disconnect()
            elif data[5] == 0x02 and not self.connected:
                self.sleep(1.0)
                self.connect()
        elif data[0] == 0x03 and data[2] == 0x01 and data[3] == 0xA6:
            self.mute = data[5]
            self.set_color()

    def trigger(self, value):
        """TriggerKeyAssignment: one bit per button; only "Profile switch" does something here."""
        changed = value ^ self.buttons_down
        pressed, released = changed & value, changed & ~value
        self.buttons_down = value
        for bit in range(8):
            mask = 1 << bit
            if not changed & mask:
                continue
            button = self.buttons.get(str(mask))
            if button is None:
                continue
            down = bool(pressed & mask)
            if button.get("onRelease"):
                down = bool(released & mask)
            if down and not button.get("default") and button.get("actionType") == 11:
                self.rotate_profile()

    def rotate_profile(self):
        order = sorted(self.profiles)
        following = order[(order.index(self.active_name) + 1) % len(order)]
        self.change_profile(following)

    # --- changes ---

    def change_profile(self, name):
        if name not in self.profiles:
            return "Non-existing profile"
        if not self.connected:
            return "The headset is off"
        for n, p in self.profiles.items():
            p["Active"] = n == name
        self._save()
        self.configure()
        self.set_color()
        return ""

    def save_profile(self, name):
        if not NAME.match(name or "") or name == "default":
            return "Profile name can only contain letters and numbers"
        new = copy.deepcopy(self.profile)
        new["Active"] = False
        self.profiles[name] = new
        self._save()
        return ""

    def delete_profile(self, name):
        if name not in self.profiles or name == "default":
            return "Non-existing profile"
        if self.profiles[name]["Active"]:
            return "Unable to delete an active profile"
        del self.profiles[name]
        self._save()
        return ""

    def _changed(self, colours=False, headset=False):
        self._save()
        if colours:
            self.set_color()
        if headset and self.connected:
            self.configure()
        return ""

    def handle(self, path, body, method="POST"):
        """Requests of the headset page (headset.py and OpenLinkHub's headset.js); None when not one of them."""
        self._ensure()
        p = self.profile

        def number(key):
            try:
                return int(body.get(key))
            except (TypeError, ValueError):
                return None
        if method == "PUT" and path == "/api/userProfile":
            return self.save_profile(str(body.get("userProfileName") or ""))
        if method == "DELETE" and path == "/api/userProfile/delete":
            return self.delete_profile(str(body.get("userProfileName") or ""))
        if method != "POST":
            return None
        if path == "/api/userProfile/change":
            return self.change_profile(str(body.get("userProfileName") or ""))
        if path == "/api/color":
            mode = str(body.get("profile") or "")
            if not self.connected:
                return "The headset is off"
            if mode not in RGB_MODES:
                return "Non-existing RGB profile"
            p["RGBProfile"] = mode
            return self._changed(colours=True)
        if path == "/api/brightness/gradual":
            value = number("brightness")
            if not self.connected:
                return "The headset is off"
            if value is None or not 0 <= value <= 100:
                return "Invalid brightness"
            p["BrightnessSlider"] = value
            return self._changed(colours=p["RGBProfile"] in ("static", "headset"))
        if path == "/api/headset/zoneColors":
            count = 0
            for key, c in (body.get("colorZones") or {}).items():
                values = [c.get(k) for k in ("red", "green", "blue")] if isinstance(c, dict) else []
                if str(key) not in p["ZoneColors"] or not all(isinstance(v, (int, float)) and 0 <= v <= 255
                                                              for v in values) or len(values) != 3:
                    continue
                r, g, b = (int(v) for v in values)
                p["ZoneColors"][str(key)]["Color"].update(
                    {"red": r, "green": g, "blue": b, "Hex": "#%02x%02x%02x" % (r, g, b)})
                count += 1
            if not count:
                return "Unable to update headset colors"
            return self._changed(colours=True)
        if path == "/api/headset/sleep":
            minutes = number("sleepMode")
            if minutes not in SLEEP_MODES:
                return "Invalid sleep option"
            p["SleepMode"] = minutes
            self._save()
            if self.connected and not self.set_sleep_timer():
                return "Unable to change the sleep timer"
            return ""
        if path == "/api/headset/muteIndicator":
            value = number("muteIndicator")
            if value not in (0, 1):
                return "Invalid indicator option"
            p["DisableMicIndicator"] = value
            return self._changed(colours=True)
        if path == "/api/headset/sidetone":
            value = number("sideTone")
            if value not in (0, 1):
                return "Invalid sidetone"
            p["SideTone"] = value
            return self._changed(headset=True)
        if path == "/api/headset/sidetoneValue":
            value = number("sideToneValue")
            if value is None or not 0 <= value <= 100:
                return "Invalid sidetone"
            if p["SideTone"] != 1:
                return "Sidetone is not active"
            p["SideToneValue"] = value
            return self._changed(headset=True)
        if path == "/api/headset/equalizer":
            values = body.get("equalizers") or {}
            try:
                values = {str(int(k)): float(v) for k, v in values.items()}
            except (TypeError, ValueError, AttributeError):
                return "Unable to update equalizer"
            if len(values) != 10 or any(not 1 <= int(k) <= 10 or not -12 <= v <= 12 for k, v in values.items()):
                return "Unable to update equalizer"
            if all(p["Equalizers"][k]["Value"] == v for k, v in values.items()):
                return "Nothing to update"
            for k, v in values.items():
                p["Equalizers"][k]["Value"] = v
            return self._changed()
        if path == "/api/headset/updateKeyAssignment":
            if not self.connected:
                return "Unable to apply key assignment"
            hold, release = bool(body.get("pressAndHold")), bool(body.get("onRelease"))
            kind, enabled = number("keyAssignmentType"), bool(body.get("enabled"))
            if hold and (release or kind == 10):
                return "Press and Hold is not allowed"
            button = self.buttons.get(str(body.get("keyIndex")))
            if button is None or kind not in KEY_TYPES:
                return "Unable to apply key assignment"
            if not enabled and kind not in WORKING_TYPES:
                return "Media keys, keys, mouse buttons and macros don't work with quartercore-core yet"
            button.update({"default": enabled, "actionType": kind,
                           "actionCommand": number("keyAssignmentValue") or 0, "actionHold": hold,
                           "onRelease": release})
            self._save()
            self._try(HEADSET, OPEN_WRITE_ENDPOINT)
            return ""
        return None

    # --- API ---

    def summary(self):
        return {"Product": self.product, "Serial": self.serial, "Template": "hs80maxW.html"}

    def battery_info(self):
        return {"Device": self.product, "Level": self.battery} if self.connected else None

    def device_json(self):
        self._ensure()
        profiles = copy.deepcopy(self.profiles)
        return {"serial": self.serial, "product": self.product, "firmware": self.firmware,
                "Template": "hs80maxW.html", "Connected": self.connected, "BatteryLevel": self.battery,
                "userProfiles": profiles, "profileOrder": sorted(profiles),
                "DeviceProfile": profiles[self.active_name], "RGBModes": RGB_MODES,
                "SleepModes": {str(k): v for k, v in SLEEP_MODES.items()},
                "MuteIndicators": {"0": "Disabled", "1": "Enabled"},
                "SideToneModes": {"0": "Disabled", "1": "Enabled"},
                "KeyAssignment": copy.deepcopy(self.buttons),
                "KeyAssignmentTypes": {str(k): v for k, v in KEY_TYPES.items()},
                "MuteStatus": self.mute, "DongleFirmware": self.dongle_firmware,
                "DrivenBy": "quartercore-core", "Error": self.error}


def discover(store, root=hid.SYS_HIDRAW, opener=hid.HidDevice):
    found = []
    for info in hid.find(VENDOR, set(DONGLES), root):
        if info["interface"] == DONGLES[info["product"]][0]:
            found.append(Hs80(info, store, opener))
    return found
