# Tests for step F1: the LINK hub speeds quartercore-core works out without setting them
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests
# Fixed temperatures and profiles; nothing reads or writes a real hub.

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_openlinkhub  # noqa: E402
from quartercore.core import cooling  # noqa: E402
from quartercore.core.server import Core, serve  # noqa: E402

# The user's "Normal" profile: pump curve 0, fan curve 1 (CPU sensor)
NORMAL = {"sensor": 0, "zeroRpm": False, "points": {
    "0": [{"x": 0, "y": 70}, {"x": 70, "y": 70}, {"x": 80, "y": 80}, {"x": 90, "y": 90}, {"x": 200, "y": 100}],
    "1": [{"x": 0, "y": 30}, {"x": 40, "y": 40}, {"x": 50, "y": 40}, {"x": 60, "y": 45}, {"x": 70, "y": 55},
          {"x": 80, "y": 70}, {"x": 90, "y": 90}, {"x": 200, "y": 100}]}}
FAN = {"channelId": 1, "name": "iCUE LINK RX RGB", "profile": "Normal", "rpm": 685, "HasSpeed": True, "AIO": False}
TITAN = {"channelId": 19, "name": "iCUE LINK TITAN 360", "profile": "Normal", "rpm": 2394, "temperature": 26,
         "HasSpeed": True, "AIO": True, "TitanAIO": True}
PROBE = {"channelId": 7, "name": "Probe", "HasSpeed": False, "IsTemperatureProbe": True, "temperature": 31}


class FakeTemps:
    def __init__(self, cpu=41.0, gpu=39.0):
        self.cpu_value, self.gpu_value = cpu, gpu

    def cpu(self):
        return self.cpu_value

    def gpu(self):
        return self.gpu_value


class CurveTest(unittest.TestCase):
    def test_interpolate_like_upstream(self):
        points = NORMAL["points"]["1"]
        self.assertEqual(cooling.interpolate(points, -5), 30)
        self.assertEqual(cooling.interpolate(points, 45), 40)
        self.assertEqual(cooling.interpolate(points, 65), 50)
        self.assertEqual(cooling.interpolate(points, 500), 100)
        self.assertEqual(cooling.interpolate([], 50), 0)
        self.assertEqual(cooling.interpolate(list(reversed(points)), 55), 42.5)      # sorted first

    def test_go_round(self):
        self.assertEqual((cooling.go_round(42.5), cooling.go_round(42.4), cooling.go_round(-1.5)), (43, 42, -2))

    def test_fans_and_pump(self):
        self.assertEqual(cooling.speed(FAN, NORMAL, 41), 40)
        self.assertEqual(cooling.speed(FAN, NORMAL, 55), 43)            # 42.5 rounds up, like math.Round
        self.assertEqual(cooling.speed(TITAN, NORMAL, 26), 70)          # the AIO follows the pump curve
        self.assertEqual(cooling.speed(TITAN, NORMAL, 85), 85)

    def test_failsafes(self):
        low = {"sensor": 0, "zeroRpm": False, "points": {"0": [{"x": 0, "y": 10}], "1": [{"x": 0, "y": 5}]}}
        self.assertEqual(cooling.speed(FAN, low, 40), 20)                # fans at least 20 %
        self.assertEqual(cooling.speed(FAN, dict(low, zeroRpm=True), 40), 5)
        self.assertEqual(cooling.speed(TITAN, low, 40), 31)              # TITAN pump at least 31 %
        other_aio = dict(TITAN, TitanAIO=False)
        self.assertEqual(cooling.speed(other_aio, low, 40), 70)          # other AIOs: under 50 -> 70
        pump = {"channelId": 3, "name": "XD5 PUMP", "HasSpeed": True, "AIO": False}
        self.assertEqual(cooling.speed(pump, low, 40), 30)               # pumps: under 20 -> 30
        high = {"points": {"0": [{"x": 0, "y": 150}], "1": [{"x": 0, "y": 150}]}}
        self.assertEqual((cooling.speed(FAN, high, 40), cooling.speed(TITAN, high, 40)), (100, 100))

    def test_steps_without_graph_profiles(self):
        steps = {"profiles": [{"min": 0, "max": 40, "fans": 30, "pump": 70}, {"min": 40, "max": 60, "fans": 45,
                                                                                "pump": 10}]}
        self.assertEqual(cooling.speed(FAN, steps, 41, graph=False), 45)
        self.assertEqual(cooling.speed(TITAN, steps, 41, graph=False), 70)
        self.assertIsNone(cooling.speed(FAN, steps, 99, graph=False))

    def test_sensors(self):
        devices = {"19": TITAN, "7": PROBE}
        readings = {"cpu": 41.0, "gpu": 0}
        self.assertEqual(cooling.sensor_temperature({"sensor": 0}, devices, readings), 41.0)
        self.assertEqual(cooling.sensor_temperature({"sensor": 2}, devices, readings), 26.0)       # liquid
        self.assertEqual(cooling.sensor_temperature({"sensor": 4, "channelId": 7}, devices, readings), 31.0)
        self.assertEqual(cooling.sensor_temperature({"sensor": 1}, devices, readings), 41.0)       # no GPU: CPU
        self.assertEqual(cooling.sensor_temperature({"sensor": 5}, devices, readings), 50.0)       # max(CPU, 50)
        self.assertEqual(cooling.sensor_temperature({"sensor": 0}, devices, {"cpu": 0}), 50.0)     # failed: 50
        self.assertIsNone(cooling.sensor_temperature({"sensor": 7}, devices, readings))            # a program

    def test_plan(self):
        hub = {"devices": {"1": FAN, "19": TITAN, "7": PROBE}}
        out = cooling.plan(hub, {"Normal": NORMAL}, {"cpu": 41.0, "gpu": 39.0})
        self.assertEqual(sorted(out, key=int), ["1", "19"])                                       # probe: no speed
        self.assertEqual((out["1"]["speed"], out["1"]["sensor"], out["1"]["rpm"]), (40, "CPU", 685))
        self.assertEqual(out["19"]["speed"], 70)
        unknown = dict(FAN, profile="Gone")
        self.assertEqual(cooling.plan({"devices": {"1": unknown}}, {"Normal": NORMAL}, {"cpu": 41})["1"]["speed"], 40)


class ShadowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hub = {"serial": "HUBX", "CpuTemp": 41.0, "GpuTemp": 39.0, "devices": {"1": FAN, "19": TITAN}}
        self.temps = FakeTemps()
        answers = {"/api/devices/": {"devices": {"HUBX": {"Product": "iCUE LINK System Hub"},
                                                 "KB": {"Product": "K100"}}},
                   "/api/temperatures/": {"data": {"Normal": NORMAL, "aioCriticalTemperature": NORMAL,
                                                   "graphProfiles": True}},
                   "/api/devices/HUBX": {"device": self.hub}}
        self.shadow = cooling.Shadow("http://olh", self.temps, lambda url: answers[url[len("http://olh"):]],
                                     clock=lambda: 1000, log_folder=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def lines(self):
        return [json.loads(l) for l in (Path(self.tmp.name) / "cooling-shadow.jsonl").read_text().splitlines()]

    def test_tick_and_log(self):
        self.shadow.tick()
        status = self.shadow.status("HUBX")
        self.assertEqual((status["cpu"], status["openlinkhubCpu"]), (41.0, 41.0))
        self.assertEqual({k: c["speed"] for k, c in status["channels"].items()}, {"1": 40, "19": 70})
        self.shadow.tick()
        self.assertEqual(len(self.lines()), 1)                    # only changes are written
        self.temps.cpu_value = 65.0                               # our reading differs from OpenLinkHub's
        self.shadow.tick()
        line = self.lines()[-1]
        self.assertEqual((line["channels"]["1"]["speed"], line["channels"]["1"]["openlinkhub"]), (50, 40))
        self.assertEqual(self.shadow.status()["error"], "")

    def test_openlinkhub_away(self):
        def fail(url):
            raise OSError("connection refused")
        shadow = cooling.Shadow("http://olh", self.temps, fail, log_folder=self.tmp.name)
        shadow.tick()
        self.assertIn("refused", shadow.status()["error"])
        self.assertEqual(shadow.status()["hubs"], {})


class ServerTest(unittest.TestCase):
    def test_the_hub_page_gets_the_shadow(self):
        olh, olh_url, state = fake_openlinkhub.start()

        class Stub:
            def status(self, serial=None):
                data = {"cpu": 41.0, "openlinkhubCpu": 41.0, "channels": {"1": {"speed": 40}},
                        "openlinkhubChannels": {"1": {"speed": 40}}}
                return data if serial == "HUB1" else ({"hubs": {"HUB1": data}} if serial is None else None)
        core = Core(olh_url, lambda: [], log=lambda text: None, shadow=Stub())
        core.check()
        server = serve(core, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d" % server.server_port
        try:
            with urllib.request.urlopen(url + "/api/devices/HUB1", timeout=5) as reply:
                device = json.loads(reply.read())["device"]
            self.assertEqual(device["QuartercoreShadow"]["channels"]["1"]["speed"], 40)
            self.assertEqual(device["product"], "iCUE LINK System Hub")
            with urllib.request.urlopen(url + "/api/core/cooling", timeout=5) as reply:
                self.assertIn("HUB1", json.loads(reply.read())["data"]["hubs"])
            with urllib.request.urlopen(url + "/api/devices/KB1", timeout=5) as reply:
                self.assertNotIn("QuartercoreShadow", json.loads(reply.read())["device"])
            from quartercore.backend import link_hub_view
            view = link_hub_view(device)
            channel = next(c for c in view["channels"] if c["channelId"] == 1)
            self.assertEqual((view["shadow"], channel["shadowSpeed"], channel["shadowDiffers"]), (True, 40, False))
            other = next(c for c in view["channels"] if c["channelId"] == 2)
            self.assertEqual(other["shadowSpeed"], -1)
        finally:
            server.shutdown()
            server.server_close()
            olh.shutdown()
            olh.server_close()


if __name__ == "__main__":
    unittest.main()
