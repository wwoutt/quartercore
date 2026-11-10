# Tests for the HS80 MAX WIRELESS driver of quartercore-core and the RGB effects
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests
# A simulated dongle answers the HID reports; nothing is sent to real hardware.

import json
import queue
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_openlinkhub  # noqa: E402
from quartercore.core import hs80, rgb, temperatures  # noqa: E402
from quartercore.core.server import Core, serve  # noqa: E402
from quartercore.core.store import Store  # noqa: E402

SERIAL = "553F75E3327B1415W"


class FakeDongle:
    """Both handles of one dongle: replies on the first, events on the second."""

    def __init__(self, headset_on=True):
        self.headset_on = headset_on
        self.written = []
        self.events = queue.Queue()
        self.replies = queue.Queue()
        self.handles = []

    def open(self, node):
        handle = FakeHandle(self, len(self.handles))
        self.handles.append(handle)
        return handle

    def reply(self, report):
        endpoint, command = report[2], tuple(report[3:5])
        if endpoint == hs80.HEADSET and not self.headset_on:
            return None
        out = bytearray(64)
        out[0], out[1], out[2] = 0x02, endpoint, report[3]
        if command == hs80.GET_FIRMWARE:
            out[4:7] = bytes((2, 1, 7) if endpoint == hs80.HEADSET else (5, 3, 1))
        elif command == hs80.BATTERY:
            out[4:6] = (853).to_bytes(2, "little")
        elif command == hs80.MIC_STATUS:
            out[4] = 0
        return bytes(out)

    def sent(self, endpoint=None):
        return [w for w in self.written if endpoint is None or w[2] == endpoint]

    def colors(self):
        return [bytes(w[11:19]) for w in self.sent(hs80.HEADSET) if tuple(w[3:5]) == hs80.WRITE_COLOR]


class FakeHandle:
    def __init__(self, dongle, number):
        self.dongle, self.number = dongle, number
        self.closed = False

    def write(self, data):
        assert len(data) == 65 and data[0] == 0
        self.dongle.written.append(bytes(data))
        answer = self.dongle.reply(data)
        if answer is not None:
            self.dongle.replies.put(answer)
        return len(data)

    def read(self, timeout):
        source = self.dongle.replies if self.number == 0 else self.dongle.events
        try:
            return source.get(timeout=timeout) if timeout > 0 else source.get_nowait()
        except queue.Empty:
            return b""

    def close(self):
        self.closed = True


class FakeTemps:
    def cpu(self):
        return 95.0

    def gpu(self):
        return 20.0


def event(*values):
    out = bytearray(64)
    out[:len(values)] = bytes(values)
    return bytes(out)


def wait(condition, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


INFO = {"node": "/dev/hidraw1", "product": 0x0A97, "interface": 4, "usbPath": "/devices/x/1-7"}


class RgbTest(unittest.TestCase):
    def test_rainbow_starts_red(self):
        animation = rgb.Animation(clock=lambda: 0.0)
        frame = animation.frame("rainbow", rgb.default_profiles()["rainbow"], 2, 1.0)
        self.assertEqual(frame[:3], bytes((255, 0, 0)))
        self.assertEqual(len(frame), 6)
        self.assertEqual(frame[3:], bytes((0, 255, 127)))       # position 0.5: halfway green to cyan

    def test_brightness_and_off(self):
        animation = rgb.Animation(clock=lambda: 0.0)
        self.assertEqual(animation.frame("rainbow", rgb.default_profiles()["rainbow"], 1, 0.5), bytes((127, 0, 0)))
        self.assertEqual(animation.frame("off", {}, 2, 1.0), bytes(6))
        self.assertEqual(animation.frame("nonexisting", {}, 2, 1.0), bytes(6))

    def test_temperature(self):
        profile = rgb.default_profiles()["cpu-temperature"]
        animation = rgb.Animation(clock=lambda: 0.0)
        self.assertEqual(animation.frame("cpu-temperature", profile, 1, 1.0, cpu_temp=10), bytes((0, 255, 0)))
        self.assertEqual(animation.frame("cpu-temperature", profile, 1, 1.0, cpu_temp=95), bytes((255, 0, 0)))
        self.assertEqual(animation.frame("cpu-temperature", profile, 1, 1.0, cpu_temp=50), bytes((255, 255, 0)))

    def test_colorpulse_and_gradient(self):
        now = [0.0]
        animation = rgb.Animation(clock=lambda: now[0])
        pulse = rgb.default_profiles()["colorpulse"]
        self.assertEqual(animation.frame("colorpulse", pulse, 1, 1.0), bytes((255, 0, 0)))
        now[0] = 0.5
        self.assertEqual(animation.frame("colorpulse", pulse, 1, 1.0), bytes((127, 0, 0)))
        now[0] = 0.0
        self.assertEqual(animation.frame("gradient", rgb.default_profiles()["gradient"], 1, 1.0), bytes((255, 0, 0)))

    def test_every_headset_mode_gives_a_frame(self):
        profiles = rgb.default_profiles()
        animation = rgb.Animation()
        for mode in hs80.RGB_MODES:
            self.assertEqual(len(animation.frame(mode, profiles.get(mode, {}), 2, 0.7, 50, 50)), 6, mode)

    def test_rotator_quirk(self):
        # byte() of the packed colour is its blue part, like upstream
        self.assertEqual(rgb.hsv_to_rgb(0, 255, 255) & 0xFF, 0)
        self.assertEqual(rgb.hsv_to_rgb(200, 255, 255) & 0xFF, 255)


class Hs80Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.olh = Path(self.tmp.name) / "olh"
        (self.olh / "profiles").mkdir(parents=True)
        self.store = Store(Path(self.tmp.name) / "store", self.olh / "profiles")
        self.dongle = FakeDongle()

    def tearDown(self):
        if hasattr(self, "headset"):
            self.headset.stop()
        self.tmp.cleanup()

    def make(self):
        self.input_calls = []
        recorder = type("Recorder", (), {"__getattr__": lambda _, name: lambda *a: self.input_calls.append((name,) + a)})
        self.headset = hs80.Hs80(INFO, self.store, self.dongle.open, serial="553F75E3327B1415",
                                 sleep=lambda s: None, temps=FakeTemps(), input_devices=recorder())
        return self.headset

    def start(self):
        headset = self.make()
        headset.start()
        self.assertTrue(wait(lambda: headset.connected and self.dongle.colors()))
        return headset

    def commands(self, endpoint):
        return [tuple(w[3:6]) for w in self.dongle.sent(endpoint)]

    def test_serial_and_discover(self):
        headset = self.make()
        self.assertEqual(headset.serial, SERIAL)
        self.assertEqual(headset.summary()["Template"], "hs80maxW.html")

    def test_start_and_connect(self):
        headset = self.start()
        self.assertTrue(wait(lambda: (0x0D, 0x01, 0x02) in self.commands(hs80.HEADSET)))
        self.assertEqual(self.commands(hs80.DONGLE)[:2], [(0x02, 0x13, 0), (0x01, 0x03, 0x00)])
        self.assertEqual(self.dongle.sent(hs80.DONGLE)[1][3:7], bytes(hs80.SOFTWARE_MODE))
        sent = self.commands(hs80.HEADSET)
        self.assertEqual(sent[0][:1], (0x12,))                                  # heartbeat
        self.assertEqual(sent[1:6], [(0x02, 0x13, 0), (0x02, 0xA6, 0), (0x01, 0x03, 0x00), (0x02, 0x0F, 0),
                                     (0x0D, 0x00, 0x22)])
        self.assertEqual((headset.firmware, headset.dongle_firmware, headset.battery), ("2.1.7", "5.3.1", 85))
        # The zone colours (default profile: yellow logo, cyan mic) behind length, 0, 0, 12 00
        color = [w for w in self.dongle.sent(hs80.HEADSET) if tuple(w[3:5]) == hs80.WRITE_COLOR][0]
        self.assertEqual(color[5:11], bytes((8, 0, 0, 0, 0x12, 0x00)))
        self.assertEqual(color[11:19], bytes((255, 255, 0, 0, 255, 255, 0, 0)))
        self.assertIn((0x01, 0x46, 0x00), sent)                                 # sidetone off
        device = headset.device_json()
        self.assertTrue(device["Connected"])
        self.assertEqual(device["DeviceProfile"]["RGBProfile"], "headset")
        self.assertEqual(headset.battery_info(), {"Device": "HS80 MAX WIRELESS", "Level": 85})

    def test_headset_off(self):
        self.dongle.headset_on = False
        headset = self.make()
        headset.start()
        time.sleep(1.2)
        self.assertFalse(headset.connected)
        self.assertIsNone(headset.battery_info())
        # It comes on: the dongle reports status 0x02
        self.dongle.headset_on = True
        self.dongle.events.put(event(0x03, 0x00, 0x01, 0x36, 0x00, 0x02))
        self.assertTrue(wait(lambda: headset.connected))
        self.dongle.events.put(event(0x03, 0x00, 0x01, 0x36, 0x00, 0x00))
        self.assertTrue(wait(lambda: not headset.connected))

    def test_stop_goes_back_to_hardware_mode(self):
        headset = self.start()
        headset.stop()
        self.assertEqual(self.dongle.sent(hs80.HEADSET)[-1][3:7], bytes(hs80.HARDWARE_MODE))
        self.assertEqual(self.dongle.sent(hs80.DONGLE)[-1][3:7], bytes(hs80.HARDWARE_MODE))
        self.assertTrue(all(h.closed for h in self.dongle.handles))

    def test_letting_go_sends_nothing(self):
        headset = self.start()
        headset.handle("/api/color", {"profile": "rainbow"})
        time.sleep(0.1)
        headset.release()
        count = len(self.dongle.written)
        time.sleep(0.2)
        self.assertEqual(len(self.dongle.written), count)          # no effect frames, no hardware mode
        self.assertTrue(all(h.closed for h in self.dongle.handles))
        self.assertFalse(headset.connected)

    def test_settings_are_read_when_switching(self):
        headset = self.make()
        self.assertIsNone(headset.profiles)                        # not on discovery
        self.assertFalse((Path(self.tmp.name) / "store").exists())

    def test_mute_and_mic_led(self):
        headset = self.start()
        self.dongle.events.put(event(0x03, 0x01, 0x01, 0xA6, 0x00, 0x01))
        self.assertTrue(wait(lambda: self.dongle.colors()[-1][3:6] == b"\xff\x00\x00"))
        self.dongle.events.put(event(0x03, 0x01, 0x01, 0xA6, 0x00, 0x00))
        self.assertTrue(wait(lambda: self.dongle.colors()[-1][3:6] == b"\x00\xff\xff"))
        self.assertEqual(headset.handle("/api/headset/muteIndicator", {"muteIndicator": 1}), "")
        self.assertEqual(self.dongle.colors()[-1][3:6], b"\x00\x00\x00")

    def test_battery_event(self):
        headset = self.start()
        self.dongle.events.put(event(0x03, 0x01, 0x01, 0x0F, 0x00, 0x20, 0x03))    # 800 -> 80 %
        self.assertTrue(wait(lambda: headset.battery == 80))

    def test_colours(self):
        headset = self.start()
        self.assertEqual(headset.handle("/api/headset/zoneColors", {"colorZones": {
            "0": {"red": 10, "green": 20, "blue": 30}, "1": {"red": 300, "green": 0, "blue": 0}}}), "")
        self.assertEqual(self.dongle.colors()[-1][:6], bytes((10, 20, 30, 0, 255, 255)))
        self.assertEqual(headset.handle("/api/brightness/gradual", {"brightness": 50}), "")
        self.assertEqual(self.dongle.colors()[-1][:6], bytes((5, 10, 15, 0, 127, 127)))
        self.assertEqual(headset.handle("/api/color", {"profile": "static"}), "")
        self.assertEqual(self.dongle.colors()[-1][:6], bytes((0, 127, 127, 0, 127, 127)))
        self.assertEqual(headset.handle("/api/color", {"profile": "rainbow"}), "")
        count = len(self.dongle.colors())
        self.assertTrue(wait(lambda: len(self.dongle.colors()) > count + 3))         # 25 frames a second
        self.assertEqual(headset.handle("/api/color", {"profile": "off"}), "")
        time.sleep(0.1)
        count = len(self.dongle.colors())
        self.assertEqual(self.dongle.colors()[-1], bytes(8))
        time.sleep(0.15)
        self.assertEqual(len(self.dongle.colors()), count)                          # the effect stopped
        self.assertEqual(headset.handle("/api/color", {"profile": "disco"}), "Non-existing RGB profile")
        saved = json.loads((Path(self.tmp.name) / "store" / (SERIAL + ".json")).read_text())
        self.assertEqual(saved["profiles"]["default"]["RGBProfile"], "off")
        self.assertEqual(saved["profiles"]["default"]["ZoneColors"]["0"]["Color"]["Hex"], "#0a141e")

    def test_settings(self):
        headset = self.start()
        self.assertEqual(headset.handle("/api/headset/sleep", {"sleepMode": 0}), "")
        self.assertEqual(self.commands(hs80.HEADSET)[-1], (0x01, 0x0D, 0x00))
        self.assertEqual(self.dongle.sent(hs80.HEADSET)[-1][6], 0)
        self.assertEqual(headset.handle("/api/headset/sleep", {"sleepMode": 30}), "")
        self.assertEqual(self.dongle.sent(hs80.HEADSET)[-1][3:10], bytes((0x01, 0x0E, 0x00)) +
                         (30 * 60000).to_bytes(4, "little"))
        self.assertEqual(headset.handle("/api/headset/sleep", {"sleepMode": 7}), "Invalid sleep option")
        self.assertEqual(headset.handle("/api/headset/sidetoneValue", {"sideToneValue": 40}), "Sidetone is not active")
        self.assertEqual(headset.handle("/api/headset/sidetone", {"sideTone": 1}), "")
        self.assertEqual(headset.handle("/api/headset/sidetoneValue", {"sideToneValue": 40}), "")
        sent = self.dongle.sent(hs80.HEADSET)
        self.assertEqual(sent[-3][3:7], bytes((0x01, 0x46, 0x00, 0x00)))            # sidetone on
        self.assertEqual(sent[-2][3:8], bytes((0x01, 0x47, 0x00)) + (400).to_bytes(2, "little"))
        bands = {str(i): 0 for i in range(1, 11)}
        self.assertEqual(headset.handle("/api/headset/equalizer", {"equalizers": bands}), "Nothing to update")
        bands["3"] = 6
        self.assertEqual(headset.handle("/api/headset/equalizer", {"equalizers": bands}), "")
        self.assertEqual(headset.profile["Equalizers"]["3"]["Value"], 6)
        bands["3"] = 13
        self.assertEqual(headset.handle("/api/headset/equalizer", {"equalizers": bands}), "Unable to update equalizer")
        self.assertIsNone(headset.handle("/api/headset/anc", {}))

    def test_profiles_and_button(self):
        headset = self.start()
        self.assertEqual(headset.handle("/api/userProfile", {"userProfileName": "music"}, "PUT"), "")
        self.assertEqual(headset.handle("/api/userProfile", {"userProfileName": "a-b"}, "PUT"),
                         "Profile name can only contain letters and numbers")
        self.assertEqual(headset.handle("/api/userProfile/change", {"userProfileName": "music"}), "")
        self.assertEqual(headset.active_name, "music")
        self.assertEqual(headset.handle("/api/userProfile/delete", {"userProfileName": "music"}, "DELETE"),
                         "Unable to delete an active profile")
        # The scroll press switches profiles once set to "Profile switch"
        button = {"keyIndex": 1, "enabled": False, "pressAndHold": False, "onRelease": False,
                  "keyAssignmentType": 3, "keyAssignmentValue": 30}
        self.assertEqual(headset.handle("/api/headset/updateKeyAssignment", button), "")
        self.dongle.events.put(event(0x03, 0x01, 0x02, 0x01))
        self.dongle.events.put(event(0x03, 0x01, 0x02, 0x00))
        self.assertTrue(wait(lambda: ("key", 30) in self.input_calls))
        self.assertEqual(headset.handle("/api/headset/updateKeyAssignment", dict(button, pressAndHold=True)), "")
        self.dongle.events.put(event(0x03, 0x01, 0x02, 0x01))
        self.assertTrue(wait(lambda: ("key_hold", 30, True) in self.input_calls))
        self.dongle.events.put(event(0x03, 0x01, 0x02, 0x00))
        self.assertTrue(wait(lambda: ("key_hold", 30, False) in self.input_calls))
        self.assertEqual(headset.handle("/api/headset/updateKeyAssignment", dict(button, keyAssignmentType=11)), "")
        self.dongle.events.put(event(0x03, 0x01, 0x02, 0x01))
        self.dongle.events.put(event(0x03, 0x01, 0x02, 0x00))
        self.assertTrue(wait(lambda: headset.active_name == "default"))
        self.assertEqual(headset.handle("/api/userProfile/delete", {"userProfileName": "music"}, "DELETE"), "")
        self.assertEqual(sorted(headset.device_json()["userProfiles"]), ["default"])

    def test_takes_over_openlinkhubs_settings(self):
        profile = hs80.default_profile(SERIAL)
        profile.update({"RGBProfile": "wave", "SleepMode": 30, "DisableMicIndicator": 1})
        (self.olh / "profiles" / (SERIAL + ".json")).write_text(json.dumps(profile))
        (self.olh / "profiles" / (SERIAL + "-123.json")).write_text(json.dumps(dict(profile, Active=False)))
        (self.olh / "profiles" / "OTHER.json").write_text(json.dumps(dict(profile, Serial="OTHER")))
        (self.olh / "key-assignments").mkdir()
        (self.olh / "key-assignments" / "hs80maxW.json").write_text(json.dumps({"1": {
            "name": "Scroll Press", "default": False, "actionType": 11, "actionCommand": 0, "actionHold": False,
            "buttonIndex": 0, "onRelease": False}}))
        (self.olh / "rgb").mkdir()
        wave = dict(rgb.default_profiles()["wave"], speed=2)
        (self.olh / "rgb" / (SERIAL + ".json")).write_text(json.dumps({"profiles": {"wave": wave, "keyboard": {}}}))
        headset = self.make()
        self.assertEqual(sorted(headset.device_json()["userProfiles"]), ["123", "default"])
        self.assertEqual((headset.profile["RGBProfile"], headset.profile["SleepMode"]), ("wave", 30))
        self.assertEqual(headset.buttons["1"]["actionType"], 11)
        self.assertEqual(headset.rgb["wave"]["speed"], 2)
        self.assertNotIn("keyboard", headset.rgb)
        # From now on its own file is used
        (self.olh / "profiles" / (SERIAL + ".json")).unlink()
        self.assertEqual(self.make().profile["RGBProfile"], "wave")


class TemperaturesTest(unittest.TestCase):
    def test_cpu_and_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n, (name, value) in enumerate((("nvme", "40000"), ("k10temp", "55500"))):
                folder = Path(tmp) / ("hwmon%d" % n)
                folder.mkdir()
                (folder / "name").write_text(name + "\n")
                (folder / "temp1_input").write_text(value + "\n")

            class Out:
                stdout = "47\n"
            reader = temperatures.Temperatures(Path(tmp), run=lambda *a, **k: Out())
            self.assertEqual((reader.cpu(), reader.gpu()), (55.5, 47.0))


class ServerTest(unittest.TestCase):
    def test_profiles_and_batteries_through_the_server(self):
        olh, olh_url, state = fake_openlinkhub.start()
        tmp = tempfile.TemporaryDirectory()
        dongle = FakeDongle()
        store = Store(Path(tmp.name) / "store", Path(tmp.name) / "olh" / "profiles")
        headset = hs80.Hs80(INFO, store, dongle.open, serial="553F75E3327B1415", sleep=lambda s: None,
                            temps=FakeTemps())
        core = Core(olh_url, lambda: [headset], log=lambda text: None)
        server = serve(core, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d" % server.server_port

        def call(method, path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            request = urllib.request.Request(url + path, data=data, method=method,
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as reply:
                return json.loads(reply.read())
        try:
            core.check()
            self.assertTrue(wait(lambda: headset.connected))
            self.assertEqual(call("PUT", "/api/userProfile", {"deviceId": SERIAL, "userProfileName": "game"})["status"], 1)
            self.assertIn("game", call("GET", "/api/devices/" + SERIAL)["device"]["userProfiles"])
            answer = call("DELETE", "/api/userProfile/delete", {"deviceId": SERIAL, "userProfileName": "game"})
            self.assertEqual(answer["status"], 1)
            battery = call("GET", "/api/systray")["data"]["battery"]
            self.assertEqual(battery[SERIAL], {"Device": "HS80 MAX WIRELESS", "Level": 85})
            self.assertIn("M1", battery)                        # OpenLinkHub's batteries stay
            # PUT for a device OpenLinkHub drives still goes there
            call("PUT", "/api/userProfile", {"deviceId": "HS1", "userProfileName": "abc"})
            self.assertEqual(state.requests[-1][:2], ("PUT", "/api/userProfile"))
        finally:
            core.stop()
            server.shutdown()
            server.server_close()
            olh.shutdown()
            olh.server_close()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
