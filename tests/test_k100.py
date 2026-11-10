# Tests for the K100 driver of quartercore-core
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests
# A simulated keyboard answers the HID reports; nothing is sent to real hardware.

import json
import queue
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quartercore.core import k100, rgb  # noqa: E402
from quartercore.core.server import Core  # noqa: E402
from quartercore.core.store import Store  # noqa: E402
from test_hs80 import wait  # noqa: E402

SERIAL = "321479D24AAA7CC6"
INFO = {"node": "/dev/hidraw11", "listener": "/dev/hidraw12", "product": 7109, "interface": 1,
        "usbPath": "/devices/x/1-2"}


def key(name, index, data, hashes, **extra):
    return dict({"keyName": name, "packetIndex": [index], "keyData": [data], "keyHash": hashes, "default": True,
                 "color": {"red": 0, "green": 0, "blue": 255, "brightness": 0, "Hex": ""}}, **extra)


def layout(name="US", version=4):
    return {"version": version, "key": "k100-default", "device": "K100 RGB", "layout": name, "rows": 1, "row": {
        "1": {"keys": {
            "1": key("Esc", 3, 1, ["1"]),
            "2": key("Lock", 6, 2, ["2"], isLock=True),
            "3": key("Dial", 9, 3, ["256"], isDialChange=True),
            "4": key("Ctrl", 12, 4, ["512"], modifier=True, keyNameInternal="Left Ctrl"),
            "5": key("Logo", 414, 0, [], onlyColor=True)}}}}


class FakeKeyboard:
    def __init__(self):
        self.written = []
        self.events = queue.Queue()
        self.replies = queue.Queue()
        self.handles = []

    def open(self, node):
        handle = Handle(self, node)
        self.handles.append(handle)
        return handle

    def commands(self):
        return [tuple(w[2:6]) for w in self.written]

    def colors(self):
        """The 581 colour bytes of every colour write."""
        return [w[10:10 + k100.COLOR_LENGTH] for w in self.written if tuple(w[2:4]) == k100.WRITE_COLOR]


class Handle:
    def __init__(self, keyboard, node):
        self.keyboard, self.node = keyboard, node
        self.closed = False

    def write(self, data):
        assert len(data) == 1025 and data[0] == 0 and data[1] == 0x08
        self.keyboard.written.append(bytes(data))
        reply = bytearray(1024)
        reply[0], reply[1], reply[2] = 0x00, data[2], data[3]
        if tuple(data[2:4]) == k100.GET_FIRMWARE:
            reply[3], reply[4], reply[5:7] = 1, 2, (300).to_bytes(2, "little")
        self.keyboard.replies.put(bytes(reply))
        return len(data)

    def read(self, timeout):
        source = self.keyboard.replies if self.node == INFO["node"] else self.keyboard.events
        try:
            return source.get(timeout=timeout) if timeout > 0 else source.get_nowait()
        except queue.Empty:
            return b""

    def close(self):
        self.closed = True


class Recorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name,) + args)


def key_report(*bytes_at):
    data = bytearray(1024)
    data[1] = 0x02
    for position, value in bytes_at:
        data[2 + position] = value
    return bytes(data)


def dial_report(value):
    data = bytearray(1024)
    data[1], data[4] = 0x05, value
    return bytes(data)


class K100Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.olh = root / "olh"
        (self.olh / "profiles").mkdir(parents=True)
        self.layouts = root / "layouts"
        self.layouts.mkdir()
        (self.layouts / "k100.json").write_text(json.dumps(layout()))
        (self.layouts / "k100-uk.json").write_text(json.dumps(layout("UK")))
        (self.layouts / "k65.json").write_text(json.dumps(dict(layout("US"), key="k65-default")))
        self.store = Store(root / "store", self.olh / "profiles")
        self.keyboard = FakeKeyboard()
        self.inputs = Recorder()

    def tearDown(self):
        if hasattr(self, "driver"):
            self.driver.stop()
        self.tmp.cleanup()

    def make(self):
        self.driver = k100.K100(INFO, self.store, self.keyboard.open, serial=SERIAL, sleep=lambda s: None,
                                input_devices=self.inputs, layouts_folder=self.layouts)
        return self.driver

    def start(self):
        driver = self.make()
        driver.start()
        return driver

    def saved(self):
        return json.loads((Path(self.tmp.name) / "store" / (SERIAL + ".json")).read_text())

    def test_packet(self):
        p = k100.packet(k100.WRITE_COLOR, b"\x01\x02")
        self.assertEqual((len(p), p[0], p[1], p[2], p[3], p[4], p[5]), (1025, 0, 0x08, 0x06, 0x01, 1, 2))

    def test_key_value_like_openlinkhub(self):
        self.assertEqual(k100.key_value(key_report((0, 1))), 1)
        self.assertEqual(k100.key_value(key_report((1, 1))), 256)
        self.assertEqual(k100.key_value(key_report((13, 0x04))), 0)      # the Fn bit is left out

    def test_start(self):
        driver = self.start()
        commands = self.keyboard.commands()
        self.assertEqual(commands[:3], [(0x01, 0x03, 0x00, 0x02), (0x0D, 0x01, 0x22, 0), (0x02, 0x13, 0, 0)])
        self.assertEqual(driver.firmware, "1.2.300")
        colors = self.keyboard.colors()
        self.assertTrue(colors)
        first = [w for w in self.keyboard.written if tuple(w[2:4]) == k100.WRITE_COLOR][0]
        self.assertEqual(first[4:10], bytes((0x45, 0x02, 0, 0, 0x12, 0x00)))   # 581 colour bytes
        self.assertEqual(colors[0][3:6], b"\x00\x00\xff")                     # Esc
        self.assertEqual(colors[0][546:549], b"\xff\xff\xff")                 # dial: volume colour
        self.assertIn((0x01, 0x02, 0x00, 0xE8), commands)                     # brightness 1000
        self.assertIn((0x01, 0x4A, 0x00, 0x00), commands)                     # performance off
        assignment = [w for w in self.keyboard.written if tuple(w[2:4]) == k100.KEY_ASSIGNMENT][0]
        self.assertEqual(assignment[4:6], (138).to_bytes(2, "little"))
        self.assertEqual(assignment[8:8 + 138], b"\x01" * 138)
        self.assertEqual(commands[-1], (0x01, 0x38, 0x00, 31))                # debounce 1 ms
        device = driver.device_json()
        self.assertEqual((device["Template"], device["Layouts"]), ("k100.html", ["UK", "US"]))

    def test_key_colours_kept_until_saved(self):
        driver = self.start()
        before = self.saved()
        self.assertEqual(driver.handle("/api/keyboard/color", {"keyOption": 3, "keyId": 1, "keys": [1, 2],
                                                               "color": {"red": 255, "green": 0, "blue": 0}}), "")
        self.assertEqual(self.keyboard.colors()[-1][3:9], b"\xff\x00\x00\xff\x00\x00")
        self.assertEqual(self.saved(), before)
        self.assertEqual(driver.handle("/api/keyboard/profile/save", {"keyboardProfileName": "0"}), "")
        self.assertEqual(self.saved()["profiles"]["default"]["Keyboards"]["default"]["row"]["1"]["keys"]["1"]
                         ["color"]["red"], 255)
        self.assertEqual(driver.handle("/api/keyboard/color", {"keyOption": 3, "keys": [99], "color": {}}),
                         "Invalid key selected")

    def test_dial(self):
        driver = self.start()
        self.keyboard.events.put(dial_report(1))
        self.keyboard.events.put(dial_report(255))
        self.assertTrue(wait(lambda: self.inputs.calls[-2:] == [("key", 1), ("key", 2)]))
        self.assertEqual(driver.handle("/api/keyboard/dial", {"keyboardControlDial": 5}), "")
        self.assertEqual(self.keyboard.colors()[-1][546:549], bytes((191, 255, 0)))
        self.keyboard.events.put(dial_report(1))
        self.assertTrue(wait(lambda: self.inputs.calls[-1] == ("key", 125)))
        driver.handle("/api/keyboard/dial", {"keyboardControlDial": 2})
        self.keyboard.events.put(dial_report(255))
        self.assertTrue(wait(lambda: driver.profile["BrightnessLevel"] == 900))

    def test_lock_and_dial_change_keys(self):
        driver = self.start()
        self.keyboard.events.put(key_report((0, 2)))
        self.assertTrue(wait(lambda: driver.profile["Performance"]))
        self.assertTrue(wait(lambda: self.keyboard.colors()[-1][342:345] == b"\xff\x00\x00"))
        self.assertEqual(self.keyboard.colors()[-1][0:3], b"\xff\xff\xff")
        self.keyboard.events.put(key_report())
        self.keyboard.events.put(key_report((1, 1)))
        self.assertTrue(wait(lambda: driver.profile["ControlDial"] == 2))

    def test_key_assignment(self):
        driver = self.start()
        body = {"keyIndex": 1, "enabled": False, "pressAndHold": False, "onRelease": False,
                "keyAssignmentType": 3, "keyAssignmentValue": 30}
        self.assertEqual(driver.handle("/api/keyboard/updateKeyAssignment", body), "")
        assignment = [w for w in self.keyboard.written if tuple(w[2:4]) == k100.KEY_ASSIGNMENT][-1]
        self.assertEqual(assignment[8 + 1], 0)                                 # Esc goes to software
        self.keyboard.events.put(key_report((0, 1)))
        self.assertTrue(wait(lambda: ("key", 30, False) in self.inputs.calls))
        self.assertIn("not allowed", driver.handle("/api/keyboard/updateKeyAssignment",
                                                   dict(body, keyAssignmentType=10, pressAndHold=True)))
        self.assertEqual(driver.handle("/api/keyboard/updateKeyAssignment", dict(body, keyIndex=5)),
                         "Unable to apply key assignment")                     # only a colour

    def test_profiles(self):
        driver = self.start()
        self.assertEqual(driver.handle("/api/keyboard/profile/new", {"keyboardProfileName": "game"}, "PUT"), "")
        self.assertEqual(driver.profile["Profiles"], ["default", "game"])
        self.assertEqual(driver.handle("/api/keyboard/profile/change", {"keyboardProfileName": "game"}), "")
        self.assertEqual(driver.handle("/api/keyboard/profile/delete", {"keyboardProfileName": "game"}, "DELETE"), "")
        self.assertEqual(driver.profile["Profile"], "default")
        self.assertEqual(driver.handle("/api/userProfile", {"userProfileName": "work"}, "PUT"), "")
        self.assertEqual(driver.handle("/api/userProfile/change", {"userProfileName": "work"}), "")
        self.assertEqual(driver.handle("/api/userProfile/delete", {"userProfileName": "work"}, "DELETE"),
                         "Unable to delete an active profile")
        self.assertEqual(driver.get("/api/device/profiles/" + SERIAL), ["default", "work"])

    def test_layout_and_settings(self):
        driver = self.start()
        self.assertEqual(driver.handle("/api/keyboard/layout", {"keyboardLayout": "UK"}), "")
        self.assertEqual(driver.profile["Keyboards"]["default"]["layout"], "UK")
        self.assertEqual(driver.handle("/api/keyboard/layout", {"keyboardLayout": "XX"}), "Invalid keyboard layout")
        self.assertEqual(driver.handle("/api/keyboard/debounceTime", {"debounceTime": 4}), "")
        self.assertEqual(self.keyboard.commands()[-1], (0x01, 0x38, 0x00, 34))
        self.assertEqual(driver.handle("/api/keyboard/debounceTime", {"debounceTime": 4}), "Invalid debounce time")
        self.assertEqual(driver.handle("/api/keyboard/setPerformance", {"perf_winKey": True}), "")
        self.assertTrue(driver.profile["DisableWinKey"])
        self.assertEqual(driver.handle("/api/keyboard/dial/setColors", {"colorZones": {"1": {"red": 1, "green": 2,
                                                                                               "blue": 3}}}), "")
        self.assertEqual(self.keyboard.colors()[-1][546:549], b"\x01\x02\x03")
        self.assertEqual(driver.handle("/api/keyboard/pollingRate", {"pollingRate": 9}), "Invalid polling rate")
        self.assertEqual(driver.handle("/api/keyboard/pollingRate", {"pollingRate": 3}), "")
        self.assertEqual(self.keyboard.commands()[-1], (0x01, 0x01, 0x00, 3))
        self.assertTrue(driver.gone)

    def test_effects(self):
        driver = self.start()
        self.assertEqual(driver.handle("/api/color", {"profile": "rainbow"}), "")
        count = len(self.keyboard.colors())
        self.assertTrue(wait(lambda: len(self.keyboard.colors()) > count + 3))
        self.assertEqual(driver.handle("/api/brightness", {"brightness": 1}), "")
        self.assertEqual(driver.handle("/api/color", {"profile": "static"}), "")
        time.sleep(0.05)
        self.assertEqual(self.keyboard.colors()[-1][3:6], b"\x00\xff\xff")      # static colour of rgb.json
        self.assertEqual(driver.handle("/api/color", {"profile": "disco"}), "Non-existing RGB profile")
        body = {"profile": "static", "speed": 4, "startColor": {"red": 9, "green": 8, "blue": 7},
                "endColor": {"red": 9, "green": 8, "blue": 7}, "middleColor": {}, "colorZones": None}
        self.assertEqual(driver.handle("/api/color/change", body, "PUT"), "")
        self.assertEqual(self.keyboard.colors()[-1][3:6], b"\x09\x08\x07")
        self.assertEqual(driver.handle("/api/color/change", dict(body, speed=20), "PUT"), "Invalid speed")
        self.assertIn("static", driver.get("/api/color/" + SERIAL)["profiles"])

    def test_reads(self):
        driver = self.make()
        self.assertEqual(driver.get("/api/keyboard/assignmentsTypes/" + SERIAL)["22"], "Profile Switch")
        self.assertEqual(driver.get("/api/keyboard/assignmentsModifiers/" + SERIAL), {"0": "None", "4": "Left Ctrl"})
        self.assertEqual(driver.get("/api/keyboard/getPerformance/" + SERIAL)[0]["internal"], "perf_winKey")
        self.assertEqual(driver.get("/api/keyboard/dial/getColors/" + SERIAL)[4]["Name"], "Screen Brightness")
        self.assertIsNone(driver.get("/api/keyboard/getFlashTap/" + SERIAL))

    def test_takes_over_openlinkhubs_profile(self):
        own = k100.default_profile(SERIAL, layout())
        own.update({"RGBProfile": "wave", "ControlDial": 5, "Path": "/var/opt/x.json"})
        (self.olh / "profiles" / (SERIAL + ".json")).write_text(json.dumps(own))
        driver = self.make()
        self.assertEqual((driver.profile["RGBProfile"], driver.profile["ControlDial"]), ("wave", 5))
        self.assertNotIn("Path", driver.profile)

    def test_old_layout_version_is_replaced(self):
        own = k100.default_profile(SERIAL, layout(version=3))
        (self.olh / "profiles" / (SERIAL + ".json")).write_text(json.dumps(own))
        self.assertEqual(self.make().profile["Keyboards"]["default"]["version"], 4)

    def test_stop_and_release(self):
        driver = self.start()
        driver.stop()
        self.assertEqual(self.keyboard.commands()[-1], (0x01, 0x03, 0x00, 0x01))
        self.assertTrue(all(h.closed for h in self.keyboard.handles))
        del self.driver

    def test_discover_pairs_the_interfaces(self):
        found = [{"node": "/dev/hidraw%d" % n, "product": 7109, "interface": n - 10, "usbPath": "/u"}
                 for n in (10, 11, 12, 13)]
        original = k100.hid.find
        k100.hid.find = lambda vendor, products, root: found
        try:
            drivers = k100.discover(self.store, opener=self.keyboard.open)
        finally:
            k100.hid.find = original
        self.assertEqual([(d.info["node"], d.info["listener"]) for d in drivers], [("/dev/hidraw11", "/dev/hidraw12")])


class ReconnectTest(unittest.TestCase):
    def test_a_gone_driver_is_taken_over_again(self):
        class Driver:
            def __init__(self, serial):
                self.serial, self.product, self.gone, self.device = serial, "K100", False, None
                self.started = self.released = False

            def start(self):
                self.started = True

            def refresh(self):
                pass

            def release(self):
                self.released = True
        first, second = Driver("KB"), Driver("KB")
        found = [first]
        core = Core("http://127.0.0.1:1", lambda: list(found), standalone=True, log=lambda text: None)
        core.check()
        first.gone = True
        found[:] = [second]
        core.check()
        self.assertTrue(first.released and second.started)
        self.assertIs(core.drivers["KB"], second)


if __name__ == "__main__":
    unittest.main()
