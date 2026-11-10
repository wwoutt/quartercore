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


class State:
    def __init__(self):
        self.profiles = initial_profiles()
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
            self.reply({"code": 200, "status": 0, "devices": {}})
        elif self.path == "/api/stats/memory":
            self.reply({"code": 200, "status": 1, "data": {"Total": 34359738368, "Used": 8589934592, "UsedPercent": 25}})
        elif self.path == "/api/storageTemp":
            self.reply({"code": 200, "status": 1, "data": [
                {"Key": "hwmon1", "Model": "Test SSD", "Temperature": 30, "TemperatureString": "30.0 °C"}]})
        elif self.path in ("/api/cpuLoad", "/api/gpuLoad"):
            self.reply({"code": 200, "status": 1, "data": 12})
        else:
            self.reply({"code": 200, "status": 1, "data": "40.0 °C"})

    def do_PUT(self):
        s = self.state
        body = self.body()
        with s.lock:
            s.requests.append(("PUT", self.path, body))
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
