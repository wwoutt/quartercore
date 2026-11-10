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
                 "color": rgb(*color), "onlyColor": False, "noColor": False}, **flags)


def initial_keyboard():
    led = dict(width=10, height=40, left=0, top=0, onlyColor=True)
    keys = {
        "0": {"keys": {"1": key("", width=80, left=0, top=0, height=20, css="keyboard-key wide100", onlyColor=True),
                       "2": key("", width=80, left=10, top=0, height=20, css="keyboard-key wide100", onlyColor=True)}},
        "1": {"keys": {"3": key("", css="keyboard-key left-led-1", **led),
                       "4": key("ESC"), "5": key("F1", left=95), "6": key("WH +", noColor=True),
                       "7": key("", css="keyboard-key right-led-1", **led)}},
        "2": {"keys": {"8": key("", css="keyboard-key left-led-2", **led),
                       "9": key("Tab", width=108), "10": key("Q", color=(255, 0, 0)), "11": key("+", height=155),
                       "12": key("", css="keyboard-key right-led-2", **led)}},
    }
    return {
        "serial": "KB1", "product": "K100", "firmware": "1.15", "Template": "k100.html",
        "userProfiles": {"default": {"Active": True}, "work": {"Active": False}},
        "DeviceProfile": {"Profile": "default", "Profiles": ["default", "Gaming"], "RGBProfile": "static",
                          "Layout": "US", "PollingRate": 4, "ControlDial": 1, "DebounceTime": 1,
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

    def keyboard_change(self, body):
        """Applies a keyboard request to the fake state, with the checks OpenLinkHub does."""
        kb = self.state.keyboard
        profile = kb["DeviceProfile"]
        name = body.get("keyboardProfileName", "")
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
