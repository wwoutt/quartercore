# Tests for the headset page against the fake OpenLinkHub
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
from quartercore.backend import Backend, page_kind  # noqa: E402
from quartercore.headset import Headset, button_body, equalizer_body, headset_view  # noqa: E402
from test_backend import wait  # noqa: E402


class HeadsetViewTest(unittest.TestCase):
    def setUp(self):
        self.view = headset_view(fake_openlinkhub.initial_headset())

    def test_page_kind(self):
        self.assertEqual(page_kind(fake_openlinkhub.initial_headset()), "headset")
        # Other headsets have other features; they stay in the web interface for now
        self.assertEqual(page_kind({"Template": "virtuosoW.html"}), "web")

    def test_fields(self):
        v = self.view
        self.assertTrue(v["connected"])
        self.assertEqual(v["battery"], 80)
        self.assertEqual(v["userProfiles"], ["music", "default"])   # in OpenLinkHub's order
        self.assertEqual(v["userProfile"], "default")
        self.assertEqual([z["color"] for z in v["zones"]], ["#44ff00", "#1300ff"])
        self.assertEqual([o["value"] for o in v["sleepModes"]], [0, 1, 15, 60])
        self.assertEqual((v["sleepMode"], v["micLedOff"], v["sidetone"]), (15, True, False))
        self.assertEqual([b["name"] for b in v["equalizer"]][:3], ["32", "64", "125"])
        self.assertEqual(len(v["equalizer"]), 10)               # sorted by number, not as text
        self.assertEqual(v["equalizer"][9]["name"], "16K")
        self.assertEqual(v["buttons"][0]["name"], "Scroll Press")
        self.assertEqual({o["value"]: o["name"] for o in v["buttonTypes"]}[11], "Profile switch")
        self.assertEqual(v["drivenBy"], "OpenLinkHub")

    def test_view_of_the_core_driver(self):
        # quartercore-core's HS80 driver answers in the same format
        from quartercore.core import hs80
        from quartercore.core.store import Store
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            info = {"node": "/dev/null", "product": 0x0A97, "interface": 4, "usbPath": "/x"}
            driver = hs80.Hs80(info, Store(Path(tmp) / "s", Path(tmp) / "o"), serial="ABC")
            v = headset_view(driver.device_json())
        self.assertEqual((v["serial"], v["drivenBy"], v["rgbMode"], v["userProfiles"]),
                         ("ABCW", "quartercore-core", "headset", ["default"]))
        self.assertEqual([z["color"] for z in v["zones"]], ["#ffff00", "#00ffff"])
        self.assertEqual([o["value"] for o in v["sleepModes"]], [0, 1, 5, 10, 15, 30, 60])
        self.assertEqual(len(v["equalizer"]), 10)
        self.assertEqual(v["buttons"][0]["name"], "Scroll Press")

    def test_bodies(self):
        self.assertEqual(button_body("HS1", 1, {"type": 1, "value": 2, "enabled": False}), {
            "deviceId": "HS1", "keyIndex": 1, "enabled": False, "pressAndHold": False,
            "keyAssignmentType": 1, "keyAssignmentValue": 2, "onRelease": False})
        self.assertEqual(equalizer_body("HS1", {"1": 20, 2: -30})["equalizers"], {"1": 12, "2": -12})


class HeadsetPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, url, self.state = fake_openlinkhub.start()
        self.backend = Backend(url)
        self.headset = Headset(self.backend)
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))
        self.backend.selectDevice("HS1")
        self.assertTrue(wait(lambda: self.backend.active.get("page") == "headset"))

    def tearDown(self):
        self.server.shutdown()

    def active(self, key):
        return self.backend.active.get(key)

    def last(self):
        return self.state.requests[-1]

    def test_lighting(self):
        self.headset.setRgbMode("rainbow")
        self.assertTrue(wait(lambda: self.active("rgbMode") == "rainbow"))
        self.assertEqual(self.last(), ("POST", "/api/color", {"deviceId": "HS1", "channelId": 0, "profile": "rainbow"}))
        self.headset.setBrightness(150)
        self.assertTrue(wait(lambda: self.active("brightness") == 100 and self.last()[1] == "/api/brightness/gradual"))
        self.headset.setZoneColors({"1": "#ff0000"})
        self.assertTrue(wait(lambda: self.active("zones")[1]["color"] == "#ff0000"))
        self.assertEqual(self.last()[2], {"deviceId": "HS1", "colorZones": {
            "0": {"red": 68, "green": 255, "blue": 0}, "1": {"red": 255, "green": 0, "blue": 0}}})

    def test_equalizer(self):
        self.headset.setEqualizer({"3": 4, "10": -2})
        self.assertTrue(wait(lambda: self.active("equalizer")[2]["value"] == 4))
        sent = self.last()[2]["equalizers"]
        self.assertEqual(len(sent), 10)                         # all bands, like the web page
        self.assertEqual((sent["3"], sent["10"], sent["1"]), (4, -2, 0))
        self.headset.resetEqualizer()
        self.assertTrue(wait(lambda: all(b["value"] == 0 for b in self.active("equalizer"))))
        self.headset.resetEqualizer()                          # nothing changed: OpenLinkHub says so
        self.assertTrue(wait(lambda: not self.messages[-1][1]))

    def test_sidetone_and_mic(self):
        self.headset.setSidetoneValue(40)                      # refused while sidetone is off
        self.assertTrue(wait(lambda: self.messages and not self.messages[-1][1]))
        self.headset.setSidetone(True)
        self.assertTrue(wait(lambda: self.active("sidetone")))
        self.headset.setSidetoneValue(40)
        self.assertTrue(wait(lambda: self.active("sidetoneValue") == 40))
        self.assertEqual(self.last()[1:], ("/api/headset/sidetoneValue", {"deviceId": "HS1", "sideToneValue": 40}))
        self.headset.setMicLedOff(False)
        self.assertTrue(wait(lambda: self.active("micLedOff") is False))
        self.assertEqual(self.last()[2], {"deviceId": "HS1", "muteIndicator": 0})
        count = len(self.state.requests)
        self.headset.setSidetoneValue(101)
        self.assertEqual(len(self.state.requests), count)

    def test_sleep(self):
        self.headset.setSleepMode(60)
        self.assertTrue(wait(lambda: self.active("sleepMode") == 60))
        self.assertEqual(self.last(), ("POST", "/api/headset/sleep", {"deviceId": "HS1", "sleepMode": 60}))

    def test_button(self):
        self.headset.setButton(1, {"enabled": False, "type": 1, "value": 1})
        self.assertTrue(wait(lambda: self.active("buttons")[0]["type"] == 1))
        self.assertFalse(self.active("buttons")[0]["enabled"])
        count = len(self.state.requests)
        self.headset.setButton(1, {"type": 1, "value": 1, "pressAndHold": True, "onRelease": True})
        self.assertEqual(len(self.state.requests), count)      # checked before sending, like headset.js
        self.assertFalse(self.messages[-1][1])

    def test_button_values(self):
        self.assertTrue(wait(lambda: len(self.headset.buttonValues) == 4))
        self.assertEqual(self.headset.buttonValues["10"], [{"value": 1, "name": "Hello"}])
        self.assertEqual(self.headset.buttonValues["1"][0]["name"], "Volume Up")

    def test_profiles(self):
        self.headset.saveUserProfile("gaming")
        self.assertTrue(wait(lambda: "gaming" in self.active("userProfiles")))
        self.assertEqual(self.last(), ("PUT", "/api/userProfile", {"deviceId": "HS1", "userProfileName": "gaming"}))
        self.headset.setUserProfile("gaming")
        self.assertTrue(wait(lambda: self.active("userProfile") == "gaming"))
        self.headset.deleteUserProfile("music")
        self.assertTrue(wait(lambda: "music" not in self.active("userProfiles")))
        self.assertEqual(self.last(), ("DELETE", "/api/userProfile/delete",
                                       {"deviceId": "HS1", "userProfileName": "music"}))
        count = len(self.state.requests)
        self.headset.deleteUserProfile("default")
        self.headset.saveUserProfile("ab")
        self.assertEqual(len(self.state.requests), count)

    def test_switched_off(self):
        self.state.headset["Connected"] = False
        self.backend.reloadActive()
        self.assertTrue(wait(lambda: self.active("connected") is False))


if __name__ == "__main__":
    unittest.main()
