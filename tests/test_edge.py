# Tests for the native XENEON EDGE kiosk against the fake OpenLinkHub
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QObject, Signal  # noqa: E402

import fake_openlinkhub  # noqa: E402
from quartercore import edge as e, edgelayout  # noqa: E402
from quartercore.edgeeditor import EdgeEditor  # noqa: E402
from quartercore.backend import Backend  # noqa: E402
from test_backend import wait  # noqa: E402


class LayoutTest(unittest.TestCase):
    def test_all_widgets_have_defaults(self):
        # The 16 of OpenLinkHub and Quartercore's own 17-23, each with its own template
        self.assertEqual(sorted(e.WIDGET_DEFAULTS), list(range(1, 24)))
        self.assertEqual(len({w["template"] for w in e.WIDGET_DEFAULTS.values()}), 23)
        from quartercore.edgeeditor import WIDGET_NAMES
        self.assertEqual(sorted(WIDGET_NAMES), sorted(e.WIDGET_DEFAULTS))

    def test_default_layout_follows_the_upstream_page(self):
        items = {i["widgetId"]: i for i in e.build_items(e.default_areas(), None)}
        self.assertEqual(sorted(items), [1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual((items[1]["x"], items[1]["w"]), (0, 8))         # left
        self.assertEqual((items[7]["x"], items[7]["y"]), (12, 0))       # rings in pairs
        self.assertEqual((items[3]["x"], items[4]["y"]), (16, 8))       # right
        # The ring pair without widgets below (areas 7 and 8) is filled by growing down
        self.assertEqual(items[8]["h"], 8)

    def test_saved_layout_hidden_and_custom(self):
        areas = [{"areaId": a, "widgetId": w} for a, w in fake_openlinkhub.EDGE_AREAS[2]]
        items = {i["key"]: i for i in e.build_items(areas, fake_openlinkhub.EDGE_LAYOUT_2)}
        self.assertEqual((items["widget:12"]["h"], items["widget:13"]["y"]), (7, 7))
        self.assertNotIn("widget:9", items)                             # hidden
        self.assertEqual(items["custom:crypto-ticker"]["template"], "custom")
        self.assertIn("widget:14", items)                               # not saved yet: upstream place

    def test_settings_overlay_defaults(self):
        s = e.widget_settings(2, {"city": "Amsterdam", "unit": ""})
        self.assertEqual((s["city"], s["unit"], s["template"]), ("Amsterdam", "°C", "xeneon-weather"))

    def test_edge_screen(self):
        class Screen:
            def __init__(self, w, h): self.w, self.h = w, h
            def size(self):
                from PySide6.QtCore import QSize
                return QSize(self.w, self.h)
        self.assertIsNone(e.find_edge_screen([Screen(3840, 2160)]))
        portrait = Screen(720, 2560)
        self.assertIs(e.find_edge_screen([Screen(3840, 2160), portrait]), portrait)


class WidgetDataTest(unittest.TestCase):
    devices = fake_openlinkhub.STATS_DEVICES

    def test_numbers(self):
        self.assertEqual((e.number(27), e.number("27.0 °C"), e.number("686 RPM")), (27.0, 27.0, 686.0))
        self.assertIsNone(e.number(""))
        self.assertEqual(e.to_unit(100, "°F"), 212)

    def test_device_values(self):
        self.assertEqual(e.device_value(self.devices, {"deviceId": "HUB1", "channelId": 2, "unit": "°C"}, True), 26.5)
        self.assertIsNone(e.device_value(self.devices, {"deviceId": "HUB1", "channelId": 1}, True))   # no sensor
        self.assertEqual(e.device_value(self.devices, {"deviceId": "HUB1", "channelId": 1}, False), 700)
        self.assertIsNone(e.device_value(self.devices, {"deviceId": "nope"}, False))

    def test_cooling(self):
        rows = e.cooling_rows(self.devices, {"deviceId": "HUB1", "max": 3000, "unit": "°C"})
        self.assertEqual([r["name"] for r in rows], ["iCUE LINK RX RGB", "iCUE LINK TITAN 360", "Temperature probe"])
        self.assertEqual((rows[1]["temperature"], rows[1]["rpm"], rows[2]["fill"]), ("26.5 °C", "2400 RPM", -1))

    def test_bytes_memory_storage(self):
        self.assertEqual((e.format_bytes(512), e.format_bytes(1536), e.format_bytes(8589934592)),
                         ("512 B", "1.5 KiB", "8.0 GiB"))
        self.assertFalse(e.memory_view({"Total": 0})["available"])
        self.assertEqual(e.memory_view({"Total": 1024, "Used": 512, "UsedPercent": 50})["used"], "512 B")
        rows = e.storage_rows([{"MountPoint": "/"}, {"MountPoint": "/home"}], {"mountPoint": "/home"})
        self.assertEqual([r["mountPoint"] for r in rows], ["/home"])
        temps = e.storage_temperatures([{"Key": "a", "Model": "SSD", "Temperature": 30},
                                        {"Key": "b", "Model": "HDD", "Temperature": None}],
                                       {"storageSensor": "*", "unit": "°F"})
        self.assertEqual(temps, [{"name": "SSD / a", "value": "86.0 °F"}])

    def test_other_batteries(self):
        from quartercore import batteries
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mouse = root / "hid" / "razermouse" / "0003:1532:00A8.000F"
            mouse.mkdir(parents=True)
            for name, text in (("charge_level", "204\n"), ("charge_status", "1\n"), ("device_serial", "PM1\n"),
                               ("device_type", "Razer Naga V2 Pro (Wireless)\n")):
                (mouse / name).write_text(text)
            (root / "hid" / "razermouse" / "0003:1532:00A8.0010").mkdir()       # an interface without a battery
            self.assertEqual(batteries.razer_batteries(root / "hid"),
                             ({"razer:PM1": {"Device": "Razer Naga V2 Pro (Wireless)", "Level": 80, "Charging": True}},
                              False))
            supplies = root / "power_supply"
            for name, scope in (("hidpp_battery_0", "Device"), ("BAT0", "System")):
                d = supplies / name
                d.mkdir(parents=True)
                for f, text in (("scope", scope), ("type", "Battery"), ("capacity", "55"), ("status", "Discharging"),
                                ("manufacturer", "Logitech"), ("model_name", "MX Master 3")):
                    (d / f).write_text(text + "\n")
            self.assertEqual(batteries.kernel_batteries(supplies),
                             {"kernel:hidpp_battery_0": {"Device": "Logitech MX Master 3", "Level": 55, "Charging": False}})
            if os.getuid() != 0:
                (mouse / "charge_level").chmod(0)                                 # not in the group plugdev
                self.assertEqual(batteries.razer_batteries(root / "hid"), ({}, True))

    def test_battery_and_media(self):
        systray = {"battery": {"B": {"Device": "Mouse", "Level": 120}, "A": {"Device": "Headset", "Level": 50}}}
        self.assertEqual(e.battery_rows(systray, {}), [{"name": "Headset", "level": 50, "charging": False},
                                                       {"name": "Mouse", "level": 100, "charging": False}])
        self.assertEqual(e.battery_rows(systray, {"batteryDevice": "B"})[0]["name"], "Mouse")
        others = {"razer:PM1": {"Device": "Razer Naga V2 Pro", "Level": 80, "Charging": True}}
        self.assertEqual(e.battery_rows(systray, {}, others)[-1], {"name": "Razer Naga V2 Pro", "level": 80, "charging": True})
        self.assertEqual(len(e.battery_rows(systray, {"batteryDevice": "razer:PM1"}, others)), 1)
        m = e.media_view({"title": "T", "artists": ["A", "B"], "position": 65, "length": 130})
        self.assertEqual((m["artist"], m["position"], m["progress"]), ("A, B", "1:05", 0.5))
        self.assertFalse(e.media_view("media monitor is not initialized")["available"])

    def test_history(self):
        samples = [(100, 50), (102, None), (104, 60), (120, 70)]
        segments = e.history_path(samples, now=120, minutes=1, maximum=100)
        self.assertEqual(len(segments), 3)                 # split at the gap and after more than 6 s
        self.assertEqual(segments[-1][0], [600.0, round(139 - 0.7 * 138, 2)])

    def test_weather(self):
        data = {"current": {"temperature_2m": 12.4, "weather_code": 0, "is_day": 0, "apparent_temperature": 10},
                "hourly": {"time": ["2026-01-01T09:00", "2026-01-01T11:00"], "temperature_2m": [8, 10]}}
        view = e.weather_view(data, {"city": "Amsterdam", "country": "NL"}, now=datetime(2026, 1, 1, 10))
        self.assertEqual((view["icon"], view["temperature"], view["feelsLike"]), ("🌙", "12", "10°C"))
        self.assertEqual(view["forecast"][0], {"time": "11:00", "temp": "10°"})
        self.assertEqual(view["forecast"][1]["time"], "--:--")
        # Without a given time: the hours count in the city's own time zone
        from datetime import timedelta, timezone
        city_now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=6)
        hours = [(city_now + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00") for h in range(1, 6)]
        far = e.weather_view({"current": {}, "utc_offset_seconds": -6 * 3600,
                              "hourly": {"time": hours, "temperature_2m": [1, 2, 3, 4, 5]}}, {})
        self.assertEqual([f["temp"] for f in far["forecast"]], ["1°", "2°", "3°", "4°"])
        q = e.weather_query({"latitude": 1, "longitude": 2, "unit": "°F"})
        self.assertEqual((q["temperature_unit"], q["forecast_hours"]), ("fahrenheit", 8))

    def test_calendar(self):
        # November 2026 starts on a Sunday
        monday_first = e.calendar_days(2026, 11, False, datetime(2026, 11, 10))
        self.assertEqual(len(monday_first), 42)
        self.assertEqual((monday_first[0]["day"], monday_first[0]["muted"], monday_first[6]["day"]), (26, True, 1))
        self.assertTrue(monday_first[6 + 9]["today"])
        sunday_first = e.calendar_days(2026, 11, True, datetime(2026, 11, 10))
        self.assertEqual((sunday_first[0]["day"], sunday_first[0]["muted"]), (1, False))
        self.assertTrue(e.calendar_days(2027, 1, False, datetime(2026, 11, 10))[0]["muted"])


class FakeSensors:
    """Stands in for quartercore.sensors, so the tests don't depend on this computer."""

    class CpuLoad:
        def read(self):
            return 12.0

    class GpuReader(QObject):
        updated = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.temperature = self.load = None

        def refresh(self):
            self.temperature, self.load = 78.0, 12.0
            self.updated.emit()

    @staticmethod
    def cpu_temperature():
        return 41.0

    @staticmethod
    def memory_usage():
        return {"Total": 34359738368, "Used": 8589934592, "Available": 25769803776, "UsedPercent": 25,
                "SwapTotal": 0, "SwapUsed": 0, "SwapPercent": 0}

    @staticmethod
    def storage_usage():
        return [{"MountPoint": "/", "Device": "/dev/nvme0n1p3", "Filesystem": "btrfs", "Total": 100,
                 "Used": 25, "Available": 75, "UsedPercent": 25.0, "AvailableData": True}]

    @staticmethod
    def storage_temperatures():
        return [{"Key": "hwmon1", "Model": "Test SSD", "Temperature": 30}]


class FakeMedia(QObject):
    updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.playing = None
        self.actions = []

    def refresh(self):
        self.playing = {"playing": True, "title": "Song", "artists": ["Artist"], "position": 65, "length": 200}
        self.updated.emit()

    def control(self, action):
        self.actions.append(action)


class EdgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def start(self, variant=1, olh_layout=True):
        os.environ["FAKE_EDGE"] = str(variant)
        self.server, self.url, self.state = fake_openlinkhub.start()
        if not olh_layout:
            self.state.edge = None
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "xeneon-edge.json"
        self.backend = Backend(self.url)
        self.media = FakeMedia()
        self.edge = e.Edge(self.backend, sensors=FakeSensors, media=self.media)
        self.edge.weather_url = self.url + "/weather"
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))
        self.editor = EdgeEditor(self.backend, self.edge, path=self.path)

    def tearDown(self):
        self.edge.setActive(False)
        self.server.shutdown()
        self.tmp.cleanup()
        os.environ.pop("FAKE_EDGE", None)

    def data(self, widget_id):
        return self.edge.data.get("widget:%d" % widget_id, {})

    def test_first_start_takes_over_openlinkhub(self):
        self.start(1)
        self.assertTrue(wait(lambda: self.path.exists()))
        self.assertEqual(len(self.edge.items), 11)
        settings = {i["widgetId"]: i["settings"] for i in self.edge.items}
        self.assertEqual(settings[10]["headerText"], "Pump")            # from the device profile
        self.assertEqual(settings[6]["max"], 95)                        # upstream default
        self.assertEqual(json.loads(self.path.read_text())["version"], 1)

    def test_first_start_without_openlinkhub_layout(self):
        self.start(1, olh_layout=False)
        self.assertTrue(wait(lambda: "/api/xeneonLayout" in self.state.gets))
        self.assertEqual(sorted(i["widgetId"] for i in self.edge.items), [1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertFalse(self.path.exists())                            # nothing saved until the user does

    def test_saved_layout_wins(self):
        self.tmp_layout = edgelayout.default_layout()
        self.tmp_layout["items"] = self.tmp_layout["items"][:2]
        self.start(1)
        edgelayout.save(self.tmp_layout, self.path)
        editor = EdgeEditor(self.backend, self.edge, path=self.path)
        self.assertEqual([i["widgetId"] for i in self.edge.items], [1, 2])
        self.assertFalse(editor.dirty)

    def test_widgets_and_data(self):
        self.start(1)
        self.assertTrue(wait(lambda: len(self.edge.items) == 11))
        self.edge.setActive(True)
        self.assertTrue(wait(lambda: self.data(6).get("value") == 41 and self.data(9).get("value") == 12
                             and self.data(8).get("value") == 78
                             and self.data(10).get("value") == 26.5 and self.data(11).get("value") == 700))
        self.assertTrue(wait(lambda: self.data(3).get("title") == "Song" and len(self.data(4).get("rows", [])) == 2))
        self.assertTrue(wait(lambda: self.data(2).get("location") == "Amsterdam, Netherlands", 5000))
        self.assertEqual(self.data(2)["condition"], "Overcast")
        # CPU and GPU are read by Quartercore itself now
        self.assertNotIn("/api/cpuTemp/clean", self.state.gets)
        self.assertNotIn("/api/stats/memory", self.state.gets)

    def test_second_set(self):
        self.start(2)
        self.assertTrue(wait(lambda: {i["key"] for i in self.edge.items} >= {"widget:12", "widget:16"}))
        self.assertNotIn("widget:9", {i["key"] for i in self.edge.items})      # hidden in the fork's layout
        self.assertNotIn("custom:crypto-ticker", {i["key"] for i in self.edge.items})
        self.edge.setActive(True)
        self.assertTrue(wait(lambda: self.data(15).get("available") and self.data(16).get("rows")
                             and self.data(13).get("rows") and self.data(14).get("profiles")))
        self.assertEqual(self.data(16)["temperatures"], [{"name": "Test SSD / hwmon1", "value": "30.0 °C"}])
        self.assertEqual([p["name"] for p in self.data(14)["profiles"]], ["default", "work"])
        self.assertTrue(wait(lambda: self.data(12).get("value") == "41.0", 4000))
        self.edge.changeProfile("KB1", "work")
        self.assertTrue(wait(lambda: [p["active"] for p in self.data(14)["profiles"]] == [False, True], 5000))

    def test_media_buttons(self):
        self.start(1)
        self.edge.media("next")
        self.edge.media("../devices")
        self.assertEqual(self.media.actions, ["next"])

    def test_inactive_polls_nothing(self):
        self.start(1)
        self.edge.setActive(True)
        self.edge.setPreview(True)
        self.edge.setActive(False)
        self.assertTrue(self.edge.tick_timer.isActive())                # the editor preview still runs
        self.edge.setPreview(False)
        self.assertFalse(self.edge.tick_timer.isActive())


class EditorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, self.url, self.state = fake_openlinkhub.start()
        self.state.edge = None
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "xeneon-edge.json"
        self.backend = Backend(self.url)
        self.edge = e.Edge(self.backend, sensors=FakeSensors, media=FakeMedia())
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))
        self.editor = EdgeEditor(self.backend, self.edge, path=self.path)
        self.editor.geocoding_url = self.url + "/geocoding"

    def tearDown(self):
        self.server.shutdown()
        self.tmp.cleanup()

    def item(self, key):
        return next(i for i in self.editor.items if i["key"] == key)

    def test_move_resize_and_overlap(self):
        # The clock (0,0 8x4) can't go onto the weather (0,4)
        self.assertFalse(self.editor.place("widget:1", 0, 2, 8, 4))
        self.assertTrue(self.editor.place("widget:1", 0, 0, 6, 3))
        self.assertTrue(self.editor.place("widget:1", 2, 1, 6, 3))
        self.assertFalse(self.editor.place("widget:1", 20, 0, 6, 3))   # outside the grid
        self.assertEqual({k: self.item("widget:1")[k] for k in "xywh"}, {"x": 2, "y": 1, "w": 6, "h": 3})
        self.assertTrue(self.editor.dirty)
        # The kiosk only changes after saving
        clock = next(i for i in self.edge.items if i["widgetId"] == 1)
        self.assertEqual(clock["x"], 0)
        self.editor.save()
        clock = next(i for i in self.edge.items if i["widgetId"] == 1)
        self.assertEqual((clock["x"], clock["w"]), (2, 6))
        self.assertFalse(self.editor.dirty)
        self.assertEqual(json.loads(self.path.read_text())["items"][0]["x"], 2)

    def test_add_hide_remove(self):
        self.assertEqual([w["id"] for w in self.editor.available][:3], [10, 11, 12])
        # The default layout fills the grid: a new widget comes in hidden
        self.editor.add(13)
        self.assertTrue(self.item("widget:13")["hidden"])
        self.assertFalse(self.messages[-1][1])
        # Hiding the GPU load (12,4 4x8) makes room
        self.editor.setHidden("widget:9", True)
        self.editor.add(15)
        self.assertEqual(self.editor.selected, "widget:15")
        memory = self.item("widget:15")
        self.assertEqual((memory["template"], memory["hidden"]), ("xeneon-memory", False))
        others = [i for i in self.editor.items if i["key"] != "widget:15" and not i["hidden"]]
        self.assertFalse(any(edgelayout.overlaps(memory, o) for o in others))
        self.editor.setHidden("widget:15", True)
        self.editor.save()
        self.assertNotIn("widget:15", {i["key"] for i in self.edge.items})
        self.editor.remove("widget:15")
        self.assertIn(15, [w["id"] for w in self.editor.available])

    def test_settings_are_checked(self):
        self.editor.setSetting("widget:6", "max", 5000)                   # CPU temperature scale up to 1000
        self.assertNotEqual(self.editor.problem, "")
        self.editor.save()
        self.assertFalse(self.path.exists())
        self.assertFalse(self.messages[-1][1])
        self.editor.setSetting("widget:6", "max", "110")
        self.editor.setSetting("widget:6", "dataColor", "#ff0000")
        self.assertEqual(self.editor.problem, "")
        self.editor.save()
        saved = json.loads(self.path.read_text())
        cpu = next(i for i in saved["items"] if i["widgetId"] == 6)
        self.assertEqual((cpu["settings"]["max"], cpu["settings"]["dataColor"]), (110, "#ff0000"))

    def test_revert_and_defaults(self):
        self.editor.remove("widget:1")
        self.editor.revert()
        self.assertFalse(self.editor.dirty)
        self.editor.place("widget:1", 0, 0, 2, 2)
        self.editor.resetDefaults()
        self.assertEqual(self.item("widget:1")["w"], 8)

    def test_choices(self):
        self.editor.refreshChoices()
        self.assertTrue(wait(lambda: len(self.editor.choices("device", "")) == 2))
        channels = self.editor.choices("channel", "HUB1")
        self.assertEqual([c["value"] for c in channels], [1, 2, 3])
        self.assertTrue(wait(lambda: len(self.editor.choices("battery", "")) == 3))
        names = [f["name"] for f in self.editor.fields("xeneon-weather")]
        self.assertIn("latitude", names)

    def test_city_search(self):
        found = []
        self.editor.citiesFound.connect(found.append)
        self.editor.searchCity("Utrecht")
        self.assertTrue(wait(lambda: found))
        self.assertEqual(found[0][0]["name"], "Utrecht")
        self.editor.setCity("widget:2", found[0][0])
        self.assertEqual(self.item("widget:2")["settings"]["latitude"], 52.09)

    def test_other_program_changed_the_file(self):
        layout = edgelayout.default_layout()
        layout["items"] = layout["items"][:1]
        edgelayout.save(layout, self.path)
        self.editor._watch()
        self.assertEqual([i["widgetId"] for i in self.edge.items], [1])


class XeneonPageTest(unittest.TestCase):
    """The native XENEON EDGE screen page sends the requests of the web page."""

    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server, self.url, self.state = fake_openlinkhub.start()
        self.backend = Backend(self.url)
        self.backend.selectDevice("EDGE1")
        self.assertTrue(wait(lambda: self.backend.active.get("page") == "xeneon"))

    def tearDown(self):
        self.server.shutdown()

    def test_requests(self):
        b = self.backend
        b.setXeneonValue("brightness", 70)
        b.setXeneonValue("contrast", 40)
        b.setXeneonValue("backlight", 90)
        b.setXeneonTone(1, 200)
        b.setXeneonValue("brightness", 101)                  # not sent
        b.setXeneonValue("volume", 1)                        # not sent
        self.assertTrue(wait(lambda: len(self.state.requests) == 4))
        sent = {path: body for _, path, body in self.state.requests}
        self.assertEqual(sent["/api/brightness/gradual"], {"deviceId": "EDGE1", "brightness": 70})
        self.assertEqual(sent["/api/colortone"], {"deviceId": "EDGE1", "colorTone": 200, "colorToneType": 1})
        self.assertTrue(wait(lambda: (b.active.get("brightness"), b.active.get("backlight"),
                                      b.active.get("tones")) == (70, 90, [150, 200, 140])))
        b.resetXeneon()
        self.assertTrue(wait(lambda: b.active.get("brightness") == 50 and b.active.get("tones")[1] == 126))


class EditorMouseTest(unittest.TestCase):
    def test_drag_and_resize_in_the_preview(self):
        """The QML side: the page scrolls, so the drag must not be taken over."""
        import subprocess
        script = Path(__file__).resolve().parent / "qml_drag_check.py"
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
        line = [l for l in out.stdout.splitlines() if l.startswith("{")]
        self.assertTrue(line, out.stderr[-2000:])
        result = json.loads(line[-1])
        self.assertEqual(result["selected"], "widget:1")
        self.assertEqual(result["resized"], {"x": 0, "y": 0, "w": 6, "h": 3})
        self.assertEqual(result["moved"], {"x": 2, "y": 0, "w": 6, "h": 3})
        self.assertTrue(result["dirty"])


class KioskWindowTest(unittest.TestCase):
    def test_the_kiosk_window_stays(self):
        """The kiosk closed a second after opening the layout editor: QML deleted the window."""
        import subprocess
        script = Path(__file__).resolve().parent / "window_check.py"
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
        line = [l for l in out.stdout.splitlines() if l.startswith("{")]
        self.assertTrue(line, out.stderr[-2000:])
        self.assertEqual(json.loads(line[-1]), {"made": True, "alive": True, "kept": 1})


class LayoutSectionTest(unittest.TestCase):
    def test_the_layout_page_stays_while_the_device_refreshes(self):
        """The layout page jumped back to the open device after its first refresh."""
        import subprocess
        script = Path(__file__).resolve().parent / "section_check.py"
        out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
        line = [l for l in out.stdout.splitlines() if l.startswith("{")]
        self.assertTrue(line, out.stderr[-2000:])
        self.assertEqual(json.loads(line[-1]), {"after": "edge", "opened": ""})


if __name__ == "__main__":
    unittest.main()
