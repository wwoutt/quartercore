# Tests for the own XENEON EDGE widgets: network, power, GPU details, processes, system, Home Assistant
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests
# Fake /proc files, a fake nvidia-smi line and the fake Home Assistant of fake_openlinkhub.py.

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QObject, Signal  # noqa: E402

import fake_openlinkhub  # noqa: E402
from quartercore import edge as e, edgelayout, homeassistant as ha, sensors  # noqa: E402
from test_backend import wait  # noqa: E402

NET = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000  10    0    0    0     0          0         0 1000  10    0    0    0     0       0          0
enp5s0: %d 2196660    0  263    0     0          0     49631 %d  347151    0    0    0     0       0          0
  wlo1:       0       0    0    0    0     0          0         0        0       0    0    0    0     0       0          0
"""


class FakeSettings(QObject):
    changed = Signal()

    def __init__(self, url="", token=""):
        super().__init__()
        self.haUrl, self.haToken = url, token


class SensorTest(unittest.TestCase):
    def test_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dev"
            path.write_text(NET % (1000000, 50000))
            self.assertEqual(sensors.network_counters(path), {"enp5s0": (1000000, 50000), "wlo1": (0, 0)})
            now = [10.0]
            rate = sensors.NetworkRate(path, clock=lambda: now[0])
            self.assertIsNone(rate.read())                            # the first read only remembers
            path.write_text(NET % (3000000, 150000))
            now[0] = 12.0
            self.assertEqual(rate.read(), (1000000.0, 50000.0))       # bytes per second over 2 s
            self.assertIsNone(rate.read("enp5s0"))                    # another interface starts again
            self.assertIsNone(rate.read("eth9"))
        self.assertEqual(sensors.format_rate(1234567), "1.2 MB/s")
        self.assertEqual(sensors.format_rate(1234567, bits=True), "9.9 Mbit/s")
        self.assertEqual(sensors.format_rate(512), "512 B/s")
        self.assertEqual(sensors.format_rate(None), "–")

    def test_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def proc(pid, name, ticks, pages):
                (root / str(pid)).mkdir(exist_ok=True)
                fields = ["S"] + ["0"] * 10 + [str(ticks), "0"] + ["0"] * 30
                (root / str(pid) / "stat").write_text("%d (%s) %s\n" % (pid, name, " ".join(fields)))
                (root / str(pid) / "statm").write_text("100 %d 0 0 0 0 0\n" % pages)
            proc(1, "systemd", 100, 1000)
            proc(42, "my game (x)", 100, 200000)
            (root / "self").mkdir()
            now = [0.0]
            top = sensors.ProcessTop(root, clock=lambda: now[0])
            top.ticks, top.page, top.cpus = 100, 4096, 2
            first = top.read("cpu", 2)
            self.assertEqual([r["cpu"] for r in first], [None, None])
            proc(42, "my game (x)", 300, 200000)                      # 200 ticks = 2 s CPU in 1 s on 2 cores
            now[0] = 1.0
            rows = top.read("cpu", 2)
            self.assertEqual((rows[0]["name"], rows[0]["cpu"]), ("my game (x)", 100.0))
            self.assertEqual(top.read("memory", 1)[0]["memory"], 200000 * 4096)

    def test_system_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "uptime").write_text("7843.79 207050.11\n")
            (root / "loadavg").write_text("1.70 1.45 1.33 2/2148 144819\n")
            (root / "cpuinfo").write_text("processor\t: 0\nmodel name\t: Intel(R) Core(TM) i7-14700K\n")
            (root / "os-release").write_text('NAME="Bazzite"\nPRETTY_NAME="Bazzite"\n')
            info = sensors.system_info(root, root / "os-release")
        self.assertEqual((info["os"], info["cpu"], info["uptime"], info["load"], info["processes"]),
                         ("Bazzite", "Intel(R) Core(TM) i7-14700K", 7843.79, [1.7, 1.45, 1.33], 2148))
        view = e.system_view(info)
        self.assertEqual((view["uptime"], view["load"]), ("2 h 10 min", "1.70  1.45  1.33"))
        self.assertEqual(e.uptime_text(200000), "2 d 7 h")

    def test_nvidia_details(self):
        line = "44, 45, NVIDIA GeForce RTX 3080 Ti, 42, 2528, 12288, 43.33, 400.00, 585, 810, [N/A]\n"
        temperature, load, details = sensors.parse_nvidia_details(line)
        self.assertEqual((temperature, load, details["name"], details["memoryUsed"], details["fan"]),
                         (44.0, 45.0, "NVIDIA GeForce RTX 3080 Ti", 2528.0, None))
        self.assertEqual(sensors.parse_nvidia("39, 23\n"), (39.0, 23.0))     # the old two fields still work
        view = e.gpu_details_view(temperature, load, details, {"unit": "°C"})
        self.assertEqual((view["memory"], view["power"], view["clock"], view["fan"]),
                         ("2.5 / 12.0 GB", "43 W / 400 W", "585 MHz", "–"))
        self.assertFalse(e.gpu_details_view(None, None, {}, {})["available"])


class ViewTest(unittest.TestCase):
    def test_network_view(self):
        history = [(1000000.0, 50000.0), (2000000.0, 100000.0)]
        view = e.network_view(history, {"rateUnit": "bytes"})
        self.assertEqual((view["down"], view["up"], view["peak"]), ("2.0 MB/s", "100 kB/s", "2.0 MB/s"))
        self.assertEqual(view["downHistory"], [0.5, 1.0])
        self.assertFalse(e.network_view([], {})["available"])

    def test_power_view(self):
        psu = {"product": "HX1500i", "power": 160.0, "outputPower": 144.0}
        view = e.power_view(psu, [80.0, 160.0], {"pricePerKwh": "0.30", "currency": "€"})
        self.assertEqual((view["watts"], view["output"], view["efficiency"], view["costHour"], view["costDay"]),
                         ("160 W", "144 W", "90 %", "€ 0.05", "€ 1.15"))
        self.assertEqual(view["history"], [0.5, 1.0])
        self.assertEqual(e.power_view(psu, [], {"pricePerKwh": 0})["costHour"], "")
        self.assertFalse(e.power_view(None, [], {})["available"])

    def test_processes_view(self):
        rows = [{"name": "game", "cpu": 12.34, "memory": 2 ** 30}, {"name": "new", "cpu": None, "memory": 1024}]
        self.assertEqual(e.processes_view(rows)["rows"], [{"name": "game", "cpu": "12.3 %", "memory": "1.0 GiB"},
                                                          {"name": "new", "cpu": "…", "memory": "1.0 KiB"}])

    def test_default_settings_are_valid(self):
        for widget_id in range(17, 24):
            settings = e.widget_settings(widget_id)
            self.assertIsNone(edgelayout.check_settings(settings), settings["template"])
        bad = dict(e.widget_settings(21), count=99)
        self.assertEqual(edgelayout.check_settings(bad), "Number of processes")


class HomeAssistantTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, self.url, self.state = fake_openlinkhub.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_helpers(self):
        self.assertEqual(ha.entity_list("light.desk, sensor.t\nswitch.fan, light.desk, nonsense"),
                         ["light.desk", "sensor.t", "switch.fan"])
        self.assertEqual(ha.action("light.desk"), ("homeassistant", "toggle"))
        self.assertEqual(ha.action("scene.movie"), ("scene", "turn_on"))
        self.assertIsNone(ha.action("lock.front_door"))                 # never from the kiosk
        self.assertIsNone(ha.action("sensor.temperature"))
        self.assertEqual(ha.tile("x.y", None)["available"], False)
        self.assertEqual(ha.tile("switch.a", {"state": "not_home"})["state"], "away")       # translated in QML
        self.assertEqual(ha.tile("sensor.a", {"state": "21.4"})["translate"], False)

    def test_states_and_switching(self):
        client = ha.HomeAssistant(FakeSettings(self.url, fake_openlinkhub.HA_TOKEN))
        client.refresh()
        self.assertTrue(wait(lambda: client.state("light.desk") is not None))
        tiles = [ha.tile(x, client.state(x)) for x in ("light.desk", "sensor.living_temperature", "lock.front_door")]
        self.assertEqual([(t["name"], t["state"], t["unit"], t["on"], t["actionable"]) for t in tiles],
                         [("Desk lamp", "on", "", True, True), ("Living room", "21.4", "°C", False, False),
                          ("Front door", "locked", "", False, False)])
        client.activate("light.desk")
        self.assertTrue(wait(lambda: client.state("light.desk")["state"] == "off"))
        self.assertEqual(self.state.ha_calls, [("homeassistant", "toggle", "light.desk")])
        client.activate("lock.front_door")
        client.activate("sensor.living_temperature")
        wait(lambda: False, 300)
        self.assertEqual(len(self.state.ha_calls), 1)                   # nothing sent for a lock or a sensor
        self.assertEqual(client.entities()[0], {"value": "light.desk", "name": "Desk lamp (light.desk)"})

    def test_wrong_token_and_test_button(self):
        client = ha.HomeAssistant(FakeSettings(self.url, "wrong"))
        client.refresh()
        self.assertTrue(wait(lambda: client.status != ""))
        self.assertEqual(client.status, "Home Assistant refused the token")
        good = ha.HomeAssistant(FakeSettings(self.url, fake_openlinkhub.HA_TOKEN))
        good.test()
        self.assertTrue(wait(lambda: good.testResult == "Connected to Home Assistant"))
        empty = ha.HomeAssistant(FakeSettings())
        empty.test()
        self.assertEqual(empty.testResult, "Fill in the address and the token first")
        empty.refresh()
        self.assertIn("settings", empty.status)

    def test_the_kiosk_widget(self):
        from quartercore.backend import Backend
        from test_edge import FakeMedia, FakeSensors
        backend = Backend(self.url)
        client = ha.HomeAssistant(FakeSettings(self.url, fake_openlinkhub.HA_TOKEN))
        edge = e.Edge(backend, sensors=FakeSensors, media=FakeMedia(), home_assistant=client)
        settings = e.widget_settings(23, {"entities": "light.desk, switch.fan"})
        edge.set_items([{"key": "widget:23", "widgetId": 23, "template": "xeneon-ha-buttons", "settings": settings,
                         "x": 0, "y": 0, "w": 6, "h": 4}])
        edge._tick()
        self.assertTrue(wait(lambda: (edge.data.get("widget:23") or {}).get("tiles", [{}])[0].get("name") == "Desk lamp"))
        edge.activateEntity("switch.fan")
        self.assertTrue(wait(lambda: edge.data["widget:23"]["tiles"][1]["on"]))
        none = e.Edge(backend, sensors=FakeSensors, media=FakeMedia(), home_assistant=ha.HomeAssistant(FakeSettings()))
        self.assertIn("settings", none._home_assistant_view(settings)["message"])
        backend.system_timer.stop()
        backend.devices_timer.stop()
        wait(lambda: False, 300)
        self.backend = backend


if __name__ == "__main__":
    unittest.main()
