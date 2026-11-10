# quartercore-core HTTP server: OpenLinkHub's API for own devices, the rest passed on
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Quartercore points at this server (default http://127.0.0.1:27013) instead
# of OpenLinkHub. Requests for a device quartercore-core drives are answered
# here, in OpenLinkHub's format; everything else goes on to OpenLinkHub
# (http://127.0.0.1:27003), and web pages are redirected there.
#
# Safety: a device is only taken over when OpenLinkHub runs and doesn't list
# it (it was turned off in OpenLinkHub's supported devices), or in standalone
# mode (no OpenLinkHub at all). So two programs never drive one device.

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .. import __version__

CHECK_INTERVAL = 10
REFRESH_INTERVAL = 1
PROXY_TIMEOUT = 10


class Core:
    def __init__(self, openlinkhub, discover, standalone=False, log=print):
        self.openlinkhub = openlinkhub.rstrip("/")
        self.discover = discover
        self.standalone = standalone
        self.log = log
        self.lock = threading.RLock()
        self.drivers = {}        # serial -> driver, for every device found
        self.owned = set()       # serials quartercore-core drives now
        self.openlinkhub_up = False
        self.stopping = threading.Event()

    # --- OpenLinkHub ---

    def openlinkhub_devices(self):
        """Serials OpenLinkHub drives, or None when it doesn't answer."""
        try:
            with urllib.request.urlopen(self.openlinkhub + "/api/devices/", timeout=5) as reply:
                data = json.loads(reply.read())
            return set((data.get("devices") or {}).keys())
        except (OSError, ValueError):
            return None

    def check(self):
        """Finds devices and takes over the ones OpenLinkHub leaves alone."""
        listed = self.openlinkhub_devices()
        self.openlinkhub_up = listed is not None
        with self.lock:
            for driver in self.discover():
                self.drivers.setdefault(driver.serial, driver)
            for serial, driver in self.drivers.items():
                free = self.standalone or (listed is not None and serial not in listed)
                if free and serial not in self.owned:
                    self.log("taking over %s (%s)" % (driver.product, serial))
                    driver.start()
                    driver.refresh()
                    self.owned.add(serial)
                elif not free and serial in self.owned and listed is not None:
                    # OpenLinkHub drives it again: let go without sending anything
                    self.log("OpenLinkHub drives %s again, letting go" % serial)
                    if driver.device is not None:
                        driver.device.close()
                        driver.device = None
                    self.owned.discard(serial)

    def run(self):
        last_check = 0
        while not self.stopping.is_set():
            if time.monotonic() - last_check >= CHECK_INTERVAL:
                last_check = time.monotonic()
                try:
                    self.check()
                except Exception as e:  # keep the service alive, report the problem
                    self.log("check failed: %s" % e)
            with self.lock:
                owned = [self.drivers[s] for s in self.owned]
            for driver in owned:
                driver.refresh()
            self.stopping.wait(REFRESH_INTERVAL)

    def stop(self):
        self.stopping.set()
        with self.lock:
            for serial in list(self.owned):
                self.drivers[serial].stop()
            self.owned.clear()

    def driver(self, serial):
        with self.lock:
            return self.drivers.get(serial) if serial in self.owned else None


def make_handler(core):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def reply(self, body, code=200):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def body(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                return raw, json.loads(raw or b"{}")
            except ValueError:
                return raw, {}

        def proxy(self, method, raw=b""):
            if not self.path.startswith("/api/"):
                # Web pages: OpenLinkHub's own interface
                self.send_response(302)
                self.send_header("Location", core.openlinkhub + self.path)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            request = urllib.request.Request(core.openlinkhub + self.path, data=raw if method != "GET" else None,
                                             method=method, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=PROXY_TIMEOUT) as answer:
                    data, code = answer.read(), answer.status
            except urllib.error.HTTPError as e:
                data, code = e.read(), e.code
            except OSError:
                self.reply({"code": 0, "status": 0, "message": "OpenLinkHub is not available"}, 502)
                return
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path
            if path == "/api/core":
                with core.lock:
                    owned = {s: core.drivers[s].product for s in core.owned}
                self.reply({"code": 200, "status": 1, "data": {
                    "version": __version__, "openlinkhub": core.openlinkhub, "openlinkhubUp": core.openlinkhub_up,
                    "standalone": core.standalone, "devices": owned}})
                return
            if path == "/api/devices/":
                listed = {}
                if core.openlinkhub_up:
                    try:
                        with urllib.request.urlopen(core.openlinkhub + path, timeout=PROXY_TIMEOUT) as answer:
                            listed = json.loads(answer.read()).get("devices") or {}
                    except (OSError, ValueError):
                        listed = {}
                with core.lock:
                    for serial in core.owned:
                        listed[serial] = core.drivers[serial].summary()
                self.reply({"code": 200, "status": 0, "devices": listed})
                return
            if path.startswith("/api/devices/"):
                driver = core.driver(path.rsplit("/", 1)[1])
                if driver is not None:
                    self.reply({"code": 200, "status": 0, "device": driver.device_json()})
                    return
            self.proxy("GET")

        def do_POST(self):
            raw, body = self.body()
            driver = core.driver(str(body.get("deviceId") or ""))
            if driver is not None:
                if self.path == "/api/psu/speed":
                    error = driver.set_fan_mode(int(body.get("fanMode", -1)))
                    self.reply({"code": 200, "status": 0 if error else 1,
                                "message": error or "Fan mode is changed"})
                else:
                    self.reply({"code": 200, "status": 0, "message": "Not supported by quartercore-core yet"})
                return
            self.proxy("POST", raw)

        def do_PUT(self):
            raw, _ = self.body()
            self.proxy("PUT", raw)

        def do_DELETE(self):
            raw, _ = self.body()
            self.proxy("DELETE", raw)

    return Handler


def serve(core, port, host="127.0.0.1"):
    server = ThreadingHTTPServer((host, port), make_handler(core))
    server.daemon_threads = True
    return server
