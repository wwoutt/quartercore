# Batteries of devices outside OpenLinkHub: Razer mice and headsets, Bluetooth and other wireless devices
# Author: wwoutt (2026-11-12), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Only reads files in /sys, nothing is sent to a device:
# - Razer: the OpenRazer kernel driver (razermouse, razerkbd, ...) has charge_level
#   (0-255) and charge_status for wireless devices. The files belong to the group
#   plugdev, so the user must be in that group (and logged in again after joining).
# - Everything else the kernel knows: /sys/class/power_supply with scope "Device"
#   (Logitech, Bluetooth headsets, game controllers, ...), not the computer's own battery.
# The answers look like OpenLinkHub's /api/systray batteries: key -> {"Device", "Level"},
# plus "Charging".

from pathlib import Path

RAZER = Path("/sys/bus/hid/drivers")
RAZER_DRIVERS = ("razermouse", "razerkbd", "razerkraken", "razeraccessory", "razermousemat", "razercore")
POWER_SUPPLY = Path("/sys/class/power_supply")


def _read(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeDecodeError):
        return ""


def razer_batteries(root=RAZER):
    """(batteries, denied): denied is True when a Razer battery exists but can't be read."""
    out, denied = {}, False
    for driver in RAZER_DRIVERS:
        for device in sorted((Path(root) / driver).glob("*:*")):
            level_file = device / "charge_level"
            if not level_file.exists():
                continue
            try:
                raw = int(level_file.read_text().strip())
            except PermissionError:
                denied = True
                continue
            except (OSError, ValueError):
                continue
            serial = _read(device / "device_serial") or device.name
            key = "razer:" + serial
            if key in out:              # one device has several interfaces
                continue
            out[key] = {"Device": _read(device / "device_type") or "Razer", "Level": round(raw * 100 / 255),
                        "Charging": _read(device / "charge_status") == "1"}
    return out, denied


def kernel_batteries(root=POWER_SUPPLY):
    out = {}
    for supply in sorted(Path(root).glob("*")):
        if _read(supply / "scope") != "Device" or _read(supply / "type") != "Battery":
            continue
        level = _read(supply / "capacity")
        if not level.isdigit():
            continue
        name = " ".join(p for p in (_read(supply / "manufacturer"), _read(supply / "model_name")) if p)
        key = "kernel:" + (_read(supply / "serial_number") or supply.name)
        out[key] = {"Device": name or supply.name, "Level": int(level),
                    "Charging": _read(supply / "status") == "Charging"}
    return out


def other_batteries():
    """Every battery Quartercore reads itself: (batteries, razer_denied)."""
    razer, denied = razer_batteries()
    return dict(razer, **kernel_batteries()), denied
