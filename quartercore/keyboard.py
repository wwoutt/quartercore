# Keyboards: key layout for drawing, per-key colours and the keyboard settings
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# OpenLinkHub describes a keyboard as rows of keys. Every key has a width and
# a "left" distance to the key before it, so a row is laid out from left to
# right. Light bars at the sides are keys too (css "left-led-N", "right-led-N");
# they are drawn as strips along the edges.

import re
from collections import Counter

LED = re.compile(r"(left|right)-led-(\d+)")
KEY_HEIGHT = 70
STRIP_WIDTH = 10


def to_hex(c):
    c = c or {}
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c.get(k) or 0))) for k in ("red", "green", "blue"))


def most_common(values, default):
    values = list(values)
    return Counter(values).most_common(1)[0][0] if values else default


def options(mapping):
    """{"1": "Volume"} -> [{"value": 1, "name": "Volume"}], sorted by value."""
    return [{"value": k, "name": v} for k, v in sorted(((int(k), v) for k, v in (mapping or {}).items()))]


def layout_keys(keyboard):
    """Positions every key: returns (keys, width, height) in OpenLinkHub's pixels."""
    keys, strips = [], []
    y_cursor = 0
    rows = sorted((keyboard.get("row") or {}).items(), key=lambda kv: int(kv[0]))
    for row_id, row in rows:
        row_keys = sorted((row.get("keys") or {}).items(), key=lambda kv: int(kv[0]))
        regular = [(int(i), k) for i, k in row_keys if not LED.search(k.get("css") or "")]
        for i, k in row_keys:
            led = LED.search(k.get("css") or "")
            if led:
                strips.append((int(i), led.group(1), int(led.group(2)), k))
        if not regular:
            continue
        top = most_common((k.get("top") or 0 for _, k in regular if (k.get("top") or 0) >= 0), 0)
        height = min(KEY_HEIGHT, most_common((k.get("height") or KEY_HEIGHT for _, k in regular), KEY_HEIGHT))
        y = y_cursor + top
        y_cursor = y + height
        # Rows below the top light bar leave room for the strip at the left edge
        x = STRIP_WIDTH if int(row_id) > 0 and strips else 0
        for key_id, k in regular:
            x += k.get("left") or 0
            width = k.get("width") or 65
            keys.append({
                "keyId": key_id, "row": int(row_id), "name": k.get("keyName") or "",
                "x": x, "y": y, "w": width,
                # Tall keys (numpad + and Enter) reach into the next row
                "h": k.get("height") if (k.get("height") or 0) > KEY_HEIGHT else height,
                "color": to_hex(k.get("color")),
                "light": bool(k.get("onlyColor")), "noColor": bool(k.get("noColor")),
            })
            x += width
    width = max((k["x"] + k["w"] for k in keys), default=0)
    height = y_cursor
    if strips:
        width += 4 + STRIP_WIDTH
        count = max(n for _, _, n, _ in strips)
        first = min((k["y"] for k in keys if k["row"] > 0), default=0)
        pitch = (height - first) / count
        for key_id, side, n, k in strips:
            keys.append({
                "keyId": key_id, "row": -1, "name": "",
                "x": 0 if side == "left" else width - STRIP_WIDTH,
                "y": first + (n - 1) * pitch, "w": STRIP_WIDTH, "h": pitch - 4,
                "color": to_hex(k.get("color")), "light": True, "noColor": False,
            })
    return keys, width, height


def keyboard_view(device):
    profile = device.get("DeviceProfile") or {}
    name = profile.get("Profile") or "default"
    keyboard = (profile.get("Keyboards") or {}).get(name) or {}
    keys, width, height = layout_keys(keyboard)
    user_profiles = device.get("userProfiles") or {}
    return {
        "serial": device.get("serial") or "",
        "product": device.get("product") or "",
        "firmware": device.get("firmware") or "",
        "keys": keys, "keysWidth": width, "keysHeight": height,
        "rgbModes": list(device.get("RGBModes") or []),
        "rgbMode": profile.get("RGBProfile") or "",
        "colorProfile": name,
        "colorProfiles": list(profile.get("Profiles") or []),
        "userProfile": next((k for k, v in user_profiles.items() if v.get("Active")), ""),
        "userProfiles": sorted(user_profiles),
        "layouts": list(device.get("Layouts") or []),
        "layout": profile.get("Layout") or "",
        "pollingRates": options(device.get("PollingRates")),
        "pollingRate": int(profile.get("PollingRate") or 0),
        "dialOptions": options(device.get("ControlDialOptions")),
        "dial": int(profile.get("ControlDial") or 0),
        "debounceTimes": options(device.get("DebounceTimes")),
        "debounceTime": int(profile.get("DebounceTime") or 0),
    }


def is_keyboard(device):
    return bool(((device.get("DeviceProfile") or {}).get("Keyboards")))
