# A small fake OpenLinkHub for tests and screenshots, never touches hardware
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Standalone: python3 tests/fake_openlinkhub.py [port]   (default 27099)
# then: python3 -m quartercore --url http://127.0.0.1:27099

import copy
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CPU_CURVE = [{"x": 0, "y": 30}, {"x": 50, "y": 40}, {"x": 80, "y": 80}, {"x": 200, "y": 100}]
PUMP_CURVE = [{"x": 0, "y": 60}, {"x": 70, "y": 70}, {"x": 200, "y": 100}]


def initial_profiles():
    def profile(sensor, sensor_name, steps=None, linear=False, zero_rpm=False, hidden=False):
        return {"sensor": sensor, "sensorString": sensor_name, "linear": linear, "zeroRpm": zero_rpm,
                "Hidden": hidden, "profiles": steps or [{"id": 1, "min": 0, "max": 30}, {"id": 2, "min": 30, "max": 200}],
                "points": {"0": copy.deepcopy(PUMP_CURVE), "1": copy.deepcopy(CPU_CURVE)}}
    return {
        "Normal": profile(0, "CPU"),
        "Quiet": profile(0, "CPU"),
        "Performance": profile(0, "CPU"),
        "Gaming": profile(1, "GPU", zero_rpm=True),
        "Liquid": profile(2, "Liquid Temperature", linear=True),
        "Fixed": profile(0, "CPU", steps=[{"id": 1, "min": 0, "max": 200, "fans": 70, "pump": 70}]),
        "aioCriticalTemperature": profile(2, "Liquid Temperature", hidden=True),
    }


def rgb(r, g, b, temperature=0, position=0):
    return {"red": r, "green": g, "blue": b, "brightness": 1, "position": position, "temperature": temperature, "Hex": ""}


def effect(name, speed=4, start=(0, 255, 255), end=(0, 255, 255), direction=0, gradients=None, middle=(0, 0, 0)):
    return {"speed": speed, "brightness": 1, "smoothness": 20, "start": rgb(*start), "middle": rgb(*middle),
            "end": rgb(*end), "gradients": gradients, "minTemp": 0, "maxTemp": 0, "profileName": name,
            "alternateColors": False, "rgbDirection": direction, "perLed": False}


def initial_effects():
    return {
        "static": effect("Static", start=(0, 255, 255), end=(0, 255, 255)),
        "colorwave": effect("Color Wave", speed=2, start=(255, 0, 0), end=(0, 0, 255), direction=4),
        "rainbow": effect("Rainbow", speed=4),
        "cpu-temperature": dict(effect("CPU Temperature"), start=rgb(0, 255, 0, 20), middle=rgb(255, 255, 0, 50),
                                end=rgb(255, 0, 0, 95)),
        "gradient": effect("Gradient", speed=10, gradients={
            "0": rgb(255, 0, 0, position=0), "1": rgb(0, 255, 0, position=0.5), "2": rgb(0, 0, 255, position=1)}),
        "probe-temperature": effect("Probe Temperature"),
        "off": effect(""),
        "keyboard": effect("Keyboard"),
        "led": dict(effect("Per LED"), perLed=True),
    }


HUB = {
    "serial": "HUB1", "product": "iCUE LINK System Hub", "firmware": "1.0", "Template": "lsh.html",
    "DeviceProfile": {"BrightnessSlider": 100}, "RGBModes": ["static", "rainbow"],
    "devices": {
        "1": {"name": "iCUE LINK RX RGB", "label": "Set Label", "description": "Fan", "rpm": 700,
              "temperatureString": "", "profile": "Normal", "rgb": "static", "HasSpeed": True},
        "2": {"name": "iCUE LINK TITAN 360", "label": "Set Label", "description": "AIO", "rpm": 2400,
              "temperatureString": "26.5 °C", "profile": "Normal", "rgb": "static", "HasSpeed": True},
        "3": {"name": "Temperature probe", "label": "Set Label", "description": "Probe", "rpm": 0,
              "temperatureString": "30 °C", "profile": "", "rgb": "", "HasSpeed": False, "IsTemperatureProbe": True},
    },
}


def psu_channel(channel, name, **values):
    base = {"channelId": channel, "name": name, "label": name, "rpm": 0, "volts": 0, "amps": 0, "watts": 0,
            "temperatureString": "", "HasSpeed": False, "HasTemps": False, "HasWatts": False, "HasVolts": False,
            "MainPSU": False}
    base.update(values)
    return base


PSU = {
    "serial": "PSU1", "product": "HX1500i", "Template": "psuhid.html", "InputVoltage": 230,
    "DeviceProfile": {"FanMode": 0},
    "FanModes": {"0": "Default", "4": "40 %", "10": "100 %"},
    "devices": {
        "0": psu_channel(0, "HX1500i", watts=110, HasWatts=True, MainPSU=True),
        "1": psu_channel(1, "Fan 1", rpm=0, HasSpeed=True),
        "2": psu_channel(2, "PSU Temperature", temperatureString="40.2 °C", HasTemps=True),
        "4": psu_channel(4, "Power Out", watts=92, HasWatts=True),
        "5": psu_channel(5, "12V Rail", volts=12.15, amps=7.25, watts=82, HasWatts=True, HasVolts=True),
        "6": psu_channel(6, "5V Rail", volts=5.09, amps=2, watts=10, HasWatts=True, HasVolts=True),
    },
}


def key(name, width=65, left=15, top=15, height=70, css="", color=(0, 255, 0), **flags):
    return dict({"keyName": name, "width": width, "height": height, "left": left, "top": top, "css": css,
                 "color": rgb(*color), "onlyColor": False, "noColor": False,
                 # Key assignment: "default" means the key does its normal job
                 "default": True, "actionType": 0, "actionCommand": 0, "actionHold": False,
                 "toggleDelay": 0, "modifierKey": 0, "retainOriginal": False, "deviceId": "",
                 "modifier": False}, **flags)


# /api/input/...: index -> name and Linux key code; the fake uses its own indexes
INPUT_KEYS = {"0": {"Name": "None", "CommandCode": 0}, "101": {"Name": "A", "CommandCode": 30},
              "102": {"Name": "B", "CommandCode": 48}, "103": {"Name": "H", "CommandCode": 35},
              "104": {"Name": "Left Ctrl", "CommandCode": 29}}
MEDIA_KEYS = {"1": {"Name": "Volume Up", "CommandCode": 115}, "2": {"Name": "Volume Down", "CommandCode": 114}}
MOUSE_BUTTONS = {"201": {"Name": "Left Button", "CommandCode": 272}, "202": {"Name": "Right Button", "CommandCode": 273}}
ASSIGNMENT_TYPES = {"0": "None", "1": "Media Keys", "2": "DPI +", "3": "Keyboard", "4": "DPI -", "8": "Sniper",
                    "9": "Mouse", "10": "Macro", "13": "Scroll Up", "21": "Change Profile"}
DIAL_OPTIONS = {1: "Volume Control", 2: "Brightness"}


def initial_macros():
    return {"1": {"id": 1, "name": "Hello", "repeat": 0, "repeatDelay": 0, "actions": {
        "0": {"actionType": 3, "actionCommand": 103, "actionDelay": 0, "actionHold": False, "actionRepeat": 0,
              "actionRepeatDelay": 0, "actionText": "", "mousePositionX": 0, "mousePositionY": 0,
              "mousePositionAbsolute": False},
        "1": {"actionType": 5, "actionCommand": 0, "actionDelay": 50, "actionHold": False, "actionRepeat": 0,
              "actionRepeatDelay": 0, "actionText": "", "mousePositionX": 0, "mousePositionY": 0,
              "mousePositionAbsolute": False}}}}


def initial_keyboard():
    led = dict(width=10, height=40, left=0, top=0, onlyColor=True)
    keys = {
        "0": {"keys": {"1": key("", width=80, left=0, top=0, height=20, css="keyboard-key wide100", onlyColor=True),
                       "2": key("", width=80, left=10, top=0, height=20, css="keyboard-key wide100", onlyColor=True)}},
        "1": {"keys": {"3": key("", css="keyboard-key left-led-1", **led),
                       "4": key("ESC"), "5": key("F1", left=95), "6": key("WH +", noColor=True),
                       "7": key("", css="keyboard-key right-led-1", **led)}},
        "2": {"keys": {"8": key("", css="keyboard-key left-led-2", **led),
                       "9": key("Tab", width=108),
                       "10": key("Q", color=(255, 0, 0), default=False, actionType=3, actionCommand=101),
                       "11": key("+", height=155),
                       "12": key("", css="keyboard-key right-led-2", **led)}},
    }
    return {
        "serial": "KB1", "product": "K100", "firmware": "1.15", "Template": "k100.html",
        "userProfiles": {"default": {"Active": True}, "work": {"Active": False}},
        "DeviceProfile": {"Profile": "default", "Profiles": ["default", "Gaming"], "RGBProfile": "static",
                          "Layout": "US", "PollingRate": 4, "ControlDial": 1, "DebounceTime": 1,
                          "DisableWinKey": False, "DisableShiftTab": False, "DisableAltTab": True,
                          "DisableAltF4": False,
                          "ControlDialColors": {"1": rgb(255, 255, 255), "2": rgb(0, 255, 255)},
                          "Keyboards": {"default": {"row": keys}, "Gaming": {"row": copy.deepcopy(keys)}}},
        "RGBModes": ["keyboard", "rainbow", "static"], "Layouts": ["US", "DE"],
        "PollingRates": {"0": "Not Set", "4": "1000 Hz / 1 msec", "7": "8000 Hz / 0.125 msec"},
        "ControlDialOptions": {"1": "Volume Control", "2": "Brightness"},
        "DebounceTimes": {"1": "1ms", "2": "2ms"},
    }


class State:
    def __init__(self):
        self.profiles = initial_profiles()
        self.effects = {"HUB1": initial_effects(), "KB1": initial_effects()}
        self.psu = copy.deepcopy(PSU)
        self.keyboard = initial_keyboard()
        self.macros = initial_macros()
        self.requests = []
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    state = State()

    def log_message(self, *args):
        pass

    def reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def ok(self, message):
        self.reply({"code": 200, "status": 1, "message": message})

    def refuse(self, message):
        self.reply({"code": 200, "status": 0, "message": message})

    # Reads answer status 0 with their data, like the real OpenLinkHub
    def do_GET(self):
        s = self.state
        if self.path == "/api/temperatures/":
            self.reply({"code": 200, "status": 0, "data": s.profiles})
        elif self.path.startswith("/api/temperatures/graph/"):
            name = self.path.rsplit("/", 1)[1]
            p = s.profiles.get(name)
            if p is None:
                self.reply({"code": 0, "status": 0, "message": "Non-existing speed profile"})
                return
            self.reply({"code": 200, "status": 1, "data": {
                k: {"sensor": p["sensor"], "points": v} for k, v in p["points"].items()}})
        elif self.path == "/api/devices/":
            self.reply({"code": 200, "status": 0, "devices": {
                "HUB1": {"Product": "iCUE LINK System Hub"}, "KB1": {"Product": "K100"},
                "PSU1": {"Product": "HX1500i"}}})
        elif self.path == "/api/devices/HUB1":
            self.reply({"code": 200, "status": 0, "device": HUB})
        elif self.path == "/api/devices/PSU1":
            self.reply({"code": 200, "status": 0, "device": s.psu})
        elif self.keyboard_read():
            pass
        elif self.path == "/api/devices/KB1":
            self.reply({"code": 200, "status": 0, "device": s.keyboard})
        elif self.path.startswith("/api/color/"):
            serial = self.path.rsplit("/", 1)[1]
            if serial not in s.effects:
                self.reply({"code": 200, "status": 0, "message": "No such RGB profile"})
                return
            self.reply({"code": 200, "status": 1, "data": {"device": serial, "profiles": s.effects[serial]}})
        elif self.path == "/api/stats/memory":
            self.reply({"code": 200, "status": 1, "data": {"Total": 34359738368, "Used": 8589934592, "UsedPercent": 25}})
        elif self.path == "/api/storageTemp":
            self.reply({"code": 200, "status": 1, "data": [
                {"Key": "hwmon1", "Model": "Test SSD", "Temperature": 30, "TemperatureString": "30.0 °C"}]})
        elif self.path in ("/api/cpuLoad", "/api/gpuLoad"):
            self.reply({"code": 200, "status": 1, "data": 12})
        else:
            self.reply({"code": 200, "status": 1, "data": "40.0 °C"})

    def data(self, data):
        # Keyboard and macro reads answer status 1, like OpenLinkHub
        self.reply({"code": 200, "status": 1, "data": data})

    def keyboard_keys(self):
        profile = self.state.keyboard["DeviceProfile"]
        for row in profile["Keyboards"][profile["Profile"]]["row"].values():
            for key_id, k in row["keys"].items():
                yield int(key_id), k

    def keyboard_read(self):
        """GETs for key assignments, macros, performance and dial colours; False for other paths."""
        s = self.state
        profile = s.keyboard["DeviceProfile"]
        path = self.path
        if path == "/api/keyboard/assignmentsTypes/KB1":
            self.data(ASSIGNMENT_TYPES)
        elif path == "/api/keyboard/assignmentsModifiers/KB1":
            modifiers = {"0": "None"}
            modifiers.update({str(i): k.get("keyNameInternal") or k["keyName"]
                              for i, k in self.keyboard_keys() if k.get("modifier")})
            self.data(modifiers)
        elif path == "/api/keyboard/getPerformance/KB1":
            self.data([{"name": name, "type": "checkbox", "value": profile[field], "internal": internal}
                       for name, field, internal in (
                           ("Disable Win Key", "DisableWinKey", "perf_winKey"),
                           ("Disable Shift + Tab", "DisableShiftTab", "perf_shiftTab"),
                           ("Disable Alt + Tab", "DisableAltTab", "perf_altTab"),
                           ("Disable Alt + F4", "DisableAltF4", "perf_altF4"))])
        elif path == "/api/keyboard/dial/getColors/KB1":
            self.data([{"Id": int(k), "Name": DIAL_OPTIONS[int(k)], "Color": v}
                       for k, v in sorted(profile["ControlDialColors"].items())])
        elif path == "/api/input/keyboard":
            self.data(INPUT_KEYS)
        elif path == "/api/input/media":
            self.data(MEDIA_KEYS)
        elif path == "/api/input/mouse":
            self.data(MOUSE_BUTTONS)
        elif path == "/api/devices/mouse":
            self.data({"MOUSE1": "M75 WIRELESS"})
        elif path == "/api/device/profiles/KB1":
            self.data(list(s.keyboard["userProfiles"]))
        elif path == "/api/macro/":
            self.data(s.macros)
        elif path.startswith("/api/macro/"):
            self.data(s.macros.get(path.rsplit("/", 1)[1]))
        else:
            return False
        return True

    def macro_change(self, method, body):
        """Macro requests, with the checks of upstream requests.go and macro.go."""
        s = self.state
        m = s.macros.get(str(body.get("macroId", -1)))
        if self.path == "/api/macro/new" and method == "PUT":
            name = body.get("macroName", "")
            if len(name) < 3 or not name.isalnum():
                self.refuse("Invalid macro name")
                return
            if any(v["name"].lower() == name.lower() for v in s.macros.values()):
                self.refuse("Unable to create macro profile")
                return
            new_id = max((int(k) for k in s.macros), default=0) + 1
            s.macros[str(new_id)] = {"id": new_id, "name": name, "repeat": 0, "repeatDelay": 0, "actions": {}}
            self.ok("Macro profile is created")
            return
        if m is None:
            self.refuse("Invalid macro selected")
            return
        if self.path == "/api/macro/profile" and method == "DELETE":
            del s.macros[str(m["id"])]
            self.ok("Macro profile is deleted")
        elif self.path == "/api/macro/value" and method == "DELETE":
            if m["actions"].pop(str(body.get("macroIndex")), None) is None:
                self.refuse("Unable to delete macro profile value")
                return
            self.ok("Macro value is deleted")
        elif self.path == "/api/macro/updateSettings":
            if body.get("macroRepeat", 0) < -1 or body.get("macroRepeatDelay", 0) < 0:
                self.refuse("Invalid macro loop value")
                return
            m["repeat"], m["repeatDelay"] = body["macroRepeat"], body["macroRepeatDelay"]
            self.ok("Macro settings are successfully updated")
        elif self.path == "/api/macro/updateValue":
            action = m["actions"].get(str(body.get("macroIndex")))
            if action is None:
                self.refuse("Unable to update macro profile value")
                return
            if not 0 <= body.get("actionRepeatValue", 0) <= 100:
                self.refuse("Invalid macro repeat value")
                return
            action.update(actionHold=body["pressAndHold"], actionRepeat=body["actionRepeatValue"],
                          actionRepeatDelay=body["actionRepeatDelay"], mousePositionX=body["mousePositionX"],
                          mousePositionY=body["mousePositionY"], mousePositionAbsolute=body["mousePositionAbsolute"])
            self.ok("Macro value is updated")
        elif self.path == "/api/macro/newValue":
            kind = body.get("macroType", 0)
            if not 3 <= kind <= 20 or (kind == 3 and body.get("macroValue", 0) == 0) or (
                    kind == 5 and body.get("macroDelay", 0) < 1) or (kind == 6 and not body.get("macroText")):
                self.refuse("Invalid macro value")
                return
            # Like upstream: the new index is the number of steps, so after a gap it replaces the last one
            m["actions"][str(len(m["actions"]))] = {
                "actionType": kind, "actionCommand": body["macroValue"], "actionDelay": body["macroDelay"],
                "actionHold": False, "actionRepeat": 0, "actionRepeatDelay": 0, "actionText": body["macroText"],
                "mousePositionX": body["mousePositionX"], "mousePositionY": body["mousePositionY"],
                "mousePositionAbsolute": body["mousePositionAbsolute"]}
            self.ok("Macro value is saved")
        else:
            self.refuse("unknown")

    def key_assignment(self, body):
        """updateKeyAssignment with the checks of ProcessChangeKeyAssignment and the K100."""
        kind, hold = body.get("keyAssignmentType", 0), body.get("pressAndHold", False)
        if kind == 10 and hold:
            self.refuse("Press and Hold is not allowed for macros")
            return
        if kind == 8 and not hold:
            self.refuse("Sniper requires Press and Hold")
            return
        for key_id, k in self.keyboard_keys():
            if key_id == body.get("keyIndex"):
                if k["onlyColor"]:
                    self.refuse("Unable to apply key assignment")
                    return
                # The K100 keeps these fields; it ignores the modifier and "retain original"
                k.update({"default": body.get("enabled", False), "actionType": kind,
                          "actionCommand": body.get("keyAssignmentValue", 0),
                          "deviceId": body.get("keyAssignmentValueString", ""), "actionHold": hold,
                          "toggleDelay": max(30, body.get("toggleDelay", 0))})
                self.ok("Key assignment is updated")
                return
        self.refuse("Unable to apply key assignment")

    def keyboard_change(self, body):
        """Applies a keyboard request to the fake state, with the checks OpenLinkHub does."""
        kb = self.state.keyboard
        profile = kb["DeviceProfile"]
        name = body.get("keyboardProfileName", "")
        if self.path == "/api/keyboard/updateKeyAssignment":
            self.key_assignment(body)
            return
        if self.path == "/api/keyboard/setPerformance":
            for field, internal in (("DisableWinKey", "perf_winKey"), ("DisableShiftTab", "perf_shiftTab"),
                                    ("DisableAltTab", "perf_altTab"), ("DisableAltF4", "perf_altF4")):
                profile[field] = bool(body.get(internal, False))
            self.ok("Keyboard performance is updated")
            return
        if self.path == "/api/keyboard/dial/setColors":
            for zone, color in (body.get("colorZones") or {}).items():
                if zone in profile["ControlDialColors"]:
                    profile["ControlDialColors"][zone] = rgb(color["red"], color["green"], color["blue"])
            self.ok("Control dial is updated")
            return
        if self.path == "/api/keyboard/color":
            if body.get("keyOption") != 3 or not body.get("keys"):
                self.refuse("Invalid key selected")
                return
            for row in profile["Keyboards"][profile["Profile"]]["row"].values():
                for key_id, k in row["keys"].items():
                    if int(key_id) in body["keys"]:
                        k["color"] = rgb(body["color"]["red"], body["color"]["green"], body["color"]["blue"])
        elif self.path == "/api/color":
            profile["RGBProfile"] = body["profile"]
        elif self.path == "/api/keyboard/profile/change":
            if name not in profile["Profiles"]:
                self.refuse("Non-existing profile")
                return
            profile["Profile"] = name
        elif self.path == "/api/keyboard/profile/new":
            if not name.isalnum():
                self.refuse("Profile name can only contain letters and numbers")
                return
            profile["Keyboards"][name] = copy.deepcopy(profile["Keyboards"][profile["Profile"]])
            profile["Profiles"].append(name)
            profile["Profile"] = name
        elif self.path == "/api/keyboard/profile/delete":
            if name == "default" or name not in profile["Profiles"]:
                self.refuse("Unable to delete profile")
                return
            profile["Profiles"].remove(name)
            del profile["Keyboards"][name]
            profile["Profile"] = "default"
        elif self.path == "/api/userProfile/change":
            for key_name, p in kb["userProfiles"].items():
                p["Active"] = key_name == body["userProfileName"]
        elif self.path == "/api/keyboard/layout":
            profile["Layout"] = body["keyboardLayout"]
        elif self.path == "/api/keyboard/pollingRate":
            profile["PollingRate"] = body["pollingRate"]
        elif self.path == "/api/keyboard/dial":
            profile["ControlDial"] = body["keyboardControlDial"]
        elif self.path == "/api/keyboard/debounceTime":
            profile["DebounceTime"] = body["debounceTime"]
        self.ok("Done")

    def do_PUT(self):
        s = self.state
        body = self.body()
        with s.lock:
            s.requests.append(("PUT", self.path, body))
            if self.path.startswith("/api/macro/"):
                self.macro_change("PUT", body)
                return
            if self.path.startswith("/api/keyboard/"):
                self.keyboard_change(body)
                return
            if self.path == "/api/color/change":
                fx = s.effects.get(body.get("deviceId"), {}).get(body.get("profile"))
                if fx is None:
                    self.refuse("Non-existing profile")
                    return
                if not 1 <= body.get("speed", 0) <= 10:
                    self.refuse("Invalid speed")
                    return
                fx.update(start=body["startColor"], middle=body["middleColor"], end=body["endColor"],
                          speed=body["speed"], alternateColors=body["alternateColors"],
                          rgbDirection=body["rgbDirection"])
                if "colorZones" in body:
                    fx["gradients"] = body["colorZones"]
                self.ok("RGB profile is updated")
                return
            if self.path == "/api/temperatures/updateGraph":
                p = s.profiles.get(body.get("profile"))
                if p is None:
                    self.refuse("Non-existing speed profile")
                    return
                if body.get("updateType") not in (0, 1):
                    self.refuse("Invalid update type")
                    return
                p["points"][str(body["updateType"])] = body["points"]
                self.ok("Speed profile is updated")
            else:
                self.refuse("unknown")

    def do_POST(self):
        s = self.state
        body = self.body()
        with s.lock:
            s.requests.append(("POST", self.path, body))
            if self.path.startswith("/api/macro/"):
                self.macro_change("POST", body)
                return
            if self.path.startswith("/api/keyboard/") or self.path == "/api/userProfile/change" or (
                    self.path == "/api/color" and body.get("deviceId") == "KB1"):
                self.keyboard_change(body)
                return
            if self.path == "/api/psu/speed":
                if body.get("deviceId") != "PSU1" or not 0 <= body.get("fanMode", -1) <= 10:
                    self.refuse("Invalid fan mode")
                    return
                s.psu["DeviceProfile"]["FanMode"] = body["fanMode"]
                self.ok("Fan mode is changed")
                return
            if self.path == "/api/temperatures/new":
                name = body.get("profile", "")
                if name in s.profiles:
                    self.refuse("Profile already exists")
                    return
                s.profiles[name] = {"sensor": body.get("sensor", 0), "sensorString": "CPU",
                                    "linear": body.get("linear", False), "zeroRpm": body.get("zeroRpm", False),
                                    "Hidden": False, "profiles": [{"id": 1, "min": 0, "max": 200}],
                                    "points": {"0": copy.deepcopy(PUMP_CURVE), "1": copy.deepcopy(CPU_CURVE)}}
                self.ok("Speed profile is saved")
            else:
                self.ok("Done")

    def do_DELETE(self):
        s = self.state
        body = self.body()
        with s.lock:
            s.requests.append(("DELETE", self.path, body))
            if self.path.startswith("/api/macro/"):
                self.macro_change("DELETE", body)
                return
            if self.path.startswith("/api/keyboard/"):
                self.keyboard_change(body)
                return
            if s.profiles.pop(body.get("profile"), None) is None:
                self.refuse("Non-existing speed profile")
            else:
                self.ok("Speed profile is deleted")


def start(port=0):
    """Starts a fresh fake in a thread; returns (server, url, state)."""
    Handler.state = State()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d" % server.server_port, Handler.state


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 27099
    Handler.state = State()
    print("Fake OpenLinkHub on http://127.0.0.1:%d" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
