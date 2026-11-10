# Tests for the power supply page logic against the fake OpenLinkHub
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402

import fake_openlinkhub  # noqa: E402
from quartercore.backend import Backend, psu_view  # noqa: E402
from test_backend import wait  # noqa: E402


class PsuViewTest(unittest.TestCase):
    def test_grouping(self):
        view = psu_view(fake_openlinkhub.PSU)
        self.assertEqual(view["power"], 110)
        self.assertEqual(view["outputPower"], 92)
        self.assertEqual(view["inputVoltage"], 230)
        self.assertEqual(view["fans"], [{"name": "Fan 1", "rpm": 0}])
        self.assertEqual(view["temperatures"], [{"name": "PSU Temperature", "value": "40.2 °C"}])
        self.assertEqual([r["name"] for r in view["rails"]], ["12V Rail", "5V Rail"])
        self.assertEqual(view["rails"][0]["amps"], 7.25)

    def test_fan_modes_sorted_by_value(self):
        view = psu_view(fake_openlinkhub.PSU)
        self.assertEqual([m["value"] for m in view["fanModes"]], [0, 4, 10])
        self.assertEqual(view["fanMode"], 0)


class PsuPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, url, self.state = fake_openlinkhub.start()
        self.backend = Backend(url)
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))

    def tearDown(self):
        self.server.shutdown()

    def test_page_type_from_template(self):
        self.backend.refreshDevices()
        self.assertTrue(wait(lambda: any(d["serial"] == "PSU1" and d["page"] == "psu" for d in self.backend.devices)))

    def test_fan_mode(self):
        self.backend.selectDevice("PSU1")
        self.assertTrue(wait(lambda: self.backend.active.get("page") == "psu"))
        self.backend.setPsuFanMode(4)
        self.assertTrue(wait(lambda: self.backend.active.get("fanMode") == 4))
        self.assertIn(("POST", "/api/psu/speed", {"deviceId": "PSU1", "fanMode": 4}), self.state.requests)
        self.assertTrue(self.messages[-1][1])


if __name__ == "__main__":
    unittest.main()
