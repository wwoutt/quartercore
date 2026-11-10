# Tests for the keyboard page logic against the fake OpenLinkHub
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
from quartercore.keyboard import keyboard_view  # noqa: E402
from test_backend import wait  # noqa: E402


class KeyboardViewTest(unittest.TestCase):
    def setUp(self):
        self.view = keyboard_view(fake_openlinkhub.initial_keyboard())
        self.keys = {k["keyId"]: k for k in self.view["keys"]}

    def test_page_kind(self):
        self.assertEqual(page_kind(fake_openlinkhub.initial_keyboard()), "keyboard")
        self.assertEqual(page_kind({"Template": "other.html"}), "web")
        # Other keyboards are recognised by their key data, not by the template name
        other = dict(fake_openlinkhub.initial_keyboard(), Template="k70.html")
        self.assertEqual(page_kind(other), "keyboard")

    def test_rows_flow_left_to_right(self):
        esc, f1, plus = self.keys[4], self.keys[5], self.keys[6]
        self.assertEqual(esc["x"], 10 + 15)                 # room for the left strip, then its distance
        self.assertEqual(f1["x"], esc["x"] + 65 + 95)       # a gap of one key
        self.assertEqual(plus["x"], f1["x"] + 65 + 15)
        self.assertEqual(self.keys[1]["x"], 0)              # the top light bar starts at the edge
        self.assertEqual(self.keys[2]["x"], 90)

    def test_rows_stack_downwards(self):
        self.assertEqual(self.keys[1]["y"], 0)
        self.assertEqual(self.keys[4]["y"], 20 + 15)
        self.assertEqual(self.keys[9]["y"], 35 + 70 + 15)
        self.assertEqual(self.keys[11]["h"], 155)           # tall key keeps its height
        self.assertEqual(self.view["keysHeight"], 120 + 70)

    def test_side_strips(self):
        left, right = self.keys[3], self.keys[7]
        self.assertTrue(left["light"] and right["light"])
        self.assertEqual(left["x"], 0)
        self.assertGreater(right["x"], self.keys[6]["x"] + 65)
        self.assertLess(self.keys[3]["y"], self.keys[8]["y"])  # led 1 above led 2
        self.assertEqual(self.view["keysWidth"], right["x"] + 10)

    def test_colours_and_flags(self):
        self.assertEqual(self.keys[10]["color"], "#ff0000")
        self.assertTrue(self.keys[6]["noColor"])
        self.assertFalse(self.keys[4]["light"])

    def test_settings(self):
        v = self.view
        self.assertEqual((v["colorProfile"], v["colorProfiles"]), ("default", ["default", "Gaming"]))
        self.assertEqual((v["userProfile"], v["userProfiles"]), ("default", ["default", "work"]))
        self.assertEqual([o["value"] for o in v["pollingRates"]], [0, 4, 7])
        self.assertEqual((v["pollingRate"], v["dial"], v["debounceTime"], v["layout"]), (4, 1, 1, "US"))


class KeyboardPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, url, self.state = fake_openlinkhub.start()
        self.backend = Backend(url)
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))
        self.backend.selectDevice("KB1")
        self.assertTrue(wait(lambda: self.backend.active.get("page") == "keyboard"))

    def tearDown(self):
        self.server.shutdown()

    def key(self, key_id):
        return next(k for k in self.backend.active["keys"] if k["keyId"] == key_id)

    def last(self):
        return self.state.requests[-1]

    def test_colour_for_selected_keys(self):
        self.backend.setKeyColors([4, 9], "#0000ff")
        self.assertTrue(wait(lambda: self.key(4)["color"] == "#0000ff"))
        self.assertEqual(self.key(9)["color"], "#0000ff")
        self.assertEqual(self.key(10)["color"], "#ff0000")  # not selected
        self.assertEqual(self.state.requests[0], ("POST", "/api/keyboard/color", {
            "deviceId": "KB1", "keyId": 4, "keyOption": 3, "keys": [4, 9],
            "color": {"red": 0, "green": 0, "blue": 255}}))

    def test_nothing_sent_without_keys_or_colour(self):
        self.backend.setKeyColors([], "#0000ff")
        self.backend.setKeyColors([4], "blue")
        self.assertEqual(self.state.requests, [])

    def test_colour_profiles(self):
        self.backend.setKeyboardColorProfile("Gaming")
        self.assertTrue(wait(lambda: self.backend.active.get("colorProfile") == "Gaming"))
        self.backend.saveKeyboardColorProfileAs("Work2")
        self.assertTrue(wait(lambda: self.backend.active.get("colorProfile") == "Work2"))
        self.assertEqual(self.last(), ("PUT", "/api/keyboard/profile/new",
                                       {"deviceId": "KB1", "keyboardProfileName": "Work2", "new": True}))
        self.backend.saveKeyboardColorProfile()
        self.assertTrue(wait(lambda: self.last()[1] == "/api/keyboard/profile/save"))
        self.assertEqual(self.last()[2], {"deviceId": "KB1", "keyboardProfileName": "0", "new": False})
        self.backend.deleteKeyboardColorProfile("Work2")
        self.assertTrue(wait(lambda: self.backend.active.get("colorProfile") == "default"))
        self.assertEqual(self.last()[0], "DELETE")

    def test_empty_profile_name(self):
        self.backend.saveKeyboardColorProfileAs("   ")
        self.assertEqual(self.state.requests, [])
        self.assertFalse(self.messages[-1][1])

    def test_settings_requests(self):
        self.backend.setKeyboardRgbMode("keyboard")
        self.backend.setKeyboardLayout("DE")
        self.backend.setKeyboardPollingRate(7)
        self.backend.setKeyboardDial(2)
        self.backend.setKeyboardDebounceTime(2)
        self.backend.setUserProfile("work")
        self.assertTrue(wait(lambda: len(self.state.requests) == 6))
        sent = {path: body for _, path, body in self.state.requests}
        self.assertEqual(sent["/api/color"], {"deviceId": "KB1", "channelId": 0, "profile": "keyboard"})
        self.assertEqual(sent["/api/keyboard/layout"], {"deviceId": "KB1", "keyboardLayout": "DE"})
        self.assertEqual(sent["/api/keyboard/pollingRate"], {"deviceId": "KB1", "pollingRate": 7})
        self.assertEqual(sent["/api/keyboard/dial"], {"deviceId": "KB1", "keyboardControlDial": 2})
        self.assertEqual(sent["/api/keyboard/debounceTime"], {"deviceId": "KB1", "debounceTime": 2})
        self.assertEqual(sent["/api/userProfile/change"], {"deviceId": "KB1", "userProfileName": "work"})
        self.assertTrue(wait(lambda: (self.backend.active.get("rgbMode"), self.backend.active.get("layout"),
                                      self.backend.active.get("userProfile")) == ("keyboard", "DE", "work")))


if __name__ == "__main__":
    unittest.main()
