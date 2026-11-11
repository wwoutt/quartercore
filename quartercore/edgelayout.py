# XENEON EDGE layout and widget settings, stored by Quartercore itself
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
# Modified by wwoutt, 2026-11-11: settings of the own widgets 17-23
#
# The layout lives in ~/.config/Quartercore/xeneon-edge.json, so the native
# kiosk doesn't need OpenLinkHub (roadmap step A). The grid is the one of the
# fork wwoutt/OpenLinkHub (24 x 12 cells on 2560 x 720); the widget settings
# and their limits are those of OpenLinkHub by Nikola Jurkovic
# (ProcessSaveWidget in src/devices/xeneonedge/xeneonedge.go). Unlike
# OpenLinkHub, which has 11 widget areas, every widget can be shown at once.
#
# File: {"version": 1, "columns": 24, "rows": 12,
#        "items": [{"widgetId", "x", "y", "w", "h", "hidden", "settings": {...}}]}

import copy
import json
import os
import re
from pathlib import Path

from .edge import (AREA_CELLS, COLUMNS, DEFAULT_AREAS, ROWS, WIDGET_DEFAULTS, build_items, grow_down,
                   widget_settings)

VERSION = 1
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def N_(text):
    """Marks a text for translation; it is translated where it is shown."""
    return text


def layout_path():
    home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return home / "Quartercore" / "xeneon-edge.json"


def default_layout():
    """The upstream default widgets in the places of the upstream page."""
    items = []
    for area, widget_id in DEFAULT_AREAS.items():
        x, y, w, h = AREA_CELLS[area]
        items.append({"widgetId": widget_id, "x": x, "y": y, "w": w, "h": h, "hidden": False,
                      "measured": True, "settings": widget_settings(widget_id)})
    grow_down(items)
    for item in items:
        item.pop("measured")
    return {"version": VERSION, "columns": COLUMNS, "rows": ROWS, "items": items}


def from_openlinkhub(areas, layout, profile_areas):
    """Imports the layout of the fork's editor and the widget settings of OpenLinkHub."""
    items = []
    for item in build_items(areas, layout, profile_areas):
        if item["template"] == "custom":
            continue     # HTML widgets aren't shown natively
        items.append({"widgetId": item["widgetId"], "x": item["x"], "y": item["y"], "w": item["w"],
                      "h": item["h"], "hidden": False, "settings": item["settings"]})
    # Hidden widgets of the saved layout keep their place (but not their settings)
    placed = {i["widgetId"] for i in items}
    for item in (layout or {}).get("items") or []:
        widget_id = int(item.get("widgetId") or 0)
        if item.get("hidden") and widget_id in WIDGET_DEFAULTS and widget_id not in placed:
            items.append({"widgetId": widget_id, "x": int(item["x"]), "y": int(item["y"]), "w": int(item["w"]),
                          "h": int(item["h"]), "hidden": True, "settings": widget_settings(widget_id)})
    return {"version": VERSION, "columns": COLUMNS, "rows": ROWS, "items": items}


def overlaps(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def fits(item, items):
    """Inside the grid and not on top of another shown widget."""
    if item["x"] < 0 or item["y"] < 0 or item["w"] < 1 or item["h"] < 1:
        return False
    if item["x"] + item["w"] > COLUMNS or item["y"] + item["h"] > ROWS:
        return False
    if item.get("hidden"):
        return True
    return not any(o is not item and o["widgetId"] != item["widgetId"] and not o.get("hidden") and overlaps(item, o)
                   for o in items)


def free_spot(items, w=4, h=4):
    """The first free place for a new widget, top left first; None when the grid is full."""
    for size in ((w, h), (4, 4), (4, 2), (2, 2), (1, 1)):
        for y in range(ROWS - size[1] + 1):
            for x in range(COLUMNS - size[0] + 1):
                candidate = {"widgetId": -1, "x": x, "y": y, "w": size[0], "h": size[1]}
                if fits(candidate, items):
                    return candidate
    return None


def load(path=None):
    """The saved layout, or None when there is none (or it can't be read)."""
    path = Path(path or layout_path())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return None
    items = []
    for item in data["items"]:
        try:
            widget_id = int(item["widgetId"])
            entry = {"widgetId": widget_id, "x": int(item["x"]), "y": int(item["y"]), "w": int(item["w"]),
                     "h": int(item["h"]), "hidden": bool(item.get("hidden"))}
        except (KeyError, TypeError, ValueError):
            continue
        if widget_id in WIDGET_DEFAULTS and widget_id not in {i["widgetId"] for i in items} and fits(entry, []):
            entry["settings"] = widget_settings(widget_id, item.get("settings"))
            items.append(entry)
    return {"version": VERSION, "columns": COLUMNS, "rows": ROWS, "items": items}


def save(layout, path=None):
    path = Path(path or layout_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def shown_items(layout):
    """The items the kiosk shows, in the form edge.build_items gives them."""
    items = []
    for item in layout.get("items") or []:
        if item.get("hidden"):
            continue
        settings = item["settings"]
        items.append({"key": "widget:%d" % item["widgetId"], "widgetId": item["widgetId"],
                      "template": settings["template"], "name": settings.get("name", ""),
                      "settings": settings, "hidden": False,
                      "x": item["x"], "y": item["y"], "w": item["w"], "h": item["h"]})
    return items


# --- widget settings ---
#
# Each field: name, label, kind (color, int, float, text, bool, choice, device,
# channel), and for numbers min/max, for choices the values. "device" and
# "channel" are filled with the devices OpenLinkHub knows.

TEMPERATURE_UNITS = [{"value": "°C", "name": "°C"}, {"value": "°F", "name": "°F"}]
COMMON = [
    {"name": "textColor", "label": N_("Text colour"), "kind": "color"},
    {"name": "subTextColor", "label": N_("Second text colour"), "kind": "color"},
    {"name": "fontSize", "label": N_("Text size"), "kind": "int", "min": 8, "max": 200},
    {"name": "subFontSize", "label": N_("Second text size"), "kind": "int", "min": 8, "max": 100},
]
DATA_COLOR = {"name": "dataColor", "label": N_("Colour"), "kind": "color"}
HEADER = {"name": "headerText", "label": N_("Title"), "kind": "text", "max": 80}
UNIT = {"name": "unit", "label": N_("Unit"), "kind": "choice", "choices": TEMPERATURE_UNITS}
DEVICE = {"name": "deviceId", "label": N_("Device"), "kind": "device"}
CHANNEL = {"name": "channelId", "label": N_("Sensor"), "kind": "channel"}


def maximum(top):
    return {"name": "max", "label": N_("Maximum of the scale"), "kind": "int", "min": 1, "max": top}


FIELDS = {
    "xeneon-clock": [
        {"name": "left", "label": N_("Time: from the left (px)"), "kind": "int", "min": 0, "max": 1000},
        {"name": "top", "label": N_("Time: from the top (px)"), "kind": "int", "min": 0, "max": 500},
        {"name": "subLeft", "label": N_("Date: from the left (px)"), "kind": "int", "min": 0, "max": 1000},
        {"name": "subTop", "label": N_("Date: below the time (px)"), "kind": "int", "min": 0, "max": 500},
    ],
    "xeneon-weather": [
        {"name": "city", "label": N_("City"), "kind": "text", "max": 100},
        {"name": "country", "label": N_("Country"), "kind": "text", "max": 100, "optional": True},
        {"name": "latitude", "label": N_("Latitude"), "kind": "float", "min": -90, "max": 90},
        {"name": "longitude", "label": N_("Longitude"), "kind": "float", "min": -180, "max": 180},
        UNIT,
        {"name": "refreshInterval", "label": N_("Refresh every (minutes)"), "kind": "int", "min": 5, "max": 120},
        {"name": "hideForecast", "label": N_("Hide the forecast"), "kind": "bool"},
    ],
    "xeneon-media-player": [DATA_COLOR, {"name": "hideControls", "label": N_("Hide the buttons"), "kind": "bool"}],
    "xeneon-battery-status": [DATA_COLOR, {"name": "batteryDevice", "label": N_("Device"), "kind": "battery"}],
    "xeneon-calendar": [DATA_COLOR, {"name": "weekStart", "label": N_("Week starts on"), "kind": "choice",
                                     "choices": [{"value": 0, "name": N_("Monday")}, {"value": 1, "name": N_("Sunday")}]}],
    "xeneon-memory": [DATA_COLOR, HEADER, {"name": "showSwap", "label": N_("Show swap"), "kind": "bool"}],
    "xeneon-storage": [DATA_COLOR, HEADER, {"name": "mountPoint", "label": N_("File system"), "kind": "mount"},
                       {"name": "storageSensor", "label": N_("Drive temperatures"), "kind": "storageSensor"}, UNIT],
    "xeneon-temperature-history": [
        DATA_COLOR, HEADER, UNIT, maximum(1000),
        {"name": "source", "label": N_("Source"), "kind": "choice",
         "choices": [{"value": "cpu", "name": N_("CPU")}, {"value": "gpu", "name": N_("GPU")},
                     {"value": "device", "name": N_("Device sensor")}]},
        dict(DEVICE, showIf="source=device"), dict(CHANNEL, showIf="source=device"),
        {"name": "historyMinutes", "label": N_("Minutes shown"), "kind": "int", "min": 1, "max": 30},
    ],
    "xeneon-cooling-overview": [DATA_COLOR, HEADER, UNIT, maximum(50000), DEVICE],
    "xeneon-profile-shortcuts": [DATA_COLOR, HEADER, dict(DEVICE, kind="profileDevice")],
    "xeneon-device-temp": [DATA_COLOR, HEADER, UNIT, maximum(1000), DEVICE, CHANNEL],
    "xeneon-device-rpm": [DATA_COLOR, HEADER, maximum(50000), DEVICE, CHANNEL],
    "xeneon-cpu-temp": [DATA_COLOR, HEADER, UNIT, maximum(1000)],
    "xeneon-gpu-temp": [DATA_COLOR, HEADER, UNIT, maximum(1000)],
    "xeneon-cpu-load": [DATA_COLOR, HEADER, maximum(100)],
    "xeneon-gpu-load": [DATA_COLOR, HEADER, maximum(100)],
    # Quartercore's own widgets
    "xeneon-network": [
        DATA_COLOR, {"name": "uploadColor", "label": N_("Upload colour"), "kind": "color"}, HEADER,
        {"name": "interface", "label": N_("Network connection"), "kind": "netInterface"},
        {"name": "rateUnit", "label": N_("Speed in"), "kind": "choice",
         "choices": [{"value": "bytes", "name": N_("Bytes (MB/s)")}, {"value": "bits", "name": N_("Bits (Mbit/s)")}]},
        {"name": "historySeconds", "label": N_("Seconds in the graph"), "kind": "int", "min": 10, "max": 600},
    ],
    "xeneon-power": [
        DATA_COLOR, HEADER, {"name": "deviceId", "label": N_("Power supply"), "kind": "psuDevice"},
        {"name": "pricePerKwh", "label": N_("Price per kWh"), "kind": "float", "min": 0, "max": 100},
        {"name": "currency", "label": N_("Currency"), "kind": "text", "max": 8, "optional": True},
        {"name": "historyMinutes", "label": N_("Minutes in the graph"), "kind": "int", "min": 1, "max": 60},
    ],
    "xeneon-gpu-details": [DATA_COLOR, HEADER, UNIT],
    "xeneon-homeassistant": [
        DATA_COLOR, dict(HEADER, optional=True),
        {"name": "entities", "label": N_("Entities"), "kind": "haEntities", "max": 4000, "optional": True},
        {"name": "refreshSeconds", "label": N_("Refresh every (seconds)"), "kind": "int", "min": 2, "max": 300},
    ],
    "xeneon-ha-buttons": [
        DATA_COLOR, dict(HEADER, optional=True),
        {"name": "entities", "label": N_("Entities"), "kind": "haEntities", "max": 4000, "optional": True},
        {"name": "refreshSeconds", "label": N_("Refresh every (seconds)"), "kind": "int", "min": 2, "max": 300},
    ],
    "xeneon-processes": [
        DATA_COLOR, HEADER,
        {"name": "sortBy", "label": N_("Sort by"), "kind": "choice",
         "choices": [{"value": "cpu", "name": N_("CPU")}, {"value": "memory", "name": N_("Memory")}]},
        {"name": "count", "label": N_("Number of processes"), "kind": "int", "min": 1, "max": 15},
    ],
    "xeneon-system": [DATA_COLOR, HEADER],
}


def fields(template):
    return COMMON + FIELDS.get(template, [])


def check_settings(settings):
    """None when the settings are fine, else the label of the first wrong field (like ProcessSaveWidget)."""
    template = settings.get("template")
    for field in fields(template):
        if "showIf" in field:
            key, _, wanted = field["showIf"].partition("=")
            if str(settings.get(key)) != wanted:
                continue
        value = settings.get(field["name"])
        kind = field["kind"]
        if kind == "color":
            if not COLOR.match(str(value or "")):
                return field["label"]
        elif kind in ("int", "float"):
            try:
                number = float(value)
            except (TypeError, ValueError):
                return field["label"]
            if (kind == "int" and number != int(number)) or not field["min"] <= number <= field["max"]:
                return field["label"]
        elif kind in ("text", "haEntities"):
            text = str(value or "").strip()
            if (not text and not field.get("optional")) or len(text) > field["max"]:
                return field["label"]
        elif kind == "choice":
            if value not in [c["value"] for c in field["choices"]]:
                return field["label"]
        elif kind in ("device", "profileDevice", "battery", "storageSensor", "netInterface", "psuDevice") \
                and len(str(value or "")) > 128:
            return field["label"]
        elif kind == "mount" and value and not str(value).startswith("/"):
            return field["label"]
        elif kind == "channel":
            try:
                if int(value or 0) < 0:
                    return field["label"]
            except (TypeError, ValueError):
                return field["label"]
    if template == "xeneon-temperature-history" and settings.get("source") == "device" and not settings.get("deviceId"):
        return N_("Device")
    return None


def clean(layout):
    """A copy without the fields only the editor uses."""
    out = copy.deepcopy(layout)
    for item in out["items"]:
        item.pop("key", None)
    return out
