# XENEON EDGE: a native fullscreen kiosk with the 16 OpenLinkHub widgets
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Native QML version of the OpenLinkHub kiosk page (web/xeneon.html and
# static/js/xeneon.js by Nikola Jurkovic) with the free layout of the fork
# wwoutt/OpenLinkHub (/api/xeneonLayout: a 24 x 12 grid on 2560 x 720).
# Widget settings come from the XENEON EDGE device profile; when OpenLinkHub
# doesn't see the XENEON EDGE, the upstream default widgets and settings are
# used. Custom HTML widgets from the widget store are not shown (native only).

import copy
import json
import os
import time
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Property, QObject, QTimer, QUrl, QUrlQuery, Signal, Slot
from PySide6.QtNetwork import QNetworkRequest

COLUMNS, ROWS = 24, 12
EDGE_WIDTH, EDGE_HEIGHT = 2560, 720
LAYOUT_INTERVAL_MS = 10000
TICK_MS = 1000
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


# Upstream database/xeneon/xeneon.json: the 16 widgets with their default settings
WIDGET_DEFAULTS = {
    1: {"name": "Date / Time", "template": "xeneon-clock", "textColor": "#e6e6e6", "fontSize": 80,
        "subTextColor": "#a1a1a1", "subFontSize": 50},
    2: {"name": "Weather", "template": "xeneon-weather", "city": "New York", "country": "United States",
        "latitude": 40.7128, "longitude": -74.006, "refreshInterval": 10, "unit": "°C"},
    3: {"name": "Media Player", "template": "xeneon-media-player", "dataColor": "#38bdf8"},
    4: {"name": "Battery Status", "template": "xeneon-battery-status", "dataColor": "#38bdf8"},
    5: {"name": "Calendar", "template": "xeneon-calendar", "dataColor": "#38bdf8", "weekStart": 0},
    6: {"name": "CPU Temp", "template": "xeneon-cpu-temp", "dataColor": "#FFC107", "max": 95,
        "headerText": "CPU Temperature", "unit": "°C", "textColor": "#a1a1a1"},
    7: {"name": "CPU Load", "template": "xeneon-cpu-load", "dataColor": "#38bdf8", "max": 100,
        "headerText": "CPU Usage", "unit": "%", "textColor": "#a1a1a1"},
    8: {"name": "GPU Temp", "template": "xeneon-gpu-temp", "dataColor": "#FFC107", "max": 85,
        "headerText": "GPU Temperature", "unit": "°C", "textColor": "#a1a1a1"},
    9: {"name": "GPU Load", "template": "xeneon-gpu-load", "dataColor": "#38bdf8", "max": 100,
        "headerText": "GPU Usage", "unit": "%", "textColor": "#a1a1a1"},
    10: {"name": "Device Temperature", "template": "xeneon-device-temp", "dataColor": "#FFC107", "max": 100,
         "headerText": "Device Temperature", "unit": "°C", "textColor": "#a1a1a1"},
    11: {"name": "Device RPM", "template": "xeneon-device-rpm", "dataColor": "#38bdf8", "max": 3000,
         "headerText": "Device RPM", "unit": "RPM", "textColor": "#a1a1a1"},
    12: {"name": "Temperature History", "template": "xeneon-temperature-history", "source": "cpu",
         "historyMinutes": 5, "max": 100, "unit": "°C", "headerText": "Temperature History",
         "dataColor": "#38bdf8", "textColor": "#e6e6e6", "subTextColor": "#a1a1a1", "fontSize": 48,
         "subFontSize": 15},
    13: {"name": "Cooling Overview", "template": "xeneon-cooling-overview", "max": 3000, "unit": "°C",
         "headerText": "Cooling Overview", "dataColor": "#38bdf8", "textColor": "#e6e6e6",
         "subTextColor": "#a1a1a1", "fontSize": 24, "subFontSize": 15},
    14: {"name": "Profile Shortcuts", "template": "xeneon-profile-shortcuts", "headerText": "Profile Shortcuts",
         "dataColor": "#38bdf8", "textColor": "#e6e6e6", "subTextColor": "#a1a1a1", "fontSize": 20,
         "subFontSize": 15},
    15: {"name": "Memory Usage", "template": "xeneon-memory", "headerText": "Memory Usage",
         "dataColor": "#38bdf8", "textColor": "#e6e6e6", "subTextColor": "#a1a1a1", "fontSize": 36,
         "subFontSize": 15, "showSwap": True},
    16: {"name": "Storage Overview", "template": "xeneon-storage", "headerText": "Storage Overview",
         "dataColor": "#38bdf8", "textColor": "#e6e6e6", "subTextColor": "#a1a1a1", "fontSize": 36,
         "subFontSize": 15, "storageSensor": "*", "unit": "°C"},
}
# Upstream default widget areas (xeneonedge.go, first save): area -> widget id
DEFAULT_AREAS = {1: 1, 2: 2, 3: 6, 4: 7, 5: 8, 6: 9, 9: 3, 10: 5, 11: 4}
# Where the upstream page (web/xeneon.html) puts each area, in grid cells:
# areas 1-2 left, the rings of areas 3-8 in pairs in the middle, areas 9-11 right
AREA_CELLS = {
    1: (0, 0, 8, 4), 2: (0, 4, 8, 8),
    3: (8, 0, 4, 4), 4: (12, 0, 4, 4), 5: (8, 4, 4, 4), 6: (12, 4, 4, 4), 7: (8, 8, 4, 4), 8: (12, 8, 4, 4),
    9: (16, 0, 8, 4), 10: (16, 4, 8, 4), 11: (16, 8, 8, 4),
}

# Open-Meteo weather codes (xeneon.js weatherCodeToLabel): label, day icon, night icon
WEATHER_CODES = {
    0: (N_("Clear sky"), "☀️", "🌙"), 1: (N_("Mainly clear"), "🌤️", "🌙"), 2: (N_("Partly cloudy"), "⛅", "⛅"),
    3: (N_("Overcast"), "☁️", "☁️"), 45: (N_("Fog"), "🌫️", "🌫️"), 48: (N_("Depositing rime fog"), "🌫️", "🌫️"),
    51: (N_("Light drizzle"), "🌦️", "🌦️"), 53: (N_("Drizzle"), "🌦️", "🌦️"),
    55: (N_("Dense drizzle"), "🌧️", "🌧️"), 56: (N_("Freezing drizzle"), "🌧️", "🌧️"),
    57: (N_("Dense freezing drizzle"), "🌧️", "🌧️"), 61: (N_("Slight rain"), "🌦️", "🌦️"),
    63: (N_("Rain"), "🌧️", "🌧️"), 65: (N_("Heavy rain"), "🌧️", "🌧️"),
    66: (N_("Freezing rain"), "🌧️", "🌧️"), 67: (N_("Heavy freezing rain"), "🌧️", "🌧️"),
    71: (N_("Slight snow"), "🌨️", "🌨️"), 73: (N_("Snow"), "🌨️", "🌨️"), 75: (N_("Heavy snow"), "❄️", "❄️"),
    77: (N_("Snow grains"), "❄️", "❄️"), 80: (N_("Rain showers"), "🌦️", "🌦️"),
    81: (N_("Rain showers"), "🌧️", "🌧️"), 82: (N_("Violent rain showers"), "⛈️", "⛈️"),
    85: (N_("Snow showers"), "🌨️", "🌨️"), 86: (N_("Heavy snow showers"), "❄️", "❄️"),
    95: (N_("Thunderstorm"), "⛈️", "⛈️"), 96: (N_("Thunderstorm with hail"), "⛈️", "⛈️"),
    99: (N_("Thunderstorm with hail"), "⛈️", "⛈️"),
}

# The data each kind of widget needs, polled every n ticks (seconds) like xeneon.js
SOURCES = {
    "cpuTemp": ("/api/cpuTemp/clean", 1), "cpuLoad": ("/api/cpuLoad", 1),
    "gpuTemp": ("/api/gpuTemp/clean", 1), "gpuLoad": ("/api/gpuLoad", 1),
    "systray": ("/api/systray", 1), "media": ("/api/media/playback", 1),
    "devices": ("/api/stats/devices", 2), "memory": ("/api/stats/memory", 2),
    "storage": ("/api/stats/storage", 5), "storageTemp": ("/api/storageTemp", 5),
}
NEEDS = {
    "xeneon-cpu-temp": ["cpuTemp"], "xeneon-cpu-load": ["cpuLoad"], "xeneon-gpu-temp": ["gpuTemp"],
    "xeneon-gpu-load": ["gpuLoad"], "xeneon-battery-status": ["systray"], "xeneon-media-player": ["media"],
    "xeneon-device-temp": ["devices"], "xeneon-device-rpm": ["devices"], "xeneon-cooling-overview": ["devices"],
    "xeneon-memory": ["memory"], "xeneon-storage": ["storage", "storageTemp"],
}
MEDIA_ACTIONS = {"previous", "stop", "play", "next", "volumeDown", "volumeUp", "mute"}


def find_edge_screen(screens):
    """The XENEON EDGE output: 2560 x 720, also when it is turned to portrait."""
    for screen in screens:
        size = screen.size()
        if sorted((size.width(), size.height())) == [EDGE_HEIGHT, EDGE_WIDTH]:
            return screen
    return None


def widget_settings(widget_id, saved=None):
    """Upstream defaults for a widget, overlaid with the settings saved in the device profile."""
    settings = copy.deepcopy(WIDGET_DEFAULTS.get(widget_id, {}))
    for key, value in (saved or {}).items():
        if value not in (None, "") or key not in settings:
            settings[key] = value
    settings["id"] = widget_id
    return settings


def grow_down(items):
    """Measured widgets grow down to the next widget, like the fork's layout script."""
    shown = [i for i in items if not i.get("hidden")]
    for item in shown:
        if not item.get("measured"):
            continue
        bottom = ROWS
        for other in shown:
            overlaps = other["x"] < item["x"] + item["w"] and item["x"] < other["x"] + other["w"]
            if other is not item and overlaps and other["y"] > item["y"]:
                bottom = min(bottom, other["y"])
        item["h"] = max(item["h"], bottom - item["y"])


def build_items(areas, layout, profile_areas=None):
    """The widgets to show, with their grid cells and settings.

    areas: [{"areaId", "widgetId", "template", "name"}] from /api/xeneonLayout (or the defaults),
    layout: the saved layout or None, profile_areas: {areaId: {"widget": {...settings}}} from
    the device profile. Hidden widgets are left out; custom HTML widgets become placeholders.
    """
    saved = {}
    for item in (layout or {}).get("items") or []:
        key = "custom:" + item["custom"] if item.get("custom") else "widget:%d" % int(item.get("widgetId") or 0)
        saved[key] = item
    items = []
    for area in sorted(areas, key=lambda a: int(a.get("areaId") or 0)):
        widget_id = int(area.get("widgetId") or 0)
        if widget_id not in WIDGET_DEFAULTS:
            continue
        area_id = int(area.get("areaId") or 0)
        stored = ((profile_areas or {}).get(str(area_id)) or (profile_areas or {}).get(area_id) or {})
        settings = widget_settings(widget_id, stored.get("widget") if stored.get("widgetId", widget_id) == widget_id
                                   else None)
        position = saved.get("widget:%d" % widget_id)
        if position:
            cells = {k: int(position[k]) for k in ("x", "y", "w", "h")}
        else:
            x, y, w, h = AREA_CELLS.get(area_id, (0, 0, 4, 4))
            cells = {"x": x, "y": y, "w": w, "h": h}
        items.append(dict(cells, key="widget:%d" % widget_id, widgetId=widget_id,
                          template=settings["template"], name=area.get("name") or settings.get("name", ""),
                          settings=settings, hidden=bool(position and position.get("hidden")),
                          measured=not position))
    for key, position in saved.items():
        if key.startswith("custom:"):
            items.append({"key": key, "widgetId": 0, "template": "custom", "name": position["custom"],
                          "settings": {}, "hidden": bool(position.get("hidden")), "measured": False,
                          **{k: int(position[k]) for k in ("x", "y", "w", "h")}})
    grow_down(items)
    return [i for i in items if not i["hidden"]]


def default_areas():
    return [{"areaId": a, "widgetId": w, "template": WIDGET_DEFAULTS[w]["template"],
             "name": WIDGET_DEFAULTS[w]["name"]} for a, w in DEFAULT_AREAS.items()]


def to_unit(celsius, unit):
    return celsius * 9 / 5 + 32 if unit == "°F" else celsius


def number(value):
    """Numbers as OpenLinkHub sends them: 27, "27.0 °C", "686 RPM"; None when there is none."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().split(" ")[0]
    try:
        return float(text)
    except ValueError:
        return None


def format_bytes(value):
    """Binary units like formatResourceBytes in xeneon.js."""
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    size, index = float(value or 0), 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return ("%.0f" if index == 0 else "%.1f") % size + " " + units[index]


def sensor(devices, serial, channel):
    device = (devices or {}).get(serial or "") or {}
    return (device.get("Devices") or {}).get(str(channel))


def device_value(devices, settings, temperature):
    """Device temperature or RPM widget value, None when the sensor has none."""
    s = sensor(devices, settings.get("deviceId"), settings.get("channelId", 0))
    if not s:
        return None
    if temperature:
        return to_unit(float(s.get("Temperature") or 0), settings.get("unit")) if s.get("TemperatureString") else None
    return number(s.get("Speed")) if s.get("Speed") else None


def cooling_rows(devices, settings):
    """Cooling overview: every channel of one device with a temperature or speed."""
    device = (devices or {}).get(settings.get("deviceId") or "") or {}
    rows = []
    maximum = max(1, int(settings.get("max") or 3000))
    for channel, s in sorted((device.get("Devices") or {}).items(), key=lambda kv: int(kv[0])):
        if not s.get("TemperatureString") and not s.get("Speed"):
            continue
        rpm = number(s.get("Speed")) if s.get("Speed") else None
        temperature = s.get("Temperature")
        rows.append({
            "name": s.get("Device") or "",
            "temperature": "%.1f %s" % (to_unit(float(temperature), settings.get("unit")), settings.get("unit"))
                           if s.get("TemperatureString") and temperature is not None else "",
            "rpm": "%d RPM" % round(rpm) if rpm is not None else "",
            "fill": max(0.0, min(1.0, rpm / maximum)) if rpm is not None else -1,
        })
    return rows


def memory_view(data):
    if not data or (data.get("Total") or 0) <= 0:
        return {"available": False}
    return {
        "available": True, "percent": float(data.get("UsedPercent") or 0),
        "used": format_bytes(data.get("Used")), "total": format_bytes(data.get("Total")),
        "free": format_bytes(data.get("Available")),
        "swapTotal": int(data.get("SwapTotal") or 0), "swapPercent": float(data.get("SwapPercent") or 0),
        "swapUsed": format_bytes(data.get("SwapUsed")), "swapSize": format_bytes(data.get("SwapTotal")),
    }


def storage_rows(data, settings):
    mount = settings.get("mountPoint") or ""
    rows = []
    for fs in data or []:
        if mount and fs.get("MountPoint") != mount:
            continue
        rows.append({
            "mountPoint": fs.get("MountPoint") or "", "device": "%s · %s" % (fs.get("Device"), fs.get("Filesystem")),
            "hasData": bool(fs.get("AvailableData")), "percent": float(fs.get("UsedPercent") or 0),
            "used": format_bytes(fs.get("Used")), "total": format_bytes(fs.get("Total")),
            "free": format_bytes(fs.get("Available")),
        })
    return rows


def storage_temperatures(data, settings):
    wanted = settings.get("storageSensor") or ""
    if not wanted:
        return []
    rows = []
    for s in data or []:
        if wanted != "*" and s.get("Key") != wanted:
            continue
        value = number(s.get("Temperature"))
        if value is None:
            continue
        rows.append({"name": "%s / %s" % (s.get("Model"), s.get("Key")),
                     "value": "%.1f %s" % (to_unit(value, settings.get("unit")), settings.get("unit"))})
    return rows


def battery_rows(systray, settings):
    wanted = settings.get("batteryDevice") or ""
    rows = []
    for serial, d in sorted(((systray or {}).get("battery") or {}).items()):
        if wanted and wanted != serial:
            continue
        rows.append({"name": d.get("Device") or serial, "level": max(0, min(100, int(number(d.get("Level")) or 0)))})
    return rows


def format_time(seconds):
    seconds = max(0, int(number(seconds) or 0))
    return "%d:%02d" % (seconds // 60, seconds % 60)


def media_view(data):
    if not isinstance(data, dict):
        return {"available": False}
    position, length = number(data.get("position")) or 0, number(data.get("length")) or 0
    artists = data.get("artists") or []
    return {"available": True, "title": data.get("title") or "N/A",
            "artist": ", ".join(artists) if isinstance(artists, list) and artists else "N/A",
            "position": format_time(position), "length": format_time(length),
            "progress": max(0.0, min(1.0, position / length)) if length > 0 else 0.0}


def history_path(samples, now, minutes, maximum, width=600, height=140):
    """Line segments of the temperature history (xeneon.js drawHistory), split at gaps of 6 s."""
    window = minutes * 60.0
    segments, current, last = [], [], None
    for t, value in samples:
        if value is None or (last is not None and t - last > 6):
            if current:
                segments.append(current)
            current = []
        if value is not None:
            x = width * (t - now + window) / window
            y = (height - 1) - max(0.0, min(1.0, value / max(1, maximum))) * (height - 2)
            current.append([round(x, 2), round(y, 2)])
        last = t
    if current:
        segments.append(current)
    return segments


def weather_query(settings):
    """Query of the Open-Meteo request, as fetchWeatherForLocation in xeneon.js."""
    unit = "fahrenheit" if settings.get("unit") == "°F" else "celsius"
    return {
        "latitude": settings.get("latitude"), "longitude": settings.get("longitude"),
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,"
                   "is_day,precipitation_probability",
        "hourly": "temperature_2m", "forecast_hours": 8, "timezone": "auto",
        "temperature_unit": unit, "wind_speed_unit": "kmh",
    }


def weather_view(data, settings, now=None):
    current = data.get("current") or {}
    hourly = data.get("hourly") or {}
    code = WEATHER_CODES.get(current.get("weather_code"))
    is_day = current.get("is_day") == 1
    unit = "°F" if settings.get("unit") == "°F" else "°C"
    forecast = []
    if now is None:
        # The hours are in the time zone of the city (timezone=auto); compare them
        # with the time there, not with the time here
        offset = data.get("utc_offset_seconds")
        now = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=offset)
               if offset is not None else datetime.now())
    for t, temperature in zip(hourly.get("time") or [], hourly.get("temperature_2m") or []):
        try:
            moment = datetime.fromisoformat(t)
        except ValueError:
            continue
        if moment > now and len(forecast) < 4:
            forecast.append({"time": moment.strftime("%H:%M"), "temp": "%d°" % round(temperature)})
    while len(forecast) < 4:
        forecast.append({"time": "--:--", "temp": "--°"})
    feels = current.get("apparent_temperature", current.get("temperature_2m")) or 0
    return {
        "available": True,
        "location": "%s, %s" % (settings.get("city") or "", settings.get("country") or ""),
        "condition": code[0] if code else N_("Unknown"), "icon": (code[1] if is_day else code[2]) if code else "🌡️",
        "temperature": "%d" % round(current.get("temperature_2m") or 0), "unit": unit,
        "feelsLike": "%d%s" % (round(feels), unit),
        "humidity": "%d%%" % round(current.get("relative_humidity_2m") or 0),
        "wind": "%d km/h" % round(current.get("wind_speed_10m") or 0),
        "rain": "%d%%" % round(current.get("precipitation_probability") or 0),
        "updated": datetime.now().strftime("%H:%M"),
        "forecast": [] if settings.get("hideForecast") else forecast,
    }


def calendar_days(year, month, week_start_sunday, today):
    """42 day cells (6 weeks) like renderCalendar in xeneon.js."""
    first = datetime(year, month, 1)
    offset = (first.isoweekday() % 7 + (0 if week_start_sunday else 6)) % 7
    next_month = datetime(year + month // 12, month % 12 + 1, 1)
    days_in_month = (next_month - first).days
    previous = datetime(year - (month == 1), (month - 2) % 12 + 1, 1)
    days_in_previous = (first - previous).days
    cells = []
    for i in range(42):
        if i < offset:
            day, cell_month, cell_year, muted = days_in_previous - offset + i + 1, previous.month, previous.year, True
        elif i >= offset + days_in_month:
            day, cell_month, cell_year, muted = i - offset - days_in_month + 1, next_month.month, next_month.year, True
        else:
            day, cell_month, cell_year, muted = i - offset + 1, month, year, False
        weekday = datetime(cell_year, cell_month, day).isoweekday()
        cells.append({"day": day, "muted": muted, "weekend": weekday >= 6,
                      "today": (cell_year, cell_month, day) == (today.year, today.month, today.day)})
    return cells


class Edge(QObject):
    """Layout and live data for the XENEON EDGE window."""
    itemsChanged = Signal()
    dataChanged = Signal()
    statusChanged = Signal()
    clockChanged = Signal()

    def __init__(self, backend, parent=None):
        super().__init__(parent or backend)
        self.backend = backend
        self._items = []
        self._data = {}
        self._raw = {}
        self._status = ""
        self._serial = ""
        self._revision = None
        self._history = {}
        self._weather_at = 0
        self._ticks = 0
        self._active = False
        self._profiles = {}
        self._screen_name = ""
        # Tests and screenshots with the fake point this at the fake OpenLinkHub
        self.weather_url = os.environ.get("QUARTERCORE_WEATHER_URL") or WEATHER_URL
        self.layout_timer = QTimer(self, interval=LAYOUT_INTERVAL_MS, timeout=self.refreshLayout)
        self.tick_timer = QTimer(self, interval=TICK_MS, timeout=self._tick)

    @property
    def api(self):
        return self.backend.api

    # --- properties for QML ---

    @Property("QVariantList", notify=itemsChanged)
    def items(self):
        return self._items

    @Property("QVariantMap", notify=dataChanged)
    def data(self):
        return self._data

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    screenChanged = Signal()

    @Property(str, notify=screenChanged)
    def screenName(self):
        """Name of the output the kiosk uses, empty when no XENEON EDGE screen is found."""
        return self._screen_name

    def set_screen_name(self, name):
        if name != self._screen_name:
            self._screen_name = name
            self.screenChanged.emit()

    @Property(int, constant=True)
    def columns(self):
        return COLUMNS

    @Property(int, constant=True)
    def rows(self):
        return ROWS

    @Property(str, notify=clockChanged)
    def clockTime(self):
        return datetime.now().strftime("%H:%M")

    # --- running ---

    @Slot(bool)
    def setActive(self, active):
        """Polls only while the XENEON EDGE window is shown."""
        if active == self._active:
            return
        self._active = active
        if active:
            self.refreshLayout()
            self.layout_timer.start()
            self.tick_timer.start()
        else:
            self.layout_timer.stop()
            self.tick_timer.stop()

    @Slot()
    def refreshLayout(self):
        def done(ok, data, error):
            payload = (data or {}).get("data") if ok else None
            if not payload:
                # OpenLinkHub doesn't see the XENEON EDGE: upstream defaults
                self._set_status(N_("OpenLinkHub doesn't see the XENEON EDGE: showing the default widgets."))
                self._apply("", default_areas(), None, None, "defaults")
                return
            self._set_status("")
            serial = payload.get("serial") or ""
            revision = payload.get("revision")
            if revision == self._revision and serial == self._serial:
                return
            areas, layout = payload.get("areas") or [], payload.get("layout")
            self.api.get("/api/devices/" + serial, lambda ok2, d2, e2: self._apply(
                serial, areas, layout,
                ((d2 or {}).get("device") or {}).get("DeviceProfile", {}).get("WidgetAreas") if ok2 else None,
                revision))
        self.api.get("/api/xeneonLayout", done)

    def _apply(self, serial, areas, layout, profile_areas, revision):
        if revision == self._revision and serial == self._serial:
            return
        self._serial, self._revision = serial, revision
        self._items = build_items(areas, layout, profile_areas)
        self.itemsChanged.emit()
        self._ticks = 0
        self._weather_at = 0
        self._tick()

    def _set_status(self, text):
        text = self.tr(text) if text else ""
        if text != self._status:
            self._status = text
            self.statusChanged.emit()

    def _templates(self):
        return {i["template"] for i in self._items}

    def _tick(self):
        self.clockChanged.emit()
        templates = self._templates()
        needed = {source for t in templates for source in NEEDS.get(t, [])}
        for item in self._items:
            if item["template"] == "xeneon-temperature-history":
                s = item["settings"].get("source")
                needed.add("cpuTemp" if s == "cpu" else "gpuTemp" if s == "gpu" else "devices")
        for name in needed:
            path, every = SOURCES[name]
            if self._ticks % every == 0:
                self.api.get(path, self._store(name))
        if self._ticks % 2 == 0:
            self._sample_history()
        if self._ticks % 3 == 0:
            self._refresh_profiles()
        self._refresh_weather()
        self._ticks += 1

    def _store(self, name):
        def done(ok, data, error):
            # Reads answer status 1 here; status 0 (media monitor off) means no data
            value = data.get("data") if ok and data.get("status") == 1 else None
            self._raw[name] = value
            self._rebuild()
        return done

    def _rebuild(self):
        """Turns the raw API data into what each widget shows."""
        raw, out = self._raw, {}
        for item in self._items:
            s, t, key = item["settings"], item["template"], item["key"]
            if t in ("xeneon-cpu-temp", "xeneon-gpu-temp"):
                v = number(raw.get("cpuTemp" if t == "xeneon-cpu-temp" else "gpuTemp"))
                out[key] = {"value": to_unit(v, s.get("unit")) if v is not None else None}
            elif t in ("xeneon-cpu-load", "xeneon-gpu-load"):
                out[key] = {"value": number(raw.get("cpuLoad" if t == "xeneon-cpu-load" else "gpuLoad"))}
            elif t in ("xeneon-device-temp", "xeneon-device-rpm"):
                out[key] = {"value": device_value(raw.get("devices"), s, t == "xeneon-device-temp")}
            elif t == "xeneon-cooling-overview":
                out[key] = {"rows": cooling_rows(raw.get("devices"), s)}
            elif t == "xeneon-memory":
                out[key] = memory_view(raw.get("memory"))
            elif t == "xeneon-storage":
                out[key] = {"rows": storage_rows(raw.get("storage"), s),
                            "temperatures": storage_temperatures(raw.get("storageTemp"), s)}
            elif t == "xeneon-battery-status":
                out[key] = {"rows": battery_rows(raw.get("systray"), s)}
            elif t == "xeneon-media-player":
                out[key] = media_view(raw.get("media"))
            elif t == "xeneon-temperature-history":
                out[key] = self._history_view(item)
            elif t == "xeneon-weather":
                out[key] = self._raw.get("weather:" + key) or {"available": False}
            elif t == "xeneon-profile-shortcuts":
                out[key] = self._profiles.get(s.get("deviceId") or "", {"profiles": [], "available": False})
        self._data = out
        self.dataChanged.emit()

    # --- temperature history ---

    def _sample_history(self):
        now = time.time()
        for item in self._items:
            if item["template"] != "xeneon-temperature-history":
                continue
            s = item["settings"]
            source = s.get("source")
            if source == "device":
                value = device_value(self._raw.get("devices"), s, True)
            else:
                value = number(self._raw.get("cpuTemp" if source == "cpu" else "gpuTemp"))
                value = to_unit(value, s.get("unit")) if value is not None else None
            samples = self._history.setdefault(item["key"], [])
            samples.append((now, value))
            window = max(1, int(s.get("historyMinutes") or 5)) * 60
            while samples and samples[0][0] < now - window:
                samples.pop(0)
        self._rebuild()

    def _history_view(self, item):
        s = item["settings"]
        samples = self._history.get(item["key"], [])
        values = [v for _, v in samples if v is not None]
        unit = s.get("unit") or "°C"
        last = samples[-1][1] if samples else None
        return {
            "value": "%.1f" % last if last is not None else "--", "unit": unit,
            "min": "%.1f %s" % (min(values), unit) if values else "--",
            "max": "%.1f %s" % (max(values), unit) if values else "--",
            "segments": history_path(samples, time.time(), max(1, int(s.get("historyMinutes") or 5)),
                                     int(s.get("max") or 100)),
        }

    # --- profile shortcuts ---

    def _refresh_profiles(self):
        for item in self._items:
            serial = item["settings"].get("deviceId") if item["template"] == "xeneon-profile-shortcuts" else ""
            if serial:
                self.api.get("/api/devices/" + serial, self._store_profiles(serial))

    def _store_profiles(self, serial):
        def done(ok, data, error):
            profiles = ((data or {}).get("device") or {}).get("userProfiles") or {} if ok else {}
            names = sorted(n for n in profiles if n.isascii() and n.isalnum())
            self._profiles[serial] = {"available": ok, "profiles": [
                {"name": n, "active": bool(profiles[n].get("Active"))} for n in names]}
            self._rebuild()
        return done

    @Slot(str, str)
    def changeProfile(self, serial, name):
        def done(ok, data, error):
            self.backend.notify.emit(str((data or {}).get("message") or error), ok)
            self._refresh_profiles()
        self.api.post("/api/userProfile/change", {"deviceId": serial, "userProfileName": name}, done)

    # --- media ---

    @Slot(str)
    def media(self, action):
        if action in MEDIA_ACTIONS:
            self.api.get("/api/media/" + action, lambda ok, data, error: None)

    # --- weather ---

    def _refresh_weather(self):
        for item in self._items:
            if item["template"] != "xeneon-weather":
                continue
            s = item["settings"]
            interval = max(5, int(s.get("refreshInterval") or 10)) * 60
            if self._weather_at and time.time() - self._weather_at < interval:
                continue
            self._weather_at = time.time()
            if s.get("latitude") is None or s.get("longitude") is None:
                continue
            url = QUrl(self.weather_url)
            query = QUrlQuery()
            for k, v in weather_query(s).items():
                query.addQueryItem(k, str(v))
            url.setQuery(query)
            reply = self.api.manager.get(QNetworkRequest(url))
            reply.finished.connect(lambda r=reply, key=item["key"], st=s: self._weather_done(r, key, st))

    def _weather_done(self, reply, key, settings):
        raw = bytes(reply.readAll())
        reply.deleteLater()
        try:
            view = weather_view(json.loads(raw), settings)
            view["condition"] = self.tr(view["condition"])
        except (ValueError, TypeError, AttributeError):
            view = {"available": False}
        self._raw["weather:" + key] = view
        self._rebuild()

    # --- calendar ---

    @Slot(int, int, bool, result="QVariantList")
    def calendar(self, year, month, sunday_first):
        return calendar_days(year, month, sunday_first, datetime.now())
