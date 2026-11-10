# Tests for the lighting page logic against the fake OpenLinkHub
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
from quartercore.lighting import Lighting, change_request, effect_view, from_hex, to_hex  # noqa: E402
from test_backend import wait  # noqa: E402

EFFECTS = fake_openlinkhub.initial_effects()


class ConversionTest(unittest.TestCase):
    def test_hex(self):
        self.assertEqual(to_hex({"red": 255, "green": 16, "blue": 0}), "#ff1000")
        self.assertEqual(from_hex("#ff1000", 40), {"red": 255, "green": 16, "blue": 0, "temperature": 40.0})
        with self.assertRaises(ValueError):
            from_hex("#fff")

    def test_options_per_effect(self):
        static = effect_view("static", EFFECTS["static"])
        self.assertTrue(static["speedFixed"])
        self.assertEqual(static["colorMode"], "two")
        wave = effect_view("colorwave", EFFECTS["colorwave"])
        self.assertEqual((wave["speedMin"], wave["speedMax"], wave["speedStep"]), (1, 3, 1))
        self.assertTrue(wave["alternating"])
        self.assertEqual(wave["direction"], 4)
        self.assertEqual(effect_view("cpu-temperature", EFFECTS["cpu-temperature"])["colorMode"], "temperature")
        gradient = effect_view("gradient", EFFECTS["gradient"])
        self.assertEqual(gradient["colorMode"], "gradient")
        self.assertEqual([s["position"] for s in gradient["gradient"]], [0, 0.5, 1])
        self.assertTrue(effect_view("probe-temperature", EFFECTS["probe-temperature"])["probe"])

    def test_request_like_the_web_editor(self):
        wave = effect_view("colorwave", EFFECTS["colorwave"])
        body = change_request("HUB1", wave, {"start": {"color": "#00ff00", "temperature": 0}, "speed": 3,
                                             "alternateColors": True, "direction": 5})
        self.assertEqual(body["profile"], "colorwave")
        self.assertEqual(body["startColor"], {"red": 0, "green": 255, "blue": 0, "temperature": 0.0})
        self.assertEqual(body["endColor"]["blue"], 255)  # unchanged colour is kept
        self.assertEqual((body["speed"], body["alternateColors"], body["rgbDirection"]), (3, True, 5))
        self.assertNotIn("colorZones", body)
        self.assertNotIn("rgbMinTemp", body)

    def test_fixed_speed_and_options_are_not_sent_where_unused(self):
        static = effect_view("static", EFFECTS["static"])
        body = change_request("HUB1", static, {"speed": 9, "alternateColors": True, "direction": 4})
        self.assertEqual((body["speed"], body["alternateColors"], body["rgbDirection"]), (4, False, 0))

    def test_gradient_zones(self):
        gradient = effect_view("gradient", EFFECTS["gradient"])
        stops = [{"color": "#0000ff", "position": 1.2, "brightness": 1}, {"color": "#ff0000", "position": 0, "brightness": 1}]
        body = change_request("HUB1", gradient, {"gradient": stops})
        self.assertEqual(body["colorZones"]["0"]["red"], 255)
        self.assertEqual(body["colorZones"]["1"]["position"], 1.0)  # sorted and clamped
        with self.assertRaises(ValueError):
            change_request("HUB1", gradient, {"gradient": stops[:1]})

    def test_temperature_colours_must_go_up(self):
        cpu = effect_view("cpu-temperature", EFFECTS["cpu-temperature"])
        change_request("HUB1", cpu, {})
        with self.assertRaises(ValueError):
            change_request("HUB1", cpu, {"middle": {"color": "#ffff00", "temperature": 10}})

    def test_probe_range(self):
        probe = effect_view("probe-temperature", EFFECTS["probe-temperature"])
        self.assertEqual(change_request("HUB1", probe, {"minTemp": 20, "maxTemp": 60})["rgbMaxTemp"], 60)
        with self.assertRaises(ValueError):
            change_request("HUB1", probe, {"minTemp": 70, "maxTemp": 60})


class LightingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, url, self.state = fake_openlinkhub.start()
        self.backend = Backend(url)
        self.lighting = Lighting(self.backend)
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))
        self.backend.refreshDevices()
        # Prefers the LINK System Hub once its page type is known, and opens Static
        self.assertTrue(wait(lambda: self.lighting.serial == "HUB1" and self.lighting.selected.get("key") == "static"))

    def tearDown(self):
        self.server.shutdown()

    def test_only_devices_with_rgb(self):
        self.assertTrue(wait(lambda: len(self.lighting.devices) == 2))
        self.assertEqual(sorted(d["serial"] for d in self.lighting.devices), ["HUB1", "KB1"])

    def test_hidden_effects(self):
        keys = [e["key"] for e in self.lighting.effects]
        for hidden in ("off", "keyboard", "led"):
            self.assertNotIn(hidden, keys)
        self.assertIn("gradient", keys)

    def test_user_choice_wins(self):
        self.lighting.selectDevice("KB1")
        self.assertTrue(wait(lambda: self.lighting.serial == "KB1" and self.lighting.effects))
        self.backend.refreshDevices()
        wait(lambda: False, 300)
        self.assertEqual(self.lighting.serial, "KB1")

    def test_save_keeps_the_effect_open(self):
        self.lighting.selectEffect("colorwave")
        self.lighting.save({"start": {"color": "#112233", "temperature": 0}, "speed": 1})
        self.assertTrue(wait(lambda: self.lighting.selected.get("start", {}).get("color") == "#112233"))
        self.assertEqual(self.lighting.selected["key"], "colorwave")
        self.assertEqual(self.state.effects["HUB1"]["colorwave"]["speed"], 1)
        self.assertTrue(self.messages[-1][1])

    def test_invalid_values_are_not_sent(self):
        self.lighting.selectEffect("cpu-temperature")
        self.lighting.save({"start": {"color": "#00ff00", "temperature": 90}})
        self.assertEqual([r for r in self.state.requests if r[0] == "PUT"], [])
        self.assertFalse(self.messages[-1][1])

    def test_apply_to_hub_skips_probes(self):
        self.lighting.applyToHub("rainbow")
        self.assertTrue(wait(lambda: len([r for r in self.state.requests if r[1] == "/api/color"]) == 2))
        channels = sorted(r[2]["channelId"] for r in self.state.requests if r[1] == "/api/color")
        self.assertEqual(channels, [1, 2])


if __name__ == "__main__":
    unittest.main()
