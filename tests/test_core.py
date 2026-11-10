# Tests for quartercore-core: HID lookup, the power supply driver and the API server
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests
# A simulated power supply answers the HID commands; nothing is sent to real hardware.

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fake_openlinkhub  # noqa: E402
from quartercore.core import hid, psu, xeneon  # noqa: E402
from quartercore.core.server import Core, serve  # noqa: E402
from quartercore.core.store import Store  # noqa: E402

USB = "/devices/pci0000:00/0000:00:14.0/usb1/1-9/1-9.3/1-9.3.4"


def encode_linear11(value, exponent):
    """The other way round of psu.linear11, for the simulated power supply."""
    fraction = int(round(value / 2.0 ** exponent))
    return (fraction & 0x7FF) | ((exponent & 0x1F) << 11)


class FakePsu:
    """Answers like an HX1500i: the reply starts with the mode and command of the packet."""
    values = {psu.INPUT_VOLTAGE: (230, 0), psu.FAN_SPEED: (0, 0), 0x8D: (42.5, -2), 0x8E: (40.25, -2),
              psu.POWER_OUT: (140, 0), psu.GET_VOLTS: (12.0625, -4), psu.GET_AMPS: (7.25, -2),
              psu.GET_WATTS: (87.5, -1)}

    def __init__(self, node):
        self.node = node
        self.sent = []
        self.closed = False

    def transfer(self, packet, match, timeout=1.0):
        self.sent.append(bytes(packet))
        reply = bytearray(64)
        reply[0], reply[1] = packet[1], packet[2]
        if packet[1] == psu.CMD_READ and packet[2] in self.values:
            raw = encode_linear11(*self.values[packet[2]])
            reply[2], reply[3] = raw & 0xFF, raw >> 8
        return bytes(reply)

    def close(self):
        self.closed = True


def make_sysfs(root):
    """/sys/class/hidraw/hidraw4 -> .../1-9.3.4/1-9.3.4:1.0/0003:1B1C:1C1F.000D, like the real one."""
    root = Path(root)
    usb = root / "sys" / USB.lstrip("/")
    hid_dir = usb / "1-9.3.4:1.0" / "0003:1B1C:1C1F.000D"
    hid_dir.mkdir(parents=True)
    (usb / "idVendor").write_text("1b1c\n")
    (usb / "1-9.3.4:1.0" / "bInterfaceNumber").write_text("00\n")
    (hid_dir / "uevent").write_text("DRIVER=corsair-psu\nHID_ID=0003:00001B1C:00001C1F\n"
                                    "HID_NAME=CORSAIR HX1500i Power Supply\n")
    hidraw = root / "class" / "hidraw" / "hidraw4"
    hidraw.mkdir(parents=True)
    (hidraw / "device").symlink_to(hid_dir)
    other = root / "class" / "hidraw" / "hidraw5"
    other.mkdir(parents=True)
    (other / "uevent").write_text("")
    hwmon = root / "class" / "hwmon" / "hwmon9"
    hwmon.mkdir(parents=True)
    (hwmon / "device").symlink_to(hid_dir)
    for name, value in (("name", "corsairpsu"), ("in0_input", "230000"), ("fan1_input", "0"),
                        ("temp1_input", "42000"), ("temp2_input", "40250"), ("power1_input", "140000000"),
                        ("in1_input", "12062"), ("curr2_input", "7250"), ("power2_input", "87500000"),
                        ("in2_input", "5050"), ("curr3_input", "2000"), ("power3_input", "10000000"),
                        ("in3_input", "3360"), ("curr4_input", "1500"), ("power4_input", "5000000")):
        (hwmon / name).write_text(value + "\n")
    return root


class ProtocolTest(unittest.TestCase):
    def test_linear11(self):
        for value, exponent in ((230, 0), (42.5, -2), (12.0625, -4), (-3, 0), (0.5, -1)):
            raw = encode_linear11(value, exponent)
            self.assertAlmostEqual(psu.linear11(bytes([0, 0, raw & 0xFF, raw >> 8])), value)

    def test_packets(self):
        p = psu.packet(psu.CMD_WRITE, psu.CMD_SET_FAN_MODE, psu.FAN_MODE_MANUAL)
        self.assertEqual((len(p), p[0], p[1], p[2], p[3]), (65, 0, 0x02, 0xF0, 0x01))
        self.assertEqual(psu.fan_packets(0), [psu.packet(0x02, 0xF0, 0x00)])
        manual = psu.fan_packets(7)
        self.assertEqual([(b[2], b[3]) for b in manual], [(0xF0, 0x01), (0x3B, 70)])
        self.assertEqual(psu.fan_packets(2)[1][3], 40)              # never below 40 %


class SysfsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_sysfs(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_and_serial(self):
        found = hid.find(psu.VENDOR, psu.PRODUCTS, self.root / "class" / "hidraw")
        self.assertEqual(len(found), 1)
        info = found[0]
        self.assertEqual((info["node"], info["product"], info["interface"]), ("/dev/hidraw4", 0x1C1F, 0))
        self.assertTrue(info["usbPath"].endswith("/usb1/1-9/1-9.3/1-9.3.4"))
        # The id OpenLinkHub gives this power supply on the real machine
        self.assertEqual(hid.serial_for(USB), "b800191a9d6a8b0c244b2f158a6914e3")

    def test_hwmon_readings(self):
        folder = psu.hwmon_folder("", self.root / "class" / "hwmon")
        r = psu.read_hwmon(folder)
        self.assertEqual((r["inputVoltage"], r["vrm"], r["case"], r["powerOut"]), (230, 42, 40.25, 140))
        self.assertEqual(r["rails"][0], (12.062, 7.25, 87.5))
        ch = psu.channels("HX1500i", r)
        self.assertTrue(ch["0"]["MainPSU"] and ch["1"]["HasSpeed"] and ch["5"]["HasVolts"])
        self.assertEqual((ch["2"]["temperatureString"], ch["6"]["volts"]), ("42.0 °C", 5.05))

    def test_the_page_shows_it(self):
        from quartercore.backend import page_kind, psu_view
        store = Store(Path(self.tmp.name) / "store", Path(self.tmp.name) / "none")
        driver = psu.discover(store, self.root / "class" / "hidraw", FakePsu, self.root / "class" / "hwmon")[0]
        driver.refresh()
        device = driver.device_json()
        self.assertEqual(page_kind(device), "psu")
        view = psu_view(device)
        self.assertEqual((view["product"], view["inputVoltage"], view["power"], view["outputPower"]),
                         ("HX1500i", 230, 140, 140))
        self.assertEqual([r["name"] for r in view["rails"]], ["12V Rail", "5V Rail", "3V Rail"])
        self.assertEqual(len(view["temperatures"]), 2)


class DriverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_sysfs(self.tmp.name)
        self.store = Store(Path(self.tmp.name) / "store", Path(self.tmp.name) / "olh")
        self.driver = psu.discover(self.store, self.root / "class" / "hidraw", FakePsu, Path(self.tmp.name) / "none")[0]

    def tearDown(self):
        self.tmp.cleanup()

    def test_readings_over_hid_without_the_kernel_driver(self):
        self.driver.refresh()
        r = self.driver.readings
        self.assertEqual((r["inputVoltage"], r["vrm"], r["case"], r["powerOut"]), (230, 42.5, 40.25, 140))
        self.assertEqual(r["rails"][1], (12.0625, 7.25, 87.5))
        # Each read starts with the init command, like psuhid.go
        sent = self.driver.device.sent
        self.assertEqual((sent[0][1], sent[0][2]), (psu.CMD_INIT, psu.CMD_READ))

    def test_fan_mode(self):
        self.assertEqual(self.driver.set_fan_mode(8), "")
        sent = self.driver.device.sent
        self.assertEqual([(b[1], b[2], b[3]) for b in sent], [(0x02, 0xF0, 0x01), (0x02, 0x3B, 80)])
        saved = json.loads((Path(self.tmp.name) / "store" / ("%s.json" % self.driver.serial)).read_text())
        self.assertEqual(saved, {"FanMode": 8})
        self.assertEqual(self.driver.set_fan_mode(11), "Invalid fan mode")
        self.assertEqual(len(self.driver.device.sent), 2)

    def test_stop_goes_back_to_the_power_supplys_curve(self):
        self.driver.set_fan_mode(10)
        device = self.driver.device
        self.driver.stop()
        self.assertEqual((device.sent[-1][2], device.sent[-1][3]), (0xF0, 0x00))
        self.assertTrue(device.closed)

    def test_settings_from_openlinkhub(self):
        folder = Path(self.tmp.name) / "olh"
        folder.mkdir()
        (folder / ("%s.json" % self.driver.serial)).write_text(json.dumps({"FanMode": 6, "Active": True}))
        driver = psu.discover(self.store, self.root / "class" / "hidraw", FakePsu, Path(self.tmp.name) / "none")[0]
        self.assertEqual(driver.settings, {"FanMode": 6})
        driver.start()
        self.assertEqual(driver.device.sent[-1][3], 60)


class FakeScreen:
    """The XENEON EDGE: every report gets a reply."""

    def __init__(self, node):
        self.written, self.reads, self.closed = [], 0, False

    def write(self, data):
        self.written.append(bytes(data))

    def read(self, timeout):
        self.reads += 1
        return bytes(64)

    def close(self):
        self.closed = True


class XeneonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "store", Path(self.tmp.name) / "olh")
        info = {"node": "/dev/hidraw6", "product": xeneon.PRODUCT, "interface": 0, "usbPath": "/devices/x/1-1.3"}
        self.screen = xeneon.XeneonEdge(info, self.store, FakeScreen, serial="411226035656")

    def tearDown(self):
        self.tmp.cleanup()

    def sent(self):
        return [(b[7], b[8], b[9]) for b in self.screen.device.written]

    def test_packet(self):
        p = xeneon.packet(xeneon.BRIGHTNESS, 70)
        self.assertEqual((len(p), p[0], p[1], p[2], p[7], p[8], p[9]), (65, 0, 0x01, 0x0F, 0x02, 0x02, 70))
        self.assertEqual(p[3:7], bytes(4))

    def test_start_sends_the_saved_values(self):
        self.screen.start()
        self.assertEqual(self.sent(), [(2, 2, 50), (2, 1, 50), (2, 0, 100), (3, 1, 150), (3, 2, 126), (3, 3, 140)])
        self.assertEqual(self.screen.device.reads, 6)      # one reply read per report

    def test_settings(self):
        self.assertEqual(self.screen.handle("/api/brightness/gradual", {"brightness": 80}), "")
        self.assertEqual(self.screen.handle("/api/colortone", {"colorTone": 200, "colorToneType": 2}), "")
        self.assertEqual(self.sent(), [(2, 2, 80), (3, 3, 200)])
        saved = json.loads((Path(self.tmp.name) / "store" / "411226035656.json").read_text())
        self.assertEqual((saved["Brightness"], saved["ColorToneBlue"]), (80, 200))
        self.assertEqual(self.screen.handle("/api/contrast/gradual", {"contrast": 101}), "Invalid value")
        self.assertEqual(self.screen.handle("/api/colortone", {"colorTone": 1, "colorToneType": 3}),
                         "Invalid colour tone")
        self.assertIsNone(self.screen.handle("/api/color", {}))
        self.assertEqual(len(self.sent()), 2)

    def test_reset_and_stop(self):
        self.screen.handle("/api/backlight/gradual", {"backlight": 20})
        self.screen.reset()
        self.assertEqual(self.screen.settings, xeneon.DEFAULTS)
        device = self.screen.device
        self.screen.stop()
        # What OpenLinkHub sends when it stops
        self.assertEqual([(b[7], b[8], b[9]) for b in device.written[-6:]],
                         [(2, 2, 50), (2, 1, 100), (2, 0, 50), (3, 1, 150), (3, 2, 126), (3, 3, 140)])
        self.assertTrue(device.closed)

    def test_settings_from_openlinkhub(self):
        folder = Path(self.tmp.name) / "olh"
        folder.mkdir()
        (folder / "411226035656.json").write_text(json.dumps({"Brightness": 30, "Contrast": 60, "Backlight": 90,
                                                              "ColorToneRed": 1, "WidgetAreas": {}}))
        info = {"node": "/dev/hidraw6", "product": xeneon.PRODUCT, "interface": 0, "usbPath": "/devices/x"}
        screen = xeneon.XeneonEdge(info, self.store, FakeScreen, serial="411226035656")
        self.assertEqual((screen.settings["Brightness"], screen.settings["ColorToneRed"],
                          screen.settings["ColorToneGreen"]), (30, 1, 126))

    def test_the_page_shows_it(self):
        from quartercore.backend import page_kind, xeneon_view
        device = self.screen.device_json()
        self.assertEqual(page_kind(device), "xeneon")
        view = xeneon_view(device)
        self.assertEqual((view["brightness"], view["backlight"], view["tones"], view["drivenBy"]),
                         (50, 100, [150, 126, 140], "quartercore-core"))


class FakeDriver:
    """A device for the server tests."""

    def __init__(self, serial):
        self.serial, self.product = serial, "HX1500i"
        self.device = FakePsu("/dev/null")
        self.started = self.stopped = False
        self.fan = 0

    def start(self):
        self.started = True

    def refresh(self):
        pass

    def stop(self):
        self.stopped = True

    def set_fan_mode(self, mode):
        if not 0 <= mode <= 10:
            return "Invalid fan mode"
        self.fan = mode
        return ""

    def handle(self, path, body):
        if path == "/api/psu/speed":
            return self.set_fan_mode(int(body.get("fanMode", -1)))
        return None

    def summary(self):
        return {"Product": self.product, "Serial": self.serial}

    def device_json(self):
        return {"serial": self.serial, "product": self.product, "Template": "psuhid.html",
                "DeviceProfile": {"FanMode": self.fan}, "FanModes": {"0": "Default"}, "devices": {}}


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.olh, self.olh_url, self.state = fake_openlinkhub.start()
        self.mine, self.listed = FakeDriver("PSUX"), FakeDriver("PSU1")    # PSU1 is in OpenLinkHub's list
        self.core = Core(self.olh_url, lambda: [self.mine, self.listed], log=lambda text: None)
        self.server = serve(self.core, 0)
        self.url = "http://127.0.0.1:%d" % self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.olh.shutdown()

    def get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=5) as reply:
            return json.loads(reply.read())

    def post(self, path, body):
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as reply:
            return json.loads(reply.read())

    def test_takes_over_only_what_openlinkhub_leaves_alone(self):
        self.core.check()
        self.assertEqual(self.core.owned, {"PSUX"})
        self.assertTrue(self.mine.started)
        self.assertFalse(self.listed.started)

    def test_nothing_without_openlinkhub(self):
        core = Core("http://127.0.0.1:1", lambda: [self.mine], log=lambda text: None)
        core.check()
        self.assertEqual(core.owned, set())
        standalone = Core("http://127.0.0.1:1", lambda: [self.mine], standalone=True, log=lambda text: None)
        standalone.check()
        self.assertEqual(standalone.owned, {"PSUX"})

    def test_lets_go_when_openlinkhub_drives_it_again(self):
        self.core.check()
        self.mine.serial = "PSU1"
        self.core.drivers = {"PSU1": self.mine}
        self.core.owned = {"PSU1"}
        self.core.check()
        self.assertEqual(self.core.owned, set())
        self.assertFalse(self.mine.stopped)          # nothing sent: OpenLinkHub sets its own fan mode

    def test_api(self):
        self.core.check()
        devices = self.get("/api/devices/")["devices"]
        self.assertIn("PSUX", devices)
        self.assertIn("HUB1", devices)                                    # from OpenLinkHub
        self.assertEqual(self.get("/api/devices/PSUX")["device"]["Template"], "psuhid.html")
        self.assertEqual(self.get("/api/devices/HUB1")["device"]["product"], "iCUE LINK System Hub")
        answer = self.post("/api/psu/speed", {"deviceId": "PSUX", "fanMode": 5})
        self.assertEqual((answer["status"], self.mine.fan), (1, 5))
        self.assertEqual(self.post("/api/psu/speed", {"deviceId": "PSUX", "fanMode": 50})["status"], 0)
        self.assertIn("Not supported", self.post("/api/color", {"deviceId": "PSUX"})["message"])
        # Other devices go on to OpenLinkHub
        self.post("/api/speed", {"deviceId": "HUB1", "channelId": 1, "profile": "Quiet"})
        self.assertEqual(self.state.requests[-1][1:], ("/api/speed", {"deviceId": "HUB1", "channelId": 1,
                                                                       "profile": "Quiet"}))
        self.assertEqual(self.get("/api/core")["data"]["devices"], {"PSUX": "HX1500i"})

    def test_web_pages_go_to_openlinkhub(self):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            opener.open(self.url + "/device/HUB1", timeout=5)
        self.assertEqual(caught.exception.code, 302)
        caught.exception.close()
        self.assertEqual(caught.exception.headers["Location"], self.olh_url + "/device/HUB1")

    def test_openlinkhub_down(self):
        self.olh.shutdown()
        self.olh.server_close()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/api/speed")
        self.assertEqual(caught.exception.code, 502)
        caught.exception.close()

    def test_the_window_works_through_the_core(self):
        from PySide6.QtCore import QCoreApplication
        from quartercore.backend import Backend
        from test_backend import wait
        app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
        self.core.check()
        backend = Backend(self.url)
        backend.refreshDevices()
        self.assertTrue(wait(lambda: {d["serial"] for d in backend.devices} >= {"PSUX", "HUB1"}))
        backend.selectDevice("PSUX")
        self.assertTrue(wait(lambda: backend.active.get("page") == "psu"))
        backend.setPsuFanMode(4)
        self.assertTrue(wait(lambda: self.mine.fan == 4))
        # Let the last replies arrive before the Backend goes away
        backend.system_timer.stop()
        backend.devices_timer.stop()
        wait(lambda: False, 500)
        self.backend = backend


if __name__ == "__main__":
    unittest.main()
