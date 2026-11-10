# K100 keyboard: key colours, effects, profiles, settings, the control dial and key assignments
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/devices/k100/k100.go and
# src/keyboards). Commands go to USB interface 1 in 1025-byte reports: byte 1 is
# 0x08, then the command and its data; the keyboard answers with one report.
# Events (keys reported to software, the control dial) arrive on interface 2.
# In software mode the control dial and keys with an assignment are handled
# here, through the virtual keyboard and mouse (inputs.py); every other key
# stays a normal key. On stop the keyboard goes back to hardware mode.
#
# Not ported: OpenRGB integration, the RGB cluster, DPI and sniper actions
# (they need a mouse driven by quartercore-core) and the absolute mouse move
# in macros. The keyboard layouts are read from OpenLinkHub's database/keyboard.

import copy
import json
import re
import struct
import threading
import time
from pathlib import Path

from . import hid, inputs, macros, rgb, temperatures
from .xeneon import usb_serial

VENDOR = 0x1B1C
PRODUCTS = {7036, 7109, 7037}
COMMAND_INTERFACE, LISTEN_INTERFACE = 1, 2
REPORT = 1024
LAYOUTS = Path("/var/opt/OpenLinkHub/database/keyboard")
KEYBOARD_KEY, DEFAULT_LAYOUT = "k100-default", "US"

SOFTWARE_MODE = (0x01, 0x03, 0x00, 0x02)
HARDWARE_MODE = (0x01, 0x03, 0x00, 0x01)
ACTIVATE_LED = (0x0D, 0x01, 0x22)
BRIGHTNESS = ((0x01, 0x02, 0x00), (0x01, 0x6D, 0x00))
INIT_DEBOUNCE = ((0x01, 0x09, 0x00, 0x01), (0x01, 0x39, 0x00, 0x01))
DEBOUNCE = ((0x01, 0x0A, 0x00), (0x01, 0x38, 0x00))
GET_FIRMWARE = (0x02, 0x13)
SET_COLOR, SUB_COLOR, WRITE_COLOR = (0x12, 0x00), (0x07, 0x00), (0x06, 0x01)
POLLING_RATE = (0x01, 0x01, 0x00)
PERFORMANCE, WRITE_PERFORMANCE = (0x01, 0x4A, 0x00), (0x01,)
OPEN_ENDPOINT, CLOSE_ENDPOINT, KEY_ASSIGNMENT = (0x0D, 0x02, 0x02), (0x05, 0x01, 0x02), (0x06, 0x02)
KEEP_ALIVE = (0x12,)
KEEP_ALIVE_INTERVAL = 20
COLOR_LENGTH, LOCK_LED, KEY_ASSIGNMENT_LENGTH, LED_CHANNELS, MAX_CHUNK = 581, 342, 138, 194, 1021
FRAME = 0.02

RGB_MODES = ["circle", "circleshift", "colorpulse", "colorshift", "colorwarp", "cpu-temperature", "flickering",
             "gpu-temperature", "gradient", "keyboard", "off", "rainbow", "pastelrainbow", "rotator", "spinner",
             "static", "storm", "watercolor", "wave"]
BRIGHTNESS_MODES = {0: "RGB Profile", 1: "33 %", 2: "66 %", 3: "100 %"}
DIAL_OPTIONS = {1: "Volume Control", 2: "Brightness", 3: "Vertical Scroll", 4: "Zoom", 5: "Screen Brightness",
                6: "Media Control", 7: "Horizontal Scroll"}
POLLING_RATES = {0: "Not Set", 1: "125 Hz / 8 msec", 2: "250 Hz / 4 msec", 3: "500 Hz / 2 msec",
                 4: "1000 Hz / 1 msec", 5: "2000 Hz / 0.5 msec", 6: "4000 Hz / 0.25 msec", 7: "8000 Hz / 0.125 msec"}
KEY_TYPES = {0: "None", 1: "Media Keys", 2: "DPI +", 3: "Keyboard", 4: "DPI -", 8: "Sniper", 9: "Mouse",
             10: "Macro", 13: "Scroll Up", 14: "Scroll Down", 15: "Zoom In", 16: "Zoom Out",
             17: "Screen Brightness +", 18: "Screen Brightness -", 21: "Change Profile", 22: "Profile Switch"}
DEBOUNCE_TIMES = {i: "%dms" % i for i in range(1, 10)}
DIAL_COLORS = {1: (255, 255, 255), 2: (0, 255, 255), 3: (255, 127, 0), 4: (128, 0, 128), 5: (191, 255, 0),
               6: (0, 0, 255), 7: (255, 0, 0)}
PERFORMANCE_FIELDS = (("Disable Win Key", "DisableWinKey", "perf_winKey"),
                      ("Disable Shift + Tab", "DisableShiftTab", "perf_shiftTab"),
                      ("Disable Alt + Tab", "DisableAltTab", "perf_altTab"),
                      ("Disable Alt + F4", "DisableAltF4", "perf_altF4"))
NAME = re.compile(r"^[a-zA-Z0-9]+$")
# Action ids of inputs.ACTIONS used by the control dial
VOLUME_UP, VOLUME_DOWN, MEDIA_PREV, MEDIA_NEXT = 1, 2, 5, 7
SCREEN_BRIGHTNESS_DOWN, SCREEN_BRIGHTNESS_UP = 124, 125


def packet(command, data=b""):
    buf = bytearray(REPORT + 1)
    buf[1] = 0x08
    body = bytes(command) + bytes(data)
    buf[2:2 + len(body)] = body
    return bytes(buf)


def color(red, green, blue):
    return {"red": red, "green": green, "blue": blue, "brightness": 0, "position": 0, "temperature": 0, "Hex": ""}


def load_layouts(folder=LAYOUTS):
    """GetLayouts / GetKeyboard: the K100 layouts in OpenLinkHub's keyboard folder, by layout name."""
    layouts = {}
    try:
        files = sorted(Path(folder).glob("*.json"))
    except OSError:
        return layouts
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("key") == KEYBOARD_KEY and data.get("layout"):
            layouts[data["layout"]] = data
    return layouts


def default_profile(serial, keyboard):
    return {"Active": True, "Product": "K100", "Serial": serial, "LCDMode": 0, "LCDRotation": 0, "Brightness": 0,
            "RGBProfile": "keyboard", "Label": "Keyboard", "Layout": DEFAULT_LAYOUT,
            "Keyboards": {"default": copy.deepcopy(keyboard)}, "Profile": "default", "PollingRate": 4,
            "BrightnessLevel": 1000, "Profiles": ["default"], "ControlDial": 1, "DebounceTime": 1,
            "ControlDialColors": {str(k): color(*v) for k, v in DIAL_COLORS.items()}, "RGBCluster": False,
            "OpenRGBIntegration": False, "DisableAltTab": False, "DisableAltF4": False, "DisableShiftTab": False,
            "DisableWinKey": False, "Performance": False, "RgbOff": False}


def keys_of(keyboard):
    """(row id, key id, key) for every key, rows and keys in number order."""
    for row_id in sorted((keyboard or {}).get("row") or {}, key=int):
        row = keyboard["row"][row_id]
        for key_id in sorted(row.get("keys") or {}, key=int):
            yield row_id, key_id, row["keys"][key_id]


def key_value(data):
    """The pressed keys of a key report (data[1] == 0x02) as the number OpenLinkHub hashes (KeyHash)."""
    raw = bytearray(data[2:22])
    if raw[13] == 0x04:
        raw[13] -= 0x04
    if raw[13] == 0x40:
        raw[13] -= 0x40
    return int.from_bytes(bytes(raw), "little")


def read_openlinkhub(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class K100:
    def __init__(self, info, store, opener=None, serial=None, clock=time.monotonic, sleep=time.sleep,
                 temps=None, input_devices=None, player=None, layouts_folder=LAYOUTS):
        self.info = info
        self.store = store
        self.opener = opener or (lambda node: hid.HidDevice(node, REPORT))
        self.clock, self.sleep = clock, sleep
        self.temps = temps or temperatures.Temperatures()
        self.inputs = input_devices or inputs.shared()
        self.player = player or macros.Player(self.inputs)
        self.layouts_folder = layouts_folder
        self.serial = serial or usb_serial(info["usbPath"]) or hid.serial_for(info["usbPath"])
        self.product = "K100"
        self.lock = threading.RLock()
        self.device = None
        self.listener = None
        self.error = ""
        self.firmware = "n/a"
        self.exit = threading.Event()
        self.effect_stop = None
        self.effect_thread = None
        self.listen_thread = None
        self.last_beat = 0
        self.held_key = None
        self.mouse_loop = None
        self.gone = False             # the keyboard reconnects after a polling rate change
        self.profiles = None
        self.layouts = None

    # --- settings ---

    def _ensure(self):
        if self.profiles is None:
            self._load()

    def _load(self):
        self.layouts = load_layouts(self.layouts_folder)
        saved = self.store.load(self.serial, {"profiles": None, "rgb": None})
        if saved["profiles"] is None:
            saved = self._from_openlinkhub()
        profiles = saved["profiles"] or {}
        base = self.layouts.get(DEFAULT_LAYOUT) or {"version": 0, "key": KEYBOARD_KEY, "row": {}}
        if "default" not in profiles:
            profiles["default"] = default_profile(self.serial, base)
        for p in profiles.values():
            self._complete(p, base)
        if not any(p["Active"] for p in profiles.values()):
            profiles["default"]["Active"] = True
        self.profiles = profiles
        self.rgb = dict(rgb.default_profiles(), **(saved["rgb"] or {}))
        self._save()

    def _complete(self, p, base):
        """The checks of saveDeviceProfile: defaults, and a newer layout version replaces "default"."""
        for k, v in default_profile(self.serial, base).items():
            p.setdefault(k, v)
        if not p["DebounceTime"]:
            p["DebounceTime"] = 1
        if not p["Layout"]:
            p["Layout"] = DEFAULT_LAYOUT
        if not p["ControlDialColors"]:
            p["ControlDialColors"] = {str(k): color(*v) for k, v in DIAL_COLORS.items()}
        layout = self.layouts.get(p["Layout"])
        current = (p["Keyboards"] or {}).get("default") or {}
        if layout is not None and current.get("version") != layout.get("version"):
            p["Keyboards"]["default"] = copy.deepcopy(layout)

    def _from_openlinkhub(self):
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
            if isinstance(data, dict) and data.get("Serial") == self.serial and data.get("Keyboards"):
                data.pop("Path", None)
                profiles[key] = data
        rgb_file = read_openlinkhub(database / "rgb" / ("%s.json" % self.serial)) or {}
        own = {k: v for k, v in (rgb_file.get("profiles") or {}).items() if k in rgb.default_profiles()}
        return {"profiles": profiles or None, "rgb": own or None}

    def _save(self):
        self.store.save(self.serial, {"profiles": self.profiles, "rgb": self.rgb})

    @property
    def active_name(self):
        self._ensure()
        return next((n for n, p in self.profiles.items() if p["Active"]), "default")

    @property
    def profile(self):
        name = self.active_name
        return self.profiles[name]

    @property
    def keyboard(self):
        p = self.profile
        return (p["Keyboards"] or {}).get(p["Profile"])

    # --- HID ---

    def _open(self):
        if self.device is None:
            self.device = self.opener(self.info["node"])
        if self.listener is None and self.info.get("listener"):
            self.listener = self.opener(self.info["listener"])

    def _transfer(self, command, data=b"", timeout=0.5):
        with self.lock:
            self._open()
            while self.device.read(0):
                pass
            self.device.write(packet(command, data))
            reply = self.device.read(timeout)
            if not reply:
                raise TimeoutError("no reply from the K100")
            return reply

    def _try(self, command, data=b""):
        try:
            reply = self._transfer(command, data)
            self.error = ""
            return reply
        except OSError as e:
            self.error = str(e)
            return None

    # --- start, stop ---

    def start(self):
        self._ensure()
        self.exit.clear()
        self._try(SOFTWARE_MODE)
        self._try(ACTIVATE_LED)
        self.sleep(0.5)
        reply = self._try(GET_FIRMWARE)
        if reply:
            self.firmware = "%d.%d.%d" % (reply[3], reply[4], struct.unpack_from("<H", reply, 5)[0])
        self.last_beat = self.clock()
        self.set_color()
        self.set_brightness_level()
        self.listen_thread = threading.Thread(target=self._listen, daemon=True)
        self.listen_thread.start()
        self.setup_performance()
        self.set_debounce_time()

    def refresh(self):
        if self.clock() - self.last_beat >= KEEP_ALIVE_INTERVAL:
            self.last_beat = self.clock()
            self._try(KEEP_ALIVE)

    def stop(self):
        self.exit.set()
        self._stop_effect()
        self._try(HARDWARE_MODE)
        self.release()

    def release(self):
        """Lets go without sending anything."""
        self.exit.set()
        self._stop_effect()
        if self.mouse_loop is not None:
            self.mouse_loop.set()
            self.mouse_loop = None
        if self.listen_thread is not None and self.listen_thread is not threading.current_thread():
            self.listen_thread.join(1.0)
        self.listen_thread = None
        with self.lock:
            for name in ("device", "listener"):
                handle = getattr(self, name)
                if handle is not None:
                    handle.close()
                    setattr(self, name, None)

    # --- colours ---

    def _dial_color(self):
        p = self.profile
        c = (p["ControlDialColors"] or {}).get(str(p["ControlDial"]))
        rgb_values = (int(c["red"]), int(c["green"]), int(c["blue"])) if c else (255, 255, 255)
        return bytes(rgb_values) * 8

    def write_color(self, data):
        """writeColorBuffer: the performance LEDs, the dial colour, then the colours in chunks."""
        if self.exit.is_set():
            return
        data = bytearray(data)
        p = self.profile
        if p["Performance"]:
            data[0:3] = b"\xff\xff\xff"
            data[LOCK_LED:LOCK_LED + 3] = b"\xff\x00\x00"
        data[546:567] = self._dial_color()[:21]
        buffer = struct.pack("<H", len(data)) + bytes(2) + bytes(SET_COLOR) + bytes(data)
        for i in range(0, len(buffer), MAX_CHUNK):
            self._try(WRITE_COLOR if i == 0 else SUB_COLOR, buffer[i:i + MAX_CHUNK])

    def _stop_effect(self):
        if self.effect_stop is not None:
            self.effect_stop.set()
            if self.effect_thread is not None and self.effect_thread is not threading.current_thread():
                self.effect_thread.join(1.0)
        self.effect_stop = None
        self.effect_thread = None

    def _fill(self, value_of):
        buf = bytearray(COLOR_LENGTH)
        for _, _, key in keys_of(self.keyboard):
            for index in key.get("packetIndex") or []:
                if 0 <= index and index + 2 < COLOR_LENGTH:
                    buf[index:index + 3] = value_of(key, index)
        return buf

    def set_color(self):
        """setDeviceColor: off, the key colours, the static colour, or an effect at 50 frames a second."""
        self._stop_effect()
        p = self.profile
        if self.keyboard is None:
            return
        mode = p["RGBProfile"]
        if p["RgbOff"]:
            self.write_color(self._fill(lambda key, i: b"\x00\x00\x00"))
            return
        if mode == "keyboard":
            def own(key, i):
                c = key.get("color") or {}
                return bytes(rgb.byte(c.get(k) or 0) for k in ("red", "green", "blue"))
            self.write_color(self._fill(own))
            return
        if mode == "static":
            c = self.rgb["static"]["start"]
            value = bytes(rgb.byte(c.get(k) or 0) for k in ("red", "green", "blue"))
            self.write_color(self._fill(lambda key, i: value))
            return
        stop = threading.Event()
        self.effect_stop = stop
        self.effect_thread = threading.Thread(target=self._run_effect, args=(stop, mode), daemon=True)
        self.effect_thread.start()

    def _run_effect(self, stop, mode):
        animation = rgb.Animation(self.clock)
        while not stop.is_set() and not self.exit.is_set():
            p = self.profile
            profile = self.rgb.get(mode)
            if mode == "off":
                frame = bytes(LED_CHANNELS * 3)
            else:
                level = p["Brightness"]
                brightness = rgb_brightness(level) if level > 0 else float((profile or {}).get("brightness") or 0)
                cpu = self.temps.cpu() if mode == "cpu-temperature" else 0
                gpu = self.temps.gpu() if mode == "gpu-temperature" else 0
                frame = animation.frame(mode, profile, LED_CHANNELS, brightness, cpu, gpu, set_colors=level > 0)
            self.write_color(self._fill(lambda key, i: frame[i:i + 3] if i + 3 <= len(frame) else b"\x00\x00\x00"))
            stop.wait(FRAME)

    # --- settings on the keyboard ---

    def set_brightness_level(self):
        level = struct.pack("<H", max(0, min(1000, int(self.profile["BrightnessLevel"]))))
        for command in BRIGHTNESS:
            self._try(command, level)

    def set_debounce_time(self):
        value = int(self.profile["DebounceTime"])
        if not 0 <= value <= 9:
            return
        if not any([self._try(command) is not None for command in INIT_DEBOUNCE]):
            return
        for command in DEBOUNCE:
            self._try(command, bytes([30 + value]))

    def setup_key_assignment(self):
        """Keys with their default action stay keys; the others are reported to software."""
        buf = bytearray(b"\x01" * KEY_ASSIGNMENT_LENGTH)
        for _, _, key in keys_of(self.keyboard):
            data = key.get("keyData") or []
            if key.get("onlyColor") or not data or not 0 <= data[0] < KEY_ASSIGNMENT_LENGTH:
                continue
            buf[data[0]] = 1 if key.get("default") else 0
        self._try(OPEN_ENDPOINT)
        self._try(KEY_ASSIGNMENT, struct.pack("<H", len(buf)) + bytes(2) + bytes(buf))
        self._try(CLOSE_ENDPOINT)

    def setup_performance(self):
        p = self.profile
        base = 0
        if p["Performance"]:
            base = (1 if p["DisableWinKey"] else 0) + (2 if p["DisableAltTab"] else 0) \
                + (4 if p["DisableAltF4"] else 0) + (8 if p["DisableShiftTab"] else 0)
        self._try(PERFORMANCE, bytes([base]))
        self._try(WRITE_PERFORMANCE, bytes([0x45, 0x00, 0x01 if p["Performance"] else 0x00]))
        self.setup_key_assignment()
        if p["RGBProfile"] in ("keyboard", "static"):
            self.set_color()

    # --- events ---

    def _listen(self):
        while not self.exit.is_set():
            try:
                with self.lock:
                    self._open()
                    listener = self.listener
                if listener is None:
                    return
                data = listener.read(0.1)
            except OSError:
                self.sleep(0.5)
                continue
            if data:
                self.event(data)

    def event(self, data):
        if len(data) < 22:
            return
        if data[1] == 0x02:
            self.trigger(data)
        elif data[1] == 0x05:
            self.dial(data[4])

    def dial(self, value):
        """The control dial: 1 is a turn to the right, 255 to the left."""
        if value not in (1, 255):
            return
        right = value == 1
        option = self.profile["ControlDial"]
        if option == 1:
            self.inputs.key(VOLUME_UP if right else VOLUME_DOWN)
        elif option == 2:
            p = self.profile
            p["BrightnessLevel"] = min(1000, p["BrightnessLevel"] + 100) if right else max(0, p["BrightnessLevel"] - 100)
            self._save()
            self.set_brightness_level()
        elif option == 3:
            self.inputs.scroll(not right)
        elif option == 4:
            self.inputs.zoom(right)
        elif option == 5:
            self.inputs.key(SCREEN_BRIGHTNESS_UP if right else SCREEN_BRIGHTNESS_DOWN)
        elif option == 6:
            self.inputs.key(MEDIA_NEXT if right else MEDIA_PREV)
        elif option == 7:
            self.inputs.scroll_horizontal(right)

    def _key_by_hash(self, value):
        text = str(value)
        for _, _, key in keys_of(self.keyboard):
            if text in (key.get("keyHash") or []):
                return key
        return None

    def trigger(self, data):
        """triggerKeyAssignment: a key reported to software was pressed or let go."""
        value = key_value(data)
        self.player.release()
        if self.held_key is not None:
            # OpenLinkHub sends a press and release of a held key on the next report
            if self.held_key.get("actionType") in (1, 3):
                self.inputs.key(self.held_key.get("actionCommand") or 0)
            self.held_key = None
        if value == 0:
            return
        key = self._key_by_hash(value)
        if key is None:
            return
        p = self.profile
        if key.get("isLock"):
            p["Performance"] = not p["Performance"]
            self._save()
            self.setup_performance()
            return
        if key.get("isDialChange"):
            self.set_dial(p["ControlDial"] + 1 if p["ControlDial"] + 1 <= len(DIAL_OPTIONS) else 1)
        if key.get("default") or key.get("onlyColor"):
            return
        kind, command, hold = int(key.get("actionType") or 0), int(key.get("actionCommand") or 0), bool(key.get("actionHold"))
        if kind in (1, 3):
            if hold:
                self.held_key = key
            self.inputs.key(command, hold)
        elif kind == 9:
            if hold:
                if self.mouse_loop is None:
                    stop = self.mouse_loop = threading.Event()
                    interval = max(1, int(key.get("toggleDelay") or 0)) / 1000
                    threading.Thread(target=self._mouse_loop, args=(stop, command, interval), daemon=True).start()
                else:
                    self.mouse_loop.set()
                    self.mouse_loop = None
            else:
                self.inputs.click(command)
        elif kind == 10:
            threading.Thread(target=self.player.play, args=(command, True), daemon=True).start()
        elif kind == 13:
            self.inputs.scroll(True)
        elif kind == 14:
            self.inputs.scroll(False)
        elif kind == 15:
            self.inputs.zoom(True)
        elif kind == 16:
            self.inputs.zoom(False)
        elif kind == 17:
            self.inputs.key(SCREEN_BRIGHTNESS_UP)
        elif kind == 18:
            self.inputs.key(SCREEN_BRIGHTNESS_DOWN)
        elif kind == 21:
            self.change_profile(str(key.get("deviceId") or ""))
        elif kind == 22:
            order = sorted(self.profiles)
            self.change_profile(order[(order.index(self.active_name) + 1) % len(order)])

    def _mouse_loop(self, stop, command, interval):
        self.inputs.click(command)
        while not stop.wait(interval):
            self.inputs.click(command)

    # --- changes ---

    def set_dial(self, option):
        self.profile["ControlDial"] = option
        self._save()
        self.set_color()

    def change_profile(self, name):
        if name not in self.profiles:
            return "Non-existing profile"
        for n, p in self.profiles.items():
            p["Active"] = n == name
        self._save()
        self.set_color()
        self.setup_performance()
        return ""

    def _key(self, key_id):
        for _, kid, key in keys_of(self.keyboard):
            if int(kid) == int(key_id):
                return key
        return None

    def handle(self, path, body, method="POST"):
        """Requests of the keyboard page (backend.py, keyboard.py and lighting.py); None when not one of them."""
        self._ensure()
        p = self.profile

        def number(key):
            try:
                return int(body.get(key))
            except (TypeError, ValueError):
                return None
        name = str(body.get("keyboardProfileName") or "")
        if method == "PUT":
            if path == "/api/userProfile":
                user = str(body.get("userProfileName") or "")
                if not NAME.match(user) or user == "default":
                    return "Profile name can only contain letters and numbers"
                new = copy.deepcopy(p)
                new["Active"] = False
                self.profiles[user] = new
                self._save()
                return ""
            if path == "/api/keyboard/profile/new":
                if not NAME.match(name):
                    return "Profile name can only contain letters and numbers"
                if name in p["Profiles"] or name in p["Keyboards"]:
                    return "Profile already exists"
                p["Profiles"].append(name)
                p["Keyboards"][name] = copy.deepcopy(self.keyboard)
                self._save()
                return ""
            if path == "/api/color/change":
                error = rgb.update_profile(self.rgb, body)
                if not error:
                    self._save()
                    self.set_color()
                return error
            return None
        if method == "DELETE":
            if path == "/api/userProfile/delete":
                user = str(body.get("userProfileName") or "")
                if user not in self.profiles or user == "default":
                    return "Non-existing profile"
                if self.profiles[user]["Active"]:
                    return "Unable to delete an active profile"
                del self.profiles[user]
                self._save()
                return ""
            if path == "/api/keyboard/profile/delete":
                if name == "default":
                    return "The default profile can't be deleted"
                if name not in p["Profiles"] or name not in p["Keyboards"]:
                    return "Non-existing profile"
                p["Profiles"].remove(name)
                del p["Keyboards"][name]
                p["Profile"] = "default"
                self._save()
                self.set_color()
                return ""
            return None
        if path == "/api/userProfile/change":
            return self.change_profile(str(body.get("userProfileName") or ""))
        if path == "/api/color":
            mode = str(body.get("profile") or "")
            if mode not in RGB_MODES:
                return "Non-existing RGB profile"
            p["RGBProfile"] = mode
            self._save()
            self.set_color()
            return ""
        if path == "/api/brightness":
            mode = number("brightness")
            if mode not in BRIGHTNESS_MODES:
                return "Invalid brightness"
            p["Brightness"] = mode
            self._save()
            self.set_color()
            return ""
        if path == "/api/keyboard/color":
            return self.set_key_colors(number("keyOption"), number("keyId"), body.get("color"), body.get("keys"))
        if path == "/api/keyboard/profile/change":
            if name not in p["Profiles"] or name not in p["Keyboards"]:
                return "Non-existing profile"
            p["Profile"] = name
            self._save()
            self.set_color()
            return ""
        if path == "/api/keyboard/profile/save":
            self._save()
            return ""
        if path == "/api/keyboard/layout":
            layout = str(body.get("keyboardLayout") or "")
            if layout not in self.layouts:
                return "Invalid keyboard layout"
            p["Keyboards"]["default"] = copy.deepcopy(self.layouts[layout])
            p["Layout"] = layout
            self._save()
            self.set_color()
            self.setup_performance()
            return ""
        if path == "/api/keyboard/pollingRate":
            rate = number("pollingRate")
            if rate not in POLLING_RATES:
                return "Invalid polling rate"
            self._stop_effect()
            p["PollingRate"] = rate
            self._save()
            if self._try(POLLING_RATE, bytes([rate])) is None:
                return "Unable to change the polling rate"
            self.gone = True          # the keyboard starts again; quartercore-core takes it over anew
            return ""
        if path == "/api/keyboard/dial":
            option = number("keyboardControlDial")
            if option not in DIAL_OPTIONS:
                return "Invalid control dial option"
            self.set_dial(option)
            return ""
        if path == "/api/keyboard/debounceTime":
            value = number("debounceTime")
            if value is None or not 1 <= value <= 9 or value == p["DebounceTime"]:
                return "Invalid debounce time"
            p["DebounceTime"] = value
            self._save()
            self.set_debounce_time()
            return ""
        if path == "/api/keyboard/setPerformance":
            for _, field, internal in PERFORMANCE_FIELDS:
                p[field] = bool(body.get(internal))
            self._save()
            self.setup_performance()
            return ""
        if path == "/api/keyboard/dial/setColors":
            for zone, c in (body.get("colorZones") or {}).items():
                if str(zone) in p["ControlDialColors"] and isinstance(c, dict):
                    p["ControlDialColors"][str(zone)] = color(*(rgb.byte(c.get(k) or 0) for k in ("red", "green", "blue")))
            self._save()
            self.set_color()
            return ""
        if path == "/api/keyboard/updateKeyAssignment":
            return self.set_key_assignment(body)
        return None

    def set_key_colors(self, option, key_id, c, selection):
        """UpdateDeviceColor: one key (0), its row (1), all keys (2) or the selected keys (3). Kept until saved."""
        if not isinstance(c, dict) or any(not 0 <= (c.get(k) or 0) <= 255 for k in ("red", "green", "blue")):
            return "Invalid color"
        new = color(*(rgb.byte(c.get(k) or 0) for k in ("red", "green", "blue")))
        keyboard = self.keyboard
        targets = []
        if option == 0:
            targets = [key for _, kid, key in keys_of(keyboard) if int(kid) == key_id]
        elif option == 1:
            row = next((rid for rid, kid, _ in keys_of(keyboard) if int(kid) == key_id), None)
            targets = [key for rid, _, key in keys_of(keyboard) if rid == row] if row is not None else []
        elif option == 2:
            targets = [key for _, _, key in keys_of(keyboard)]
        elif option == 3:
            wanted = {int(k) for k in selection or [] if isinstance(k, (int, float, str)) and str(k).isdigit()}
            targets = [key for _, kid, key in keys_of(keyboard) if int(kid) in wanted]
        if not targets:
            return "Invalid key selected"
        for key in targets:
            key["color"] = dict(new)
        self.set_color()
        return ""

    def set_key_assignment(self, body):
        """ProcessChangeKeyAssignment + UpdateDeviceKeyAssignment."""
        hold, release = bool(body.get("pressAndHold")), bool(body.get("onRelease"))
        try:
            kind, value = int(body.get("keyAssignmentType") or 0), int(body.get("keyAssignmentValue") or 0)
        except (TypeError, ValueError):
            return "Unable to apply key assignment"
        if kind == 10 and hold:
            return "Press and Hold is not allowed for macros"
        if release and hold:
            return "Press and Hold is not allowed with On Release"
        if release and kind == 8:
            return "Sniper is not allowed with On Release"
        if not hold and kind == 8:
            return "Sniper needs Press and Hold"
        if kind not in KEY_TYPES:
            return "Unable to apply key assignment"
        key = self._key(body.get("keyIndex") if str(body.get("keyIndex", "")).lstrip("-").isdigit() else -1)
        if key is None or key.get("onlyColor"):
            return "Unable to apply key assignment"
        key.update({"default": bool(body.get("enabled")), "actionType": kind, "actionCommand": value,
                    "deviceId": str(body.get("keyAssignmentValueString") or ""), "actionHold": hold,
                    "toggleDelay": max(30, int(body.get("toggleDelay") or 0))})
        self._save()
        self.setup_key_assignment()
        return ""

    def get(self, path):
        """GET requests with the serial at the end; None when not one of them."""
        self._ensure()
        base = path.rsplit("/", 1)[0] + "/"
        p = self.profile
        if base == "/api/keyboard/assignmentsTypes/":
            return {str(k): v for k, v in KEY_TYPES.items()}
        if base == "/api/keyboard/assignmentsModifiers/":
            modifiers = {"0": "None"}
            for _, kid, key in keys_of(self.keyboard):
                if key.get("modifier"):
                    modifiers[str(kid)] = key.get("keyNameInternal") or key.get("keyName") or ""
            return modifiers
        if base == "/api/keyboard/getPerformance/":
            return [{"name": n, "type": "checkbox", "value": bool(p[field]), "internal": internal}
                    for n, field, internal in PERFORMANCE_FIELDS]
        if base == "/api/keyboard/dial/getColors/":
            return [{"Id": int(k), "Name": DIAL_OPTIONS.get(int(k), ""), "Color": c}
                    for k, c in sorted(p["ControlDialColors"].items(), key=lambda kv: int(kv[0]))]
        if base == "/api/device/profiles/":
            return sorted(self.profiles)
        if base == "/api/color/":
            return rgb.profiles_view(self.product, self.rgb, RGB_MODES)
        return None

    # --- API ---

    def summary(self):
        return {"Product": self.product, "Serial": self.serial, "Template": "k100.html"}

    def device_json(self):
        self._ensure()
        profiles = copy.deepcopy(self.profiles)
        return {"serial": self.serial, "product": self.product, "firmware": self.firmware, "Template": "k100.html",
                "userProfiles": profiles, "profileOrder": sorted(profiles),
                "DeviceProfile": profiles[self.active_name], "RGBModes": RGB_MODES,
                "Brightness": {str(k): v for k, v in BRIGHTNESS_MODES.items()},
                "PollingRates": {str(k): v for k, v in POLLING_RATES.items()},
                "ControlDialOptions": {str(k): v for k, v in DIAL_OPTIONS.items()},
                "DebounceTimes": {str(k): v for k, v in DEBOUNCE_TIMES.items()},
                "KeyAssignmentTypes": {str(k): v for k, v in KEY_TYPES.items()},
                "Layouts": sorted(self.layouts), "LEDChannels": LED_CHANNELS,
                "DrivenBy": "quartercore-core", "Error": self.error}


def rgb_brightness(mode):
    """GetBrightnessValue: 33, 66 or 100 %."""
    return {1: 0.3, 2: 0.6, 3: 1.0}.get(mode, 0.0)


def discover(store, root=hid.SYS_HIDRAW, opener=None):
    found = {}
    for info in hid.find(VENDOR, PRODUCTS, root):
        entry = found.setdefault(info["usbPath"], {})
        entry[info["interface"]] = info
    drivers = []
    for interfaces in found.values():
        command = interfaces.get(COMMAND_INTERFACE)
        if command is None:
            continue
        listener = interfaces.get(LISTEN_INTERFACE)
        info = dict(command, listener=listener["node"] if listener else None)
        drivers.append(K100(info, store, opener))
    return drivers
