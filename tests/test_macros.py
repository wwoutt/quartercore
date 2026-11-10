# Tests for macros: profiles, steps, settings and recording, against the fake OpenLinkHub
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
from quartercore.keyboard import (Keyboard, key_list, macro_list, macro_step_body,  # noqa: E402
                                  macro_step_problem, recorded_steps)
from test_backend import wait  # noqa: E402


class MacroFunctionsTest(unittest.TestCase):
    keys = key_list(fake_openlinkhub.INPUT_KEYS)

    def test_macro_list(self):
        macros = macro_list(fake_openlinkhub.initial_macros(), {3: {103: "H"}})
        self.assertEqual(len(macros), 1)
        steps = macros[0]["steps"]
        self.assertEqual([(s["index"], s["type"]) for s in steps], [(0, 3), (1, 5)])
        self.assertEqual((steps[0]["valueName"], steps[1]["delay"]), ("H", 50))

    def test_step_body(self):
        self.assertEqual(macro_step_body(1, {"type": 5, "delay": 20}), {
            "macroId": 1, "macroType": 5, "macroValue": 0, "macroDelay": 20, "macroText": "",
            "mousePositionX": 0, "mousePositionY": 0, "mousePositionAbsolute": False})
        # Mouse positions are only sent for a mouse position step, like macros.js
        self.assertEqual(macro_step_body(1, {"type": 3, "value": 101, "x": 5})["mousePositionX"], 0)
        self.assertEqual(macro_step_body(1, {"type": 20, "x": 5, "y": 6, "absolute": True})["mousePositionY"], 6)

    def test_step_checks(self):
        self.assertIsNotNone(macro_step_problem({"type": 0}))
        self.assertIsNotNone(macro_step_problem({"type": 3, "value": 0}))
        self.assertIsNotNone(macro_step_problem({"type": 5, "delay": 0}))
        self.assertIsNotNone(macro_step_problem({"type": 6, "text": ""}))
        self.assertIsNone(macro_step_problem({"type": 6, "text": "hi"}))
        self.assertIsNone(macro_step_problem({"type": 20}))

    def test_recording(self):
        # Qt key codes are evdev + 8: 38 = A (30), 43 = H (35), 255 is unknown
        events = [{"code": 43, "time": 0}, {"code": 255, "time": 40}, {"code": 38, "time": 120}]
        steps, skipped = recorded_steps(events, self.keys)
        self.assertEqual(skipped, 1)
        self.assertEqual(steps, [{"type": 3, "value": 103}, {"type": 5, "delay": 120}, {"type": 3, "value": 101}])
        steps, _ = recorded_steps(events, self.keys, with_delays=False)
        self.assertEqual([s["type"] for s in steps], [3, 3])


class MacroRequestsTest(unittest.TestCase):
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
        self.assertTrue(wait(lambda: self.keyboard.macros and self.keyboard.macroValues["3"]))

    def tearDown(self):
        self.server.shutdown()

    def macro(self, name):
        return next((m for m in self.keyboard.macros if m["name"] == name), None)

    def last(self):
        return self.state.requests[-1]

    def test_names_of_steps(self):
        self.assertTrue(wait(lambda: self.macro("Hello")["steps"][0]["valueName"] == "H"))

    def test_new_and_delete_macro(self):
        self.keyboard.newMacro("Copy")
        self.assertTrue(wait(lambda: self.macro("Copy") is not None))
        self.assertEqual(self.last(), ("PUT", "/api/macro/new", {"macroName": "Copy"}))
        macro_id = self.macro("Copy")["id"]
        self.keyboard.deleteMacro(macro_id)
        self.assertTrue(wait(lambda: self.macro("Copy") is None))
        self.assertEqual(self.last(), ("DELETE", "/api/macro/profile", {"macroId": macro_id}))

    def test_bad_names_not_sent(self):
        count = len(self.state.requests)
        self.keyboard.newMacro("ab")
        self.keyboard.newMacro("with space")
        self.assertEqual(len(self.state.requests), count)
        self.assertEqual([ok for _, ok in self.messages], [False, False])

    def test_steps(self):
        self.keyboard.addMacroStep(1, {"type": 6, "text": "hi"})
        self.assertTrue(wait(lambda: len(self.macro("Hello")["steps"]) == 3))
        self.assertEqual(self.last()[1:], ("/api/macro/newValue", {
            "macroId": 1, "macroType": 6, "macroValue": 0, "macroDelay": 0, "macroText": "hi",
            "mousePositionX": 0, "mousePositionY": 0, "mousePositionAbsolute": False}))

        self.keyboard.updateMacroStep(1, 0, {"pressAndHold": False, "repeat": 3, "repeatDelay": 25})
        self.assertTrue(wait(lambda: self.macro("Hello")["steps"][0]["repeat"] == 3))
        self.assertEqual(self.last()[2], {"macroId": 1, "macroIndex": 0, "pressAndHold": False,
                                          "actionRepeatValue": 3, "actionRepeatDelay": 25, "mousePositionX": 0,
                                          "mousePositionY": 0, "mousePositionAbsolute": False})

        self.keyboard.deleteMacroStep(1, 1)
        self.assertTrue(wait(lambda: [s["index"] for s in self.macro("Hello")["steps"]] == [0, 2]))
        self.assertEqual(self.last(), ("DELETE", "/api/macro/value", {"macroId": 1, "macroIndex": 1}))

    def test_invalid_step_not_sent(self):
        count = len(self.state.requests)
        self.keyboard.addMacroStep(1, {"type": 5, "delay": 0})
        self.assertEqual(len(self.state.requests), count)
        self.assertFalse(self.messages[-1][1])

    def test_settings(self):
        self.keyboard.setMacroSettings(1, True, 5, 100)
        self.assertTrue(wait(lambda: self.macro("Hello")["repeat"] == -1))
        self.assertEqual(self.last()[2], {"macroId": 1, "macroRepeat": -1, "macroRepeatDelay": 100})
        self.keyboard.setMacroSettings(1, False, 2, 0)
        self.assertTrue(wait(lambda: self.macro("Hello")["repeat"] == 2))

    def test_recording_is_added_in_order(self):
        events = [{"code": 38, "time": 0}, {"code": 56, "time": 30}, {"code": 43, "time": 60}]  # A, B, H
        self.keyboard.saveRecording(1, events, True)
        self.assertTrue(wait(lambda: len(self.macro("Hello")["steps"]) == 2 + 5))
        steps = self.macro("Hello")["steps"][2:]
        self.assertEqual([(s["type"], s["value"] if s["type"] == 3 else s["delay"]) for s in steps],
                         [(3, 101), (5, 30), (3, 102), (5, 30), (3, 103)])
        self.assertTrue(self.messages[-1][1])

    def test_empty_recording(self):
        self.keyboard.saveRecording(1, [{"code": 255, "time": 0}], True)
        self.assertFalse(self.messages[-1][1])


if __name__ == "__main__":
    unittest.main()
