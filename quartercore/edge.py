# XENEON EDGE: a native fullscreen kiosk with the 16 OpenLinkHub widgets
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Modified by wwoutt, 2026-11-11: own widgets 17-23 (network, power, GPU details, Home Assistant,
# processes, system info), not in OpenLinkHub.
# Modified by wwoutt, 2026-11-11: Home Assistant tiles with a status entity and own colour rules
#
# Native QML version of the OpenLinkHub kiosk page (web/xeneon.html and
# static/js/xeneon.js by Nikola Jurkovic) with the free layout of the fork
# wwoutt/OpenLinkHub (a 24 x 12 grid on 2560 x 720). The layout and widget
# settings are Quartercore's own (edgelayout.py, edgeeditor.py); the fork's
# /api/xeneonLayout is only read to take them over once. Custom HTML widgets
# from the widget store are not shown (native only).

import copy
import json
import os
import time
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Property, QObject, QTimer, QUrl, QUrlQuery, Signal, Slot
from PySide6.QtNetwork import QNetworkRequest

COLUMNS, ROWS = 24, 12
EDGE_WIDTH, EDGE_HEIGHT = 2560, 720
TICK_MS = 1000
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


# Upstream database/xeneon/xeneon.json: the 16 widgets with their default settings
WIDGET_DEFAULTS = {
    1: {"name": "Date / Time", "template": "xeneon-clock", "textColor": "#e6e6e6", "fontSize": 80,
        "subTextColor": "#a1a1a1", "subFontSize": 50, "left": 0, "top": 0, "subLeft": 0, "subTop": 0},
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
    # Quartercore's own widgets (not in OpenLinkHub)
    17: {"name": "Network", "template": "xeneon-network", "headerText": "Network", "dataColor": "#38bdf8",
         "uploadColor": "#f472b6", "interface": "", "rateUnit": "bytes", "historySeconds": 60},
    18: {"name": "Power", "template": "xeneon-power", "headerText": "Power", "dataColor": "#FFC107",
         "deviceId": "", "pricePerKwh": 0.30, "currency": "€", "historyMinutes": 5},
    19: {"name": "GPU Details", "template": "xeneon-gpu-details", "headerText": "GPU", "dataColor": "#38bdf8",
         "unit": "°C"},
    20: {"name": "Home Assistant", "template": "xeneon-homeassistant", "headerText": "Home Assistant",
         "dataColor": "#38bdf8", "entities": "", "refreshSeconds": 5},
    21: {"name": "Top Processes", "template": "xeneon-processes", "headerText": "Processes",
         "dataColor": "#38bdf8", "sortBy": "cpu", "count": 5},
    22: {"name": "System Info", "template": "xeneon-system", "headerText": "System", "dataColor": "#38bdf8"},
    23: {"name": "Home Assistant Buttons", "template": "xeneon-ha-buttons", "headerText": "",
         "dataColor": "#38bdf8", "entities": "", "refreshSeconds": 5},
}
HOME_ASSISTANT_TEMPLATES = {"xeneon-homeassistant", "xeneon-ha-buttons"}
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


# OpenLinkHub checks these four for every widget, also where its defaults leave them out
BASE_SETTINGS = {"textColor": "#e6e6e6", "subTextColor": "#a1a1a1", "fontSize": 36, "subFontSize": 15,
                 "dataColor": "#38bdf8"}


def widget_settings(widget_id, saved=None):
    """Upstream defaults for a widget, overlaid with the settings saved in the device profile."""
    settings = dict(copy.deepcopy(BASE_SETTINGS), **copy.deepcopy(WIDGET_DEFAULTS.get(widget_id, {})))
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


def network_view(history, settings):
    from .sensors import format_rate
    if not history:
        return {"available": False}
    bits = settings.get("rateUnit") == "bits"
    down, up = history[-1]
    top = max(max(d, u) for d, u in history) or 1
    return {"available": True, "down": format_rate(down, bits), "up": format_rate(up, bits),
            "downHistory": [d / top for d, _ in history], "upHistory": [u / top for _, u in history],
            "peak": format_rate(top, bits)}


def power_view(psu, history, settings):
    """Power from the wall (input) and to the computer (output), with the cost at the set price."""
    if not psu:
        return {"available": False}
    watts, output = float(psu.get("power") or 0), float(psu.get("outputPower") or 0)
    try:
        price = float(settings.get("pricePerKwh") or 0)
    except (TypeError, ValueError):
        price = 0.0
    currency = settings.get("currency") or ""
    top = max(history or [watts]) or 1
    return {"available": True, "watts": "%.0f W" % watts, "output": "%.0f W" % output,
            "efficiency": "%.0f %%" % (output / watts * 100) if watts > 0 and output > 0 else "",
            "costHour": "%s %.2f" % (currency, watts / 1000 * price) if price else "",
            "costDay": "%s %.2f" % (currency, watts / 1000 * price * 24) if price else "",
            "history": [v / top for v in history], "peak": "%.0f W" % top, "product": psu.get("product") or ""}


def gpu_details_view(temperature, load, details, settings):
    if temperature is None and not details:
        return {"available": False}
    d = details or {}

    def amount(value, unit, digits=0):
        return ("%." + str(digits) + "f %s") % (value, unit) if value is not None else "–"
    used, total = d.get("memoryUsed"), d.get("memoryTotal")
    temp = to_unit(temperature, settings.get("unit")) if temperature is not None else None
    return {"available": True, "name": d.get("name") or "GPU",
            "temperature": ("%.0f %s" % (temp, settings.get("unit") or "°C")) if temp is not None else "–",
            "load": load or 0, "loadText": amount(load, "%"),
            "memory": ("%.1f / %.1f GB" % (used / 1024, total / 1024)) if used is not None and total else "–",
            "memoryFraction": (used / total) if used is not None and total else 0,
            "power": amount(d.get("power"), "W") + (" / " + amount(d.get("powerLimit"), "W")
                                                     if d.get("powerLimit") else ""),
            "clock": amount(d.get("clock"), "MHz"), "memoryClock": amount(d.get("memoryClock"), "MHz"),
            "fan": amount(d.get("fan"), "%")}


def processes_view(rows):
    if rows is None:
        return {"available": False, "rows": []}
    return {"available": True, "rows": [
        {"name": r["name"], "cpu": "%.1f %%" % r["cpu"] if r.get("cpu") is not None else "…",
         "memory": format_bytes(r["memory"])} for r in rows]}


def uptime_text(seconds):
    if seconds is None:
        return "–"
    minutes = int(seconds // 60)
    days, hours, minutes = minutes // 1440, minutes // 60 % 24, minutes % 60
    return ("%d d %d h" % (days, hours)) if days else ("%d h %d min" % (hours, minutes))


def system_view(info):
    if not info:
        return {"available": False}
    load = info.get("load") or []
    return {"available": True, "host": info.get("host") or "", "os": info.get("os") or "",
            "kernel": info.get("kernel") or "", "cpu": info.get("cpu") or "",
            "uptime": uptime_text(info.get("uptime")), "load": "  ".join("%.2f" % v for v in load) or "–",
            "processes": str(info.get("processes") or "–")}


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
    """Live data for the XENEON EDGE widgets (kiosk window and editor preview).

    The layout comes from EdgeEditor (quartercore/edgeeditor.py). CPU, GPU,
    memory, storage and the media player are read by Quartercore itself
    (sensors.py, media.py); device sensors, batteries and device profiles
    still come from OpenLinkHub until those devices move (roadmap part 2).
    """
    itemsChanged = Signal()
    dataChanged = Signal()
    statusChanged = Signal()
    clockChanged = Signal()
    screenChanged = Signal()

    def __init__(self, backend, parent=None, sensors=None, media=None, home_assistant=None):
        super().__init__(parent or backend)
        from . import media as media_module, sensors as sensors_module
        self.backend = backend
        self.home_assistant = home_assistant
        if home_assistant is not None:
            home_assistant.statesChanged.connect(self._rebuild)
        self._network = getattr(sensors or sensors_module, "NetworkRate", sensors_module.NetworkRate)()
        self._processes = getattr(sensors or sensors_module, "ProcessTop", sensors_module.ProcessTop)()
        self._system_info = getattr(sensors or sensors_module, "system_info", sensors_module.system_info)
        self._net_history = []
        self._power_history = []
        self._ha_at = 0
        self._items = []
        self._preview = []
        self._data = {}
        self._raw = {}
        self._status = ""
        self._history = {}
        self._weather_at = 0
        self._weather_key = None
        self._ticks = 0
        self._kiosk = self._previewing = False
        self._profiles = {}
        self._screen_name = ""
        self.sensors = sensors or sensors_module
        self.cpu_load = self.sensors.CpuLoad()
        self.gpu = self.sensors.GpuReader(self)
        self.gpu.updated.connect(self._gpu_done)
        self.media_player = media or media_module.Media(self)
        self.media_player.updated.connect(self._media_done)
        # Tests and screenshots with the fake point this at the fake OpenLinkHub
        self.weather_url = os.environ.get("QUARTERCORE_WEATHER_URL") or WEATHER_URL
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

    def _update_running(self):
        if self._kiosk or self._previewing:
            if not self.tick_timer.isActive():
                self.tick_timer.start()
                self._tick()
        else:
            self.tick_timer.stop()

    @Slot(bool)
    def setActive(self, active):
        """Polls only while the XENEON EDGE window (or the editor preview) is shown."""
        self._kiosk = bool(active)
        self._update_running()

    @Slot(bool)
    def setPreview(self, active):
        self._previewing = bool(active)
        self._update_running()

    def set_items(self, items):
        """The widgets the kiosk shows (from the saved layout)."""
        self._items = items
        self.itemsChanged.emit()
        self._weather_at = 0
        self._rebuild()
        if self.tick_timer.isActive():
            self._tick()

    def set_preview_items(self, items):
        """Widgets of the editor that aren't saved yet, so the preview has data too."""
        self._preview = items
        self._rebuild()

    def _all(self):
        seen, items = set(), []
        for item in self._items + self._preview:
            if item["key"] not in seen:
                seen.add(item["key"])
                items.append(item)
        return items

    def _templates(self):
        return {i["template"] for i in self._all()}

    def _tick(self):
        self.clockChanged.emit()
        needed = {source for t in self._templates() for source in NEEDS.get(t, [])}
        for item in self._all():
            if item["template"] == "xeneon-temperature-history":
                s = item["settings"].get("source")
                needed.add("cpuTemp" if s == "cpu" else "gpuTemp" if s == "gpu" else "devices")
        for name in needed:
            path, every = SOURCES[name]
            if self._ticks % every:
                continue
            if name in ("cpuTemp",):
                self._raw["cpuTemp"] = self.sensors.cpu_temperature()
            elif name == "cpuLoad":
                self._raw["cpuLoad"] = self.cpu_load.read()
            elif name in ("gpuTemp", "gpuLoad"):
                self.gpu.refresh()
            elif name == "memory":
                self._raw["memory"] = self.sensors.memory_usage()
            elif name == "storage":
                self._raw["storage"] = self.sensors.storage_usage()
            elif name == "storageTemp":
                self._raw["storageTemp"] = self.sensors.storage_temperatures()
            elif name == "media":
                self.media_player.refresh()
            else:
                # Device sensors and batteries: still from OpenLinkHub
                self.api.get(path, self._store(name))
        self._tick_own(self._templates())
        if self._ticks % 2 == 0:
            self._sample_history()
        if self._ticks % 3 == 0:
            self._refresh_profiles()
        self._refresh_weather()
        self._rebuild()
        self._ticks += 1

    def _gpu_done(self):
        self._raw["gpuTemp"], self._raw["gpuLoad"] = self.gpu.temperature, self.gpu.load
        self._rebuild()

    def _media_done(self):
        self._raw["media"] = self.media_player.playing
        self._rebuild()

    def _store(self, name):
        def done(ok, data, error):
            value = data.get("data") if ok and data.get("status") == 1 else None
            self._raw[name] = value
            self._rebuild()
        return done

    def _rebuild(self):
        """Turns the raw API data into what each widget shows."""
        raw, out = self._raw, {}
        for item in self._all():
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
            elif t == "xeneon-network":
                out[key] = network_view(self._net_history, s)
            elif t == "xeneon-power":
                out[key] = power_view(raw.get("power"), self._power_history, s)
            elif t == "xeneon-gpu-details":
                out[key] = gpu_details_view(raw.get("gpuTemp"), raw.get("gpuLoad"), getattr(self.gpu, "details", {}), s)
            elif t == "xeneon-processes":
                out[key] = processes_view(raw.get("processes:" + key))
            elif t == "xeneon-system":
                out[key] = system_view(raw.get("system"))
            elif t in HOME_ASSISTANT_TEMPLATES:
                out[key] = self._home_assistant_view(s)
        self._data = out
        self.dataChanged.emit()

    # --- own widgets: network, power, GPU details, processes, system, Home Assistant ---

    def _tick_own(self, templates):
        items = self._all()
        if "xeneon-network" in templates:
            s = next(i["settings"] for i in items if i["template"] == "xeneon-network")
            rate = self._network.read(s.get("interface") or "")
            if rate is not None:
                keep = max(10, int(s.get("historySeconds") or 60))
                self._net_history = (self._net_history + [rate])[-keep:]
        if "xeneon-gpu-details" in templates and "gpu" not in {n for t in templates for n in NEEDS.get(t, [])}:
            self.gpu.refresh()
        if "xeneon-power" in templates and self._ticks % 2 == 0:
            s = next(i["settings"] for i in items if i["template"] == "xeneon-power")
            serial = s.get("deviceId") or next((d["serial"] for d in self.backend.devices if d.get("page") == "psu"), "")
            if serial:
                self.api.get("/api/devices/" + serial, self._power_done(s))
        if self._ticks % 2 == 0:
            for item in items:
                if item["template"] == "xeneon-processes":
                    s = item["settings"]
                    self._raw["processes:" + item["key"]] = self._processes.read(s.get("sortBy") or "cpu",
                                                                                 int(s.get("count") or 5))
        if "xeneon-system" in templates and self._ticks % 5 == 0:
            self._raw["system"] = self._system_info()
        if templates & HOME_ASSISTANT_TEMPLATES and self.home_assistant is not None:
            every = min(max(2, int(i["settings"].get("refreshSeconds") or 5)) for i in items
                        if i["template"] in HOME_ASSISTANT_TEMPLATES)
            if time.time() - self._ha_at >= every:
                self._ha_at = time.time()
                self.home_assistant.refresh()

    def _power_done(self, settings):
        def done(ok, data, error):
            from .backend import psu_view
            device = (data or {}).get("device") if ok else None
            view = psu_view(device) if device else None
            self._raw["power"] = view
            if view is not None:
                keep = max(1, int(settings.get("historyMinutes") or 5)) * 30      # one sample every 2 s
                self._power_history = (self._power_history + [view["power"]])[-keep:]
            self._rebuild()
        return done

    def _home_assistant_view(self, settings):
        from .homeassistant import tile, tile_specs
        ha = self.home_assistant
        if ha is None or not ha.configured:
            return {"available": False, "message": self.tr("Set the Home Assistant address and token in the settings"),
                    "tiles": []}
        entities = tile_specs(settings.get("entities"))
        if not entities:
            return {"available": False, "message": self.tr("Choose entities in the layout editor"), "tiles": []}
        return {"available": True, "message": ha.status,
                "tiles": [tile(t["entity"], ha.state(t["entity"]), t["status"],
                               ha.state(t["status"]) if t["status"] else None, t["rules"]) for t in entities]}

    @Slot(str)
    def activateEntity(self, entity_id):
        """A tap on a Home Assistant tile in the kiosk."""
        if self.home_assistant is not None:
            self.home_assistant.activate(entity_id)

    # --- temperature history ---

    def _sample_history(self):
        now = time.time()
        for item in self._all():
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
        for item in self._all():
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
            self.media_player.control(action)

    # --- weather ---

    def _refresh_weather(self):
        for item in self._all():
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
