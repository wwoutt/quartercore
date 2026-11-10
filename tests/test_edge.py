# Tests for the native XENEON EDGE kiosk against the fake OpenLinkHub
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402

import fake_openlinkhub  # noqa: E402
from quartercore import edge as e  # noqa: E402
from quartercore.backend import Backend  # noqa: E402
from test_backend import wait  # noqa: E402


class LayoutTest(unittest.TestCase):
    def test_all_widgets_have_defaults(self):
        self.assertEqual(sorted(e.WIDGET_DEFAULTS), list(range(1, 17)))
        self.assertEqual(len({w["template"] for w in e.WIDGET_DEFAULTS.values()}), 16)

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

    def test_battery_and_media(self):
        systray = {"battery": {"B": {"Device": "Mouse", "Level": 120}, "A": {"Device": "Headset", "Level": 50}}}
        self.assertEqual(e.battery_rows(systray, {}), [{"name": "Headset", "level": 50}, {"name": "Mouse", "level": 100}])
        self.assertEqual(e.battery_rows(systray, {"batteryDevice": "B"})[0]["name"], "Mouse")
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


class EdgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def start(self, variant=1):
        os.environ["FAKE_EDGE"] = str(variant)
        self.server, self.url, self.state = fake_openlinkhub.start()
        self.backend = Backend(self.url)
        self.edge = e.Edge(self.backend)
        self.edge.weather_url = self.url + "/weather"
        self.messages = []
        self.backend.notify.connect(lambda text, ok: self.messages.append((text, ok)))

    def tearDown(self):
        self.edge.setActive(False)
        self.server.shutdown()
        os.environ.pop("FAKE_EDGE", None)

    def data(self, widget_id):
        return self.edge.data.get("widget:%d" % widget_id, {})

    def test_widgets_and_data(self):
        self.start(1)
        self.edge.setActive(True)
        self.assertTrue(wait(lambda: len(self.edge.items) == 11))
        self.assertEqual(self.edge.status, "")
        settings = {i["widgetId"]: i["settings"] for i in self.edge.items}
        self.assertEqual(settings[10]["headerText"], "Pump")            # from the device profile
        self.assertEqual(settings[6]["max"], 95)                        # upstream default
        self.assertTrue(wait(lambda: self.data(6).get("value") == 41 and self.data(9).get("value") == 12
                             and self.data(10).get("value") == 26.5 and self.data(11).get("value") == 700))
        self.assertTrue(wait(lambda: self.data(3).get("title") == "Song" and len(self.data(4).get("rows", [])) == 2))
        self.assertTrue(wait(lambda: self.data(2).get("location") == "Amsterdam, Netherlands", 5000))
        self.assertEqual(self.data(2)["condition"], "Overcast")
        # Only the data these widgets need is asked for
        self.assertNotIn("/api/stats/memory", self.state.gets)
        self.assertIn("/api/cpuTemp/clean", self.state.gets)

    def test_second_set(self):
        self.start(2)
        self.edge.setActive(True)
        self.assertTrue(wait(lambda: {i["key"] for i in self.edge.items} >= {"widget:12", "custom:crypto-ticker"}))
        self.assertNotIn("widget:9", {i["key"] for i in self.edge.items})
        self.assertTrue(wait(lambda: self.data(15).get("available") and self.data(16).get("rows")
                             and self.data(13).get("rows") and self.data(14).get("profiles")))
        self.assertEqual([p["name"] for p in self.data(14)["profiles"]], ["default", "work"])
        self.assertTrue(wait(lambda: self.data(12).get("value") == "41.0", 4000))
        self.edge.changeProfile("KB1", "work")
        self.assertTrue(wait(lambda: [p["active"] for p in self.data(14)["profiles"]] == [False, True], 5000))

    def test_without_xeneon(self):
        self.start(1)
        self.state.edge = None
        self.edge.setActive(True)
        self.assertTrue(wait(lambda: self.edge.status != ""))
        self.assertEqual(sorted(i["widgetId"] for i in self.edge.items), [1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_media_buttons(self):
        self.start(1)
        self.edge.media("next")
        self.edge.media("../devices")                                   # only known actions
        self.assertTrue(wait(lambda: "/api/media/next" in self.state.gets))
        self.assertFalse(any("devices" in p for p in self.state.gets))

    def test_inactive_polls_nothing(self):
        self.start(1)
        self.edge.setActive(True)
        self.assertTrue(wait(lambda: self.edge.items))
        self.edge.setActive(False)
        self.assertFalse(self.edge.tick_timer.isActive() or self.edge.layout_timer.isActive())


if __name__ == "__main__":
    unittest.main()
