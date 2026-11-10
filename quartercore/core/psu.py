# Corsair HID power supplies (HX1500i and others): readings and fan mode
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/devices/psuhid/psuhid.go).
# Readings come from the kernel driver corsair-psu (hwmon) when it is loaded:
# that needs no permissions and nothing is sent to the power supply. Without
# it, they are read with OpenLinkHub's HID commands. The fan mode is always
# set with OpenLinkHub's HID commands; on stop the fan goes back to the power
# supply's own curve, like OpenLinkHub does.

import os
import threading
import time
from pathlib import Path

from . import hid

VENDOR = 0x1B1C
# OpenLinkHub's Psu list (devices.go)
PRODUCTS = {7198: "HX1000i", 7203: "HX1200i", 7199: "HX1500i", 7173: "HX750i", 7174: "HX850i",
            7175: "HX1000i", 7176: "HX1200i", 7181: "RM1000i", 7180: "RM850i", 7207: "HX1200i"}
FAN_MODES = {0: "Default", 4: "40 %", 5: "50 %", 6: "60 %", 7: "70 %", 8: "80 %", 9: "90 %", 10: "100 %"}

# Commands of psuhid.go
CMD_INIT, CMD_READ, CMD_WRITE = 0xFE, 0x03, 0x02
CMD_SET_FAN_MODE, FAN_MODE_DEFAULT, FAN_MODE_MANUAL = 0xF0, 0x00, 0x01
SET_FAN_SPEED = 0x3B
CMD_SWITCH = 0x00
RAIL_12V, RAIL_5V, RAIL_3V = 0x00, 0x01, 0x02
GET_AMPS, GET_VOLTS, GET_WATTS = 0x8C, 0x8B, 0x96
POWER_OUT, INPUT_VOLTAGE, FAN_SPEED = 0xEE, 0x88, 0x90
TEMP_SENSORS = (0x8D, 0x8E)


def packet(mode, command, data=0):
    """65 bytes: report id 0, then mode, command, data (createPacket)."""
    buf = bytearray(65)
    buf[1], buf[2] = mode, command
    if data:
        buf[3] = data
    return bytes(buf)


def linear11(reply):
    """PMBus LINEAR11 number in bytes 2-3 of a reply (common.FromLinear11)."""
    value = reply[2] | reply[3] << 8
    fraction, exponent = value & 0x7FF, value >> 11
    if fraction > 1023:
        fraction -= 2048
    if exponent > 15:
        exponent -= 32
    return fraction * 2.0 ** exponent


def fan_packets(mode):
    """The packets updateFanMode sends for a fan mode (0 = the PSU's own curve, 4-10 = 40-100 %)."""
    if mode == 0:
        return [packet(CMD_WRITE, CMD_SET_FAN_MODE, FAN_MODE_DEFAULT)]
    speed = max(40, min(100, mode * 10))
    return [packet(CMD_WRITE, CMD_SET_FAN_MODE, FAN_MODE_MANUAL), packet(CMD_WRITE, SET_FAN_SPEED, speed)]


def floor2(value):
    return int(value * 100) / 100


def hwmon_folder(usb, root=Path("/sys/class/hwmon")):
    """The corsairpsu hwmon folder of the power supply at this USB path."""
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return None
    for entry in entries:
        folder = Path(root) / entry
        try:
            if (folder / "name").read_text().strip() != "corsairpsu":
                continue
            device = os.path.realpath(folder / "device")
        except OSError:
            continue
        if not usb or ("/sys" + usb) in device or usb in device:
            return folder
    return None


def read_hwmon(folder):
    """Readings from corsair-psu: in*/curr* in milli units, power* in micro watts, temp* in milli degrees."""
    def value(name, scale):
        try:
            return int((Path(folder) / name).read_text().strip()) / scale
        except (OSError, ValueError):
            return None
    return {
        "inputVoltage": value("in0_input", 1000), "fan": value("fan1_input", 1),
        "vrm": value("temp1_input", 1000), "case": value("temp2_input", 1000),
        "powerOut": value("power1_input", 1e6),
        "rails": [(value("in%d_input" % (i + 1), 1000), value("curr%d_input" % (i + 2), 1000),
                   value("power%d_input" % (i + 2), 1e6)) for i in range(3)],
    }


def channels(product, r):
    """The devices map of OpenLinkHub's psuhid page, from the readings."""
    def temp(v):
        return "%.1f °C" % v if v and v > 1 else ""

    def channel(cid, name, **values):
        base = {"channelId": cid, "name": name, "label": name, "rpm": 0, "volts": 0, "amps": 0, "watts": 0,
                "temperature": 0, "temperatureString": "", "HasSpeed": False, "HasTemps": False,
                "HasWatts": False, "HasVolts": False, "HasAmps": False, "MainPSU": False}
        base.update(values)
        return base
    out = {
        "0": channel(0, product, label="PSU", watts=floor2(r.get("powerOut") or 0), HasWatts=True, MainPSU=True),
        "1": channel(1, "Fan 1", label="PSU Fan", rpm=int(r.get("fan") or 0), HasSpeed=True),
        "2": channel(2, "VRM Temperature", temperature=r.get("vrm") or 0, temperatureString=temp(r.get("vrm")),
                     HasTemps=True),
        "3": channel(3, "PSU Temperature", temperature=r.get("case") or 0, temperatureString=temp(r.get("case")),
                     HasTemps=True),
        "4": channel(4, "Power Out", watts=floor2(r.get("powerOut") or 0), HasWatts=True),
    }
    for i, name in enumerate(("12V Rail", "5V Rail", "3V Rail")):
        volts, amps, watts = (r.get("rails") or [(0, 0, 0)] * 3)[i]
        out[str(5 + i)] = channel(5 + i, name, volts=floor2(volts or 0), amps=floor2(amps or 0),
                                  watts=floor2(watts or 0), HasWatts=True, HasVolts=True, HasAmps=True)
    return out


class PowerSupply:
    """One Corsair HID power supply driven by quartercore-core."""

    def __init__(self, info, store, opener=hid.HidDevice, hwmon_root=Path("/sys/class/hwmon")):
        self.info = info
        self.store = store
        self.opener = opener
        self.hwmon_root = hwmon_root
        self.product = PRODUCTS.get(info["product"], "Power Supply")
        self.serial = hid.serial_for(info["usbPath"])
        self.lock = threading.Lock()
        self.device = None
        self.readings = {}
        self.settings = store.load(self.serial, {"FanMode": 0})
        self.error = ""

    # --- HID ---

    def _hid(self):
        if self.device is None:
            self.device = self.opener(self.info["node"])
        return self.device

    def _send(self, buf):
        """transfer(): the reply starts with the mode and command of the packet."""
        return self._hid().transfer(buf, buf[1:3])

    def _init(self):
        self._send(packet(CMD_INIT, CMD_READ))

    def _read(self, command):
        self._init()
        return linear11(self._send(packet(CMD_READ, command)))

    def read_hid(self):
        """getDeviceData with HID commands, for when the kernel driver isn't there."""
        r = {"inputVoltage": self._read(INPUT_VOLTAGE), "fan": self._read(FAN_SPEED),
             "vrm": self._read(TEMP_SENSORS[0]), "case": self._read(TEMP_SENSORS[1])}
        self._init()
        self._send(packet(CMD_WRITE, CMD_SWITCH, RAIL_12V))
        r["powerOut"] = self._read(POWER_OUT)
        rails = []
        for rail in (RAIL_12V, RAIL_5V, RAIL_3V):
            self._init()
            self._send(packet(CMD_WRITE, CMD_SWITCH, rail))
            rails.append((self._read(GET_VOLTS), self._read(GET_AMPS), self._read(GET_WATTS)))
        r["rails"] = rails
        return r

    # --- running ---

    def start(self):
        """Applies the saved fan mode, like OpenLinkHub's Init does."""
        self.set_fan_mode(int(self.settings.get("FanMode") or 0), save=False)

    def refresh(self):
        folder = hwmon_folder(self.info["usbPath"], self.hwmon_root)
        try:
            with self.lock:
                self.readings = read_hwmon(folder) if folder else self.read_hid()
            self.error = ""
        except (OSError, TimeoutError) as e:
            self.error = str(e)

    def stop(self):
        """Back to the power supply's own fan curve (Stop / setFanToDefault)."""
        try:
            with self.lock:
                for buf in fan_packets(0):
                    self._init()
                    self._send(buf)
        except (OSError, TimeoutError):
            pass
        if self.device is not None:
            self.device.close()
            self.device = None

    def set_fan_mode(self, mode, save=True):
        """UpdatePsuFan: 0 = default, 4-10 = 40-100 %; returns an error text or ""."""
        if not 0 <= mode <= 10:
            return "Invalid fan mode"
        try:
            with self.lock:
                for buf in fan_packets(mode):
                    self._send(buf)
        except (OSError, TimeoutError) as e:
            return "Unable to change fan mode: %s" % e
        self.settings["FanMode"] = mode
        if save:
            self.store.save(self.serial, self.settings)
        return ""

    # --- API ---

    def handle(self, path, body, method="POST"):
        """POST requests of the web page; None when this isn't one of them."""
        if method != "POST":
            return None
        if path == "/api/psu/speed":
            try:
                return self.set_fan_mode(int(body.get("fanMode", -1)))
            except (TypeError, ValueError):
                return "Invalid fan mode"
        return None

    def summary(self):
        return {"Product": self.product, "Serial": self.serial, "Template": "psuhid.html"}

    def device_json(self):
        """GET /api/devices/<serial>, in the shape of OpenLinkHub's psuhid device."""
        return {
            "serial": self.serial, "product": self.product, "firmware": "", "Template": "psuhid.html",
            "InputVoltage": self.readings.get("inputVoltage") or 0,
            "DeviceProfile": {"FanMode": int(self.settings.get("FanMode") or 0), "Serial": self.serial},
            "FanModes": {str(k): v for k, v in FAN_MODES.items()},
            "devices": channels(self.product, self.readings),
            "DrivenBy": "quartercore-core", "Error": self.error,
        }


def discover(store, root=hid.SYS_HIDRAW, opener=hid.HidDevice, hwmon_root=Path("/sys/class/hwmon")):
    return [PowerSupply(info, store, opener, hwmon_root) for info in hid.find(VENDOR, PRODUCTS, root)
            if info["interface"] in (0, -1)]
