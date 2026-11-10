# Tests for temperature profiles against the fake OpenLinkHub
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
from quartercore.backend import Backend  # noqa: E402
from quartercore.profiles import Profiles, clean_points  # noqa: E402
from test_backend import wait  # noqa: E402


class CleanPointsTest(unittest.TestCase):
    def test_sorted_rounded_and_clamped(self):
        self.assertEqual(clean_points([{"x": 80.4, "y": 101}, {"x": -3, "y": 20.6}, {"x": 250, "y": 50}]),
                         [{"x": 0, "y": 21}, {"x": 80, "y": 100}, {"x": 200, "y": 50}])

    def test_one_point_per_temperature(self):
        self.assertEqual(clean_points([{"x": 40, "y": 10}, {"x": 40, "y": 60}]), [{"x": 40, "y": 60}])


class ProfilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, url, self.state = fake_openlinkhub.start()
        self.backend = Backend(url)
        self.profiles = Profiles(self.backend)
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))
        self.profiles.refresh()
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Normal"))

    def tearDown(self):
        self.server.shutdown()

    def names(self):
        return [p["name"] for p in self.profiles.list]

    def test_list_order_and_kinds(self):
        self.assertEqual(self.names(), ["Quiet", "Normal", "Performance", "Fixed", "Gaming", "Liquid"])
        kinds = {p["name"]: p for p in self.profiles.list}
        self.assertFalse(kinds["Normal"]["editable"])
        self.assertTrue(kinds["Gaming"]["editable"])
        self.assertTrue(kinds["Gaming"]["zeroRpm"])
        self.assertTrue(kinds["Liquid"]["linear"])
        self.assertTrue(kinds["Fixed"]["static"])
        self.assertFalse(kinds["Fixed"]["editable"])

    def test_select_loads_both_curves(self):
        self.profiles.select("Gaming")
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Gaming"))
        selected = self.profiles.selected
        self.assertEqual(selected["fans"], fake_openlinkhub.CPU_CURVE)
        self.assertEqual(selected["pump"], fake_openlinkhub.PUMP_CURVE)
        self.assertEqual(selected["maxTemp"], 100)

    def test_liquid_sensor_uses_60_degrees(self):
        self.profiles.select("Liquid")
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Liquid"))
        self.assertEqual(self.profiles.selected["maxTemp"], 60)

    def test_save_fan_curve(self):
        self.profiles.select("Gaming")
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Gaming"))
        self.profiles.saveCurve("fans", [{"x": 60, "y": 50}, {"x": 20, "y": 25.4}])
        self.assertTrue(wait(lambda: self.profiles.selected.get("fans") == [{"x": 20, "y": 25}, {"x": 60, "y": 50}]))
        self.assertIn(("PUT", "/api/temperatures/updateGraph",
                       {"profile": "Gaming", "updateType": 1, "points": [{"x": 20, "y": 25}, {"x": 60, "y": 50}]}),
                      self.state.requests)
        self.assertEqual(self.state.profiles["Gaming"]["points"]["0"], fake_openlinkhub.PUMP_CURVE)  # pump untouched

    def test_save_pump_curve_uses_type_0(self):
        self.profiles.select("Gaming")
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Gaming"))
        self.profiles.saveCurve("pump", [{"x": 0, "y": 50}, {"x": 90, "y": 100}])
        self.assertTrue(wait(lambda: self.state.requests))
        self.assertEqual(self.state.requests[0][2]["updateType"], 0)

    def test_built_in_profiles_are_never_sent(self):
        self.profiles.saveCurve("fans", [{"x": 0, "y": 0}, {"x": 100, "y": 100}])  # Normal is selected
        self.assertEqual(self.state.requests, [])

    def test_a_curve_needs_two_points(self):
        self.profiles.select("Gaming")
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Gaming"))
        self.profiles.saveCurve("fans", [{"x": 40, "y": 50}])
        self.assertEqual(self.state.requests, [])
        self.assertFalse(self.messages[-1][1])

    def test_create_selects_the_new_profile(self):
        self.profiles.create("Silent2", 1, True, False, False, "")
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Silent2"))
        self.assertIn("Silent2", self.names())
        self.assertEqual(self.state.requests[0], ("POST", "/api/temperatures/new", {
            "profile": "Silent2", "sensor": 1, "zeroRpm": True, "static": False, "linear": False}))

    def test_create_with_a_drive(self):
        self.profiles.create("Disk", 3, False, False, False, "hwmon1")
        self.assertTrue(wait(lambda: self.state.requests))
        self.assertEqual(self.state.requests[0][2]["hwmonDeviceId"], "hwmon1")

    def test_create_refuses_bad_input(self):
        for args in (("ab", 0, False, False, False, ""),         # too short
                     ("My profile", 0, False, False, False, ""),  # space
                     ("Both", 0, False, True, True, ""),          # static and linear
                     ("Disk", 3, False, False, False, "")):       # no drive
            self.profiles.create(*args)
        self.assertEqual(self.state.requests, [])
        self.assertEqual(len(self.messages), 4)
        self.assertTrue(all(not ok for _, ok in self.messages))

    def test_delete(self):
        self.profiles.select("Gaming")
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Gaming"))
        self.profiles.remove("Gaming")
        self.assertTrue(wait(lambda: "Gaming" not in self.names()))
        # Falls back to Normal
        self.assertTrue(wait(lambda: self.profiles.selected.get("name") == "Normal"))

    def test_built_in_profiles_can_not_be_deleted(self):
        self.profiles.remove("Normal")
        self.assertEqual(self.state.requests, [])


if __name__ == "__main__":
    unittest.main()
