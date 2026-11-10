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
from quartercore.keyboard import Keyboard, assignment_body, keyboard_view  # noqa: E402
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
        self.assertEqual(self.view["keysHeight"], 120 + 155)  # the tall key in the last row fits

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

    def test_assignments(self):
        q = self.keys[10]["assignment"]
        self.assertEqual((q["enabled"], q["type"], q["value"]), (False, 3, 101))
        self.assertTrue(self.keys[4]["assignment"]["enabled"])


class AssignmentBodyTest(unittest.TestCase):
    def test_number_value(self):
        self.assertEqual(assignment_body("KB1", 10, {"enabled": False, "type": 3, "value": 102, "toggleDelay": 0}), {
            "deviceId": "KB1", "keyIndex": 10, "enabled": False, "pressAndHold": False,
            "keyAssignmentOriginal": False, "keyAssignmentModifier": 0, "keyAssignmentType": 3,
            "keyAssignmentValue": 102, "toggleDelay": 0})

    def test_text_value(self):
        # DPI, sniper and profile change send the value as a text, like overview.js
        for kind in (2, 4, 8, 21):
            body = assignment_body("KB1", 4, {"type": kind, "value": "MOUSE1"})
            self.assertEqual(body["keyAssignmentValueString"], "MOUSE1")
            self.assertNotIn("keyAssignmentValue", body)


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


class KeyAssignmentTest(unittest.TestCase):
    """Key assignments, performance and dial colours against the fake."""

    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, url, self.state = fake_openlinkhub.start()
        self.backend = Backend(url)
        self.keyboard = Keyboard(self.backend)
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))
        self.backend.selectDevice("KB1")
        self.assertTrue(wait(lambda: len(self.keyboard.dialColors) == 2 and len(self.keyboard.performance) == 4
                             and len(self.keyboard.assignmentValues["3"]) == 4 and self.keyboard.macros
                             and self.keyboard.assignmentValues.get("2") and self.keyboard.assignmentValues.get("21")))

    def tearDown(self):
        self.server.shutdown()

    def key(self, key_id):
        return next(k for k in self.backend.active["keys"] if k["keyId"] == key_id)

    def sent(self, path):
        return [body for _, p, body in self.state.requests if p == path]

    def test_lists(self):
        kb = self.keyboard
        types = {o["value"]: o["name"] for o in kb.assignmentTypes}
        self.assertEqual((types[0], types[10]), ("None", "Macro"))
        self.assertEqual(kb.modifiers, [{"value": 0, "name": "None"}])   # the K100 has no modifier keys
        values = kb.assignmentValues
        self.assertEqual([o["name"] for o in values["3"]], ["A", "B", "H", "Left Ctrl"])  # "None" left out
        self.assertEqual(values["2"], [{"value": "MOUSE1", "name": "M75 WIRELESS"}])
        self.assertEqual([o["value"] for o in values["21"]], ["default", "work"])
        self.assertEqual(values["10"], [{"value": 1, "name": "Hello"}])

    def test_assign_key(self):
        self.keyboard.setKeyAssignment(4, {"enabled": False, "type": 1, "value": 2, "toggleDelay": 0})
        self.assertTrue(wait(lambda: self.key(4)["assignment"]["type"] == 1))
        a = self.key(4)["assignment"]
        self.assertEqual((a["enabled"], a["value"], a["toggleDelay"]), (False, 2, 30))  # at least 30 ms
        self.assertEqual(self.sent("/api/keyboard/updateKeyAssignment")[0]["keyAssignmentValue"], 2)
        self.assertTrue(self.messages[-1][1])

    def test_assign_mouse_device(self):
        self.keyboard.setKeyAssignment(9, {"type": 8, "value": "MOUSE1", "pressAndHold": True})
        self.assertTrue(wait(lambda: self.key(9)["assignment"]["valueString"] == "MOUSE1"))

    def test_refusals_are_reported(self):
        self.keyboard.setKeyAssignment(4, {"type": 10, "value": 1, "pressAndHold": True})
        self.assertTrue(wait(lambda: self.messages))
        self.assertFalse(self.messages[-1][1])
        self.keyboard.setKeyAssignment(1, {"type": 3, "value": 101})   # a light zone has no assignment
        self.assertTrue(wait(lambda: len(self.messages) == 2))
        self.assertFalse(self.messages[-1][1])
        self.assertTrue(self.key(4)["assignment"]["enabled"])

    def test_performance(self):
        self.assertEqual({p["internal"]: p["value"] for p in self.keyboard.performance}["perf_altTab"], True)
        self.keyboard.setPerformance({"perf_winKey": True})
        self.assertTrue(wait(lambda: {p["internal"]: p["value"] for p in self.keyboard.performance}["perf_winKey"]))
        self.assertEqual(self.sent("/api/keyboard/setPerformance")[0], {
            "deviceId": "KB1", "perf_winKey": True, "perf_shiftTab": False, "perf_altTab": True, "perf_altF4": False})

    def test_dial_colours(self):
        self.assertEqual([c["color"] for c in self.keyboard.dialColors], ["#ffffff", "#00ffff"])
        self.keyboard.setDialColors({"2": "#ff0000"})
        self.assertTrue(wait(lambda: self.keyboard.dialColors[1]["color"] == "#ff0000"))
        self.assertEqual(self.sent("/api/keyboard/dial/setColors")[0], {"deviceId": "KB1", "colorZones": {
            "1": {"red": 255, "green": 255, "blue": 255}, "2": {"red": 255, "green": 0, "blue": 0}}})

    def test_other_device_clears_lists(self):
        self.backend.selectDevice("HUB1")
        self.assertTrue(wait(lambda: self.keyboard.dialColors == []))


if __name__ == "__main__":
    unittest.main()
