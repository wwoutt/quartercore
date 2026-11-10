# Tests for the API client and backend against a fake OpenLinkHub
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402

from quartercore.backend import Backend, link_hub_view  # noqa: E402

HUB = {
    "serial": "HUB1", "product": "iCUE LINK System Hub", "firmware": "1.0", "Template": "lsh.html",
    "DeviceProfile": {"BrightnessSlider": 40},
    "RGBModes": ["off", "static"],
    "devices": {
        "13": {"name": "iCUE LINK RX RGB", "label": "Front", "description": "Fan", "rpm": 700,
               "temperatureString": "", "profile": "Normal", "rgb": "static", "HasSpeed": True},
        "2": {"name": "iCUE LINK TITAN 360", "label": "Set Label", "description": "AIO", "rpm": 2400,
              "temperatureString": "26.5 °C", "profile": "Quiet", "rgb": "off", "HasSpeed": True},
    },
}


class FakeOpenLinkHub(BaseHTTPRequestHandler):
    posted = []

    def log_message(self, *args):
        pass

    def reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        # Reads answer status 0 with their data, like the real OpenLinkHub
        if self.path == "/api/devices/":
            self.reply({"code": 200, "status": 0, "devices": {
                "HUB1": {"Product": "iCUE LINK System Hub"},
                "HID": {"Product": "Dongle", "Hidden": True}}})
        elif self.path == "/api/devices/HUB1":
            self.reply({"code": 200, "status": 0, "device": HUB})
        elif self.path == "/api/temperatures/":
            self.reply({"code": 200, "status": 1, "data": {
                "Quiet": {"Hidden": False}, "Normal": {"Hidden": False}, "aioCritical": {"Hidden": True}}})
        else:
            self.reply({"code": 200, "status": 1, "data": "30.0 °C"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOpenLinkHub.posted.append((self.path, body))
        if body.get("profile") == "Missing":
            self.reply({"code": 200, "status": 0, "message": "Non-existing speed profile"})
        else:
            self.reply({"code": 200, "status": 1, "message": "Done"})


def wait(condition, timeout_ms=3000):
    loop = QEventLoop()
    timer = QTimer(interval=20, timeout=lambda: condition() and loop.quit())
    timer.start()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    timer.stop()
    return condition()


class BackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenLinkHub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeOpenLinkHub.posted.clear()
        self.backend = Backend(self.url)
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))

    def test_link_hub_view(self):
        view = link_hub_view(HUB)
        self.assertEqual([c["channelId"] for c in view["channels"]], [2, 13])
        self.assertEqual(view["channels"][0]["label"], "")  # "Set Label" means no label
        self.assertEqual(view["channels"][1]["label"], "Front")
        self.assertEqual(view["brightness"], 40)

    def test_devices_and_speed_profiles(self):
        self.backend.start()
        self.assertTrue(wait(lambda: self.backend.devices and self.backend.devices[0]["page"] == "linkhub"))
        self.assertEqual([d["serial"] for d in self.backend.devices], ["HUB1"])  # hidden left out
        self.assertTrue(wait(lambda: self.backend.speedProfiles == ["Normal", "Quiet"]))
        self.assertTrue(self.backend.connected)

    def select_hub(self):
        self.backend.selectDevice("HUB1")
        self.assertTrue(wait(lambda: self.backend.active.get("page") == "linkhub"))

    def test_changes_send_the_web_ui_requests(self):
        self.select_hub()
        self.backend.setSpeedProfile(13, "Quiet")
        self.backend.setRgbProfile(2, "off")
        self.backend.setLabel(2, "  Pump  ")
        self.backend.setBrightness(150)
        self.assertTrue(wait(lambda: len(FakeOpenLinkHub.posted) == 4))
        self.assertEqual(sorted(FakeOpenLinkHub.posted, key=lambda p: p[0]), [
            ("/api/brightness/gradual", {"deviceId": "HUB1", "brightness": 100}),
            ("/api/color", {"deviceId": "HUB1", "channelId": 2, "profile": "off"}),
            ("/api/label", {"deviceId": "HUB1", "channelId": 2, "deviceType": 0, "label": "Pump"}),
            ("/api/speed", {"deviceId": "HUB1", "channelId": 13, "profile": "Quiet"}),
        ])
        self.assertTrue(wait(lambda: len(self.messages) == 4))
        self.assertTrue(all(ok for _, ok in self.messages))

    def test_all_channels(self):
        self.select_hub()
        self.backend.setAllSpeedProfiles("Normal")
        self.assertTrue(wait(lambda: len(FakeOpenLinkHub.posted) == 2))
        self.assertEqual(sorted(b["channelId"] for _, b in FakeOpenLinkHub.posted), [2, 13])

    def test_refused_change_is_reported(self):
        self.select_hub()
        self.backend.setSpeedProfile(13, "Missing")
        self.assertTrue(wait(lambda: self.messages))
        self.assertEqual(self.messages[0], ("Non-existing speed profile", False))

    def test_empty_label_is_not_sent(self):
        self.select_hub()
        self.backend.setLabel(2, "   ")
        self.assertEqual(self.messages, [("A label can't be empty", False)])
        self.assertEqual(FakeOpenLinkHub.posted, [])

    def test_unreachable_server(self):
        backend = Backend("http://127.0.0.1:1")
        backend.refresh()
        self.assertTrue(wait(lambda: backend.error != ""))
        self.assertFalse(backend.connected)


if __name__ == "__main__":
    unittest.main()
