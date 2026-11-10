# Tests for reading the sensors, the media player and the XENEON EDGE layout file
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests
# Uses made-up /sys and /proc files in a temporary folder, never the real ones.

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from quartercore import edgelayout, media, sensors  # noqa: E402


def write(root, path, text):
    target = Path(root) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


class SensorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        hw = self.root / "hwmon"
        write(hw, "hwmon0/name", "acpitz\n")
        write(hw, "hwmon0/temp1_input", "16800\n")
        write(hw, "hwmon1/name", "nvme\n")
        write(hw, "hwmon1/temp1_input", "34850\n")
        write(hw, "hwmon1/device/model", "Samsung SSD 970 EVO 1TB     \n")
        write(hw, "hwmon2/name", "coretemp\n")
        write(hw, "hwmon2/temp1_input", "41234\n")
        write(hw, "hwmon3/name", "amdgpu\n")
        write(hw, "hwmon3/temp1_input", "55000\n")
        write(hw, "hwmon4/name", "nvme\n")       # no model: left out, like OpenLinkHub
        write(hw, "hwmon4/temp1_input", "30000\n")
        self.hwmon = hw

    def tearDown(self):
        self.tmp.cleanup()

    def test_cpu_temperature(self):
        self.assertEqual(sensors.cpu_temperature(self.hwmon), 41.23)
        self.assertEqual(sensors.cpu_temperature(self.hwmon, chip="acpitz"), 16.8)
        self.assertIsNone(sensors.cpu_temperature(self.root / "missing"))

    def test_storage_and_amd(self):
        self.assertEqual(sensors.storage_temperatures(self.hwmon), [
            {"Key": "hwmon1", "Model": "Samsung SSD 970 EVO 1TB", "Temperature": 34, "TemperatureString": "34.0 °C"}])
        self.assertEqual(sensors.amd_gpu_temperature(self.hwmon), 55.0)
        write(self.root, "drm/card1/device/gpu_busy_percent", "37\n")
        self.assertEqual(sensors.amd_gpu_load(self.root / "drm"), 37)

    def test_cpu_load(self):
        stat = self.root / "stat"
        stat.write_text("cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 1 2 3 4\n")
        load = sensors.CpuLoad(stat)
        load.read()
        stat.write_text("cpu  150 0 150 900 0 0 0 0 0 0\n")
        self.assertEqual(load.read(), 50.0)          # 100 busy of 200

    def test_memory(self):
        meminfo = self.root / "meminfo"
        meminfo.write_text("MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 750 kB\nSwapTotal: 400 kB\n"
                           "SwapFree: 300 kB\n")
        m = sensors.memory_usage(meminfo)
        self.assertEqual((m["Used"], m["UsedPercent"], m["SwapUsed"], m["SwapPercent"]), (250 * 1024, 25.0, 100 * 1024, 25.0))
        meminfo.write_text("MemTotal: 1000 kB\n")
        self.assertIsNone(sensors.memory_usage(meminfo))

    def test_mounts(self):
        mountinfo = self.root / "mountinfo"
        mountinfo.write_text(
            "29 1 0:26 / / rw,relatime shared:1 - btrfs /dev/nvme0n1p3 rw\n"
            "30 29 0:26 /home /home rw shared:2 - btrfs /dev/nvme0n1p3 rw\n"
            "31 29 0:5 / /proc rw - proc proc rw\n"
            "32 29 8:17 / /mnt/My\\040Games rw - ext4 /dev/sdb1 rw\n"
            "33 29 0:26 / / rw - btrfs /dev/nvme0n1p3 rw\n")
        rows = sensors.storage_mounts(mountinfo)
        self.assertEqual([r["MountPoint"] for r in rows], ["/", "/home", "/mnt/My Games"])
        self.assertEqual(rows[2]["Filesystem"], "ext4")

    def test_nvidia_output(self):
        self.assertEqual(sensors.parse_nvidia("39, 23\n"), (39.0, 23.0))
        self.assertEqual(sensors.parse_nvidia(""), (None, None))
        self.assertEqual(sensors.parse_nvidia("[N/A], [N/A]"), (None, None))


class MediaTest(unittest.TestCase):
    output = json.dumps({"type": "a{sv}", "data": [{
        "PlaybackStatus": {"type": "s", "data": "Playing"}, "Position": {"type": "x", "data": 65000000},
        "Metadata": {"type": "a{sv}", "data": {
            "xesam:title": {"type": "s", "data": "Song"}, "xesam:artist": {"type": "as", "data": ["A", "B"]},
            "mpris:length": {"type": "x", "data": 200000000}}}}]})

    def test_busctl_output(self):
        info = media.now_playing(media.parse_busctl(self.output))
        self.assertEqual(info, {"playing": True, "title": "Song", "artists": ["A", "B"], "album": "",
                                "position": 65.0, "length": 200.0})
        self.assertIsNone(media.parse_busctl("not json"))

    def test_first_playing_player(self):
        paused = {"playing": False}
        playing = {"playing": True, "title": "x"}
        self.assertEqual(media.choose({"org.mpris.MediaPlayer2.b": playing, "org.mpris.MediaPlayer2.a": paused,
                                       "org.mpris.MediaPlayer2.c": None}), ("org.mpris.MediaPlayer2.b", playing))
        self.assertEqual(media.choose({"org.mpris.MediaPlayer2.a": paused}), (None, None))

    def test_buttons(self):
        self.assertEqual(media.METHODS["play"], "PlayPause")      # upstream sends "previous" here
        self.assertIn("-l", media.VOLUME["volumeUp"])             # never above 100 %


class LayoutFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sub" / "xeneon-edge.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_layout_fills_the_grid(self):
        layout = edgelayout.default_layout()
        self.assertEqual(len(layout["items"]), 9)
        self.assertIsNone(edgelayout.free_spot(layout["items"]))
        self.assertIsNone(edgelayout.check_settings(layout["items"][0]["settings"]))
        for item in layout["items"]:
            self.assertIsNone(edgelayout.check_settings(item["settings"]), item["widgetId"])

    def test_every_widget_has_valid_defaults(self):
        from quartercore.edge import WIDGET_DEFAULTS, widget_settings
        for widget_id in WIDGET_DEFAULTS:
            settings = widget_settings(widget_id)
            if settings["template"] == "xeneon-temperature-history":
                settings["source"] = "cpu"
            self.assertIsNone(edgelayout.check_settings(settings), settings["template"])

    def test_save_and_load(self):
        layout = edgelayout.default_layout()
        edgelayout.save(layout, self.path)
        self.assertEqual(edgelayout.load(self.path), layout)
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_load_skips_bad_items(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"items": [
            {"widgetId": 1, "x": 0, "y": 0, "w": 4, "h": 4},
            {"widgetId": 1, "x": 4, "y": 0, "w": 4, "h": 4},        # twice
            {"widgetId": 99, "x": 0, "y": 0, "w": 4, "h": 4},       # unknown
            {"widgetId": 2, "x": 22, "y": 0, "w": 4, "h": 4},       # outside the grid
            {"widgetId": 3, "x": 4, "y": 4},                        # incomplete
            {"widgetId": 6, "x": 8, "y": 0, "w": 4, "h": 4, "settings": {"max": 120}}]}))
        layout = edgelayout.load(self.path)
        self.assertEqual([i["widgetId"] for i in layout["items"]], [1, 6])
        self.assertEqual(layout["items"][1]["settings"]["max"], 120)
        self.path.write_text("{broken")
        self.assertIsNone(edgelayout.load(self.path))

    def test_checks(self):
        from quartercore.edge import widget_settings
        s = widget_settings(2)
        self.assertIsNone(edgelayout.check_settings(s))
        for name, value in (("latitude", 91), ("city", " "), ("refreshInterval", 2), ("unit", "K")):
            self.assertIsNotNone(edgelayout.check_settings(dict(s, **{name: value})), name)
        history = dict(widget_settings(12), source="device", deviceId="")
        self.assertIsNotNone(edgelayout.check_settings(history))
        self.assertIsNone(edgelayout.check_settings(dict(history, deviceId="HUB1")))
        self.assertIsNotNone(edgelayout.check_settings(dict(widget_settings(6), dataColor="red")))

    def test_import_from_openlinkhub(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import fake_openlinkhub as fake
        areas = [{"areaId": a, "widgetId": w} for a, w in fake.EDGE_AREAS[2]]
        profile = fake.initial_edge(2)["device"]["DeviceProfile"]["WidgetAreas"]
        layout = edgelayout.from_openlinkhub(areas, fake.EDGE_LAYOUT_2, profile)
        items = {i["widgetId"]: i for i in layout["items"]}
        self.assertTrue(items[9]["hidden"])                      # hidden in the web editor
        self.assertNotIn(0, items)                               # the HTML widget is left out
        self.assertEqual(items[13]["settings"]["deviceId"], "HUB1")


if __name__ == "__main__":
    unittest.main()
