# Fan and pump speeds of the iCUE LINK System Hub, worked out without setting them (step F1)
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (updateDeviceSpeed in
# src/devices/lsh/lsh.go and Interpolate in src/temperatures). While
# OpenLinkHub drives the hub, the shadow reads the hub and the temperature
# profiles through OpenLinkHub's API every 3 seconds and works out the speed
# every channel would get, with its own temperature readings and with the ones
# OpenLinkHub reports. It sends nothing to the hub. Changes are written to
# ~/.local/state/Quartercore/cooling-shadow.jsonl, to compare before step F3.

import json
import math
import os
import threading
import time
import urllib.request
from pathlib import Path

from . import temperatures

INTERVAL = 3
HUB_PRODUCT = "iCUE LINK System Hub"
CPU, GPU, LIQUID, STORAGE, PROBE, CPU_GPU, HWMON, EXECUTABLE, MULTI_GPU, GLOBAL, PSU, MULTI_GPUS = range(12)
SENSOR_NAMES = {CPU: "CPU", GPU: "GPU", LIQUID: "liquid", STORAGE: "storage", PROBE: "probe", CPU_GPU: "CPU + GPU",
                HWMON: "hwmon", EXECUTABLE: "program", MULTI_GPU: "GPU", GLOBAL: "device", PSU: "power supply",
                MULTI_GPUS: "GPUs"}
LOG_LIMIT = 2 * 1024 * 1024


def state_folder():
    home = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return home / "Quartercore"


def interpolate(points, temp):
    """temperatures.Interpolate: linear between the curve points, flat outside them."""
    points = sorted(((float(p.get("x", 0)), float(p.get("y", 0))) for p in points or []), key=lambda p: p[0])
    if not points:
        return 0.0
    if temp <= points[0][0]:
        return points[0][1]
    if temp >= points[-1][0]:
        return points[-1][1]
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        if ax <= temp <= bx:
            return ay + (temp - ax) / (bx - ax) * (by - ay) if bx != ax else ay
    return 0.0


def go_round(value):
    """math.Round of Go: halves away from zero."""
    return int(math.floor(value + 0.5)) if value >= 0 else -int(math.floor(-value + 0.5))


def is_pump(device):
    """ContainsPump isn't in OpenLinkHub's API; the pump is in its AIOs (TITAN, H-series) and pump devices."""
    name = str(device.get("name") or "").lower()
    return bool(device.get("AIO")) or "pump" in name or device.get("description") == "Pump"


def speed(device, profile, temp, graph=True):
    """The speed in % OpenLinkHub sets for one channel at this temperature."""
    if graph:
        points = profile.get("points") or {}
        pump = go_round(interpolate(points.get("0") or points.get(0), temp))
        fans = go_round(interpolate(points.get("1") or points.get(1), temp))
        if fans < 20 and not profile.get("zeroRpm"):
            fans = 20
        if device.get("AIO"):
            if device.get("TitanAIO"):
                pump = max(pump, 31)
            elif pump < 50:
                pump = 70
        elif pump < 20:
            pump = 30
        return min(pump, 100) if is_pump(device) else min(fans, 100)
    for step in profile.get("profiles") or []:
        if float(step.get("min", 0)) + 0.1 <= temp <= float(step.get("max", 0)):
            fans, pump = int(step.get("fans", 0)), int(step.get("pump", 0))
            if fans < 20 and not profile.get("zeroRpm"):
                fans = 20
            if pump > 100:
                pump = 70
            if device.get("AIO"):
                if pump < 50:
                    pump = 70
            elif pump < 20:
                pump = 30
            return pump if is_pump(device) else fans
    return None


def sensor_temperature(profile, hub_devices, readings):
    """The temperature a profile uses, from readings {"cpu", "gpu"} and the hub's own devices.
    None when the shadow can't read that sensor (a program, another device)."""
    sensor = int(profile.get("sensor") or 0)
    if sensor == CPU:
        temp = readings.get("cpu") or 0
    elif sensor in (GPU, MULTI_GPU, MULTI_GPUS):
        temp = readings.get("gpu") or readings.get("cpu") or 70
    elif sensor == LIQUID:
        temp = next((float(d.get("temperature") or 0) for d in hub_devices.values() if is_pump(d)), 0)
    elif sensor == PROBE:
        device = hub_devices.get(str(profile.get("channelId")))
        temp = float(device.get("temperature") or 0) if device and device.get("IsTemperatureProbe") else 0
    elif sensor == CPU_GPU:
        temp = max(readings.get("cpu") or 0, readings.get("gpu") or 50)
    elif sensor == PSU:
        temp = next((float(d.get("temperature") or 0) for d in hub_devices.values() if d.get("IsPSU")), 0)
    elif sensor == HWMON:
        temp = temperatures.hwmon_input(profile.get("device") or "")
    else:
        return None
    return float(temp) if temp else 50.0       # OpenLinkHub: every reading failed -> 50


def plan(hub, profiles, readings, graph=True):
    """{channel id: {"name", "profile", "sensor", "temperature", "speed", "rpm"}} for the channels with a speed."""
    devices = hub.get("devices") or {}
    out = {}
    for key, device in sorted(devices.items(), key=lambda kv: int(kv[0])):
        if not device.get("HasSpeed"):
            continue
        name = device.get("profile") or "Normal"
        profile = profiles.get(name) or profiles.get("Normal") or {}
        temp = sensor_temperature(profile, devices, readings)
        out[str(device.get("channelId", key))] = {
            "name": device.get("name") or "", "profile": name,
            "sensor": SENSOR_NAMES.get(int(profile.get("sensor") or 0), "?"),
            "temperature": None if temp is None else round(temp, 1),
            "speed": None if temp is None else speed(device, profile, temp, graph),
            "rpm": int(device.get("rpm") or 0)}
    return out


def get_json(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as reply:
        return json.loads(reply.read())


class Shadow:
    """Works out the hub's speeds every INTERVAL seconds; status() for the API, a log of the changes."""

    def __init__(self, openlinkhub, temps=None, fetch=get_json, clock=time.time, log_folder=None):
        self.openlinkhub = openlinkhub.rstrip("/")
        self.temps = temps or temperatures.Temperatures()
        self.fetch = fetch
        self.clock = clock
        self.log_path = Path(log_folder or state_folder()) / "cooling-shadow.jsonl"
        self.lock = threading.Lock()
        self.hubs = {}            # serial -> latest status
        self.last_logged = {}
        self.error = ""

    def tick(self):
        try:
            devices = self.fetch(self.openlinkhub + "/api/devices/").get("devices") or {}
            hubs = [s for s, d in devices.items() if d.get("Product") == HUB_PRODUCT]
            if not hubs:
                return
            profiles = self.fetch(self.openlinkhub + "/api/temperatures/").get("data") or {}
            profiles = {k: v for k, v in profiles.items() if isinstance(v, dict)}
            ours = {"cpu": self.temps.cpu(), "gpu": self.temps.gpu()}
            for serial in hubs:
                hub = self.fetch(self.openlinkhub + "/api/devices/" + serial).get("device") or {}
                theirs = {"cpu": float(hub.get("CpuTemp") or 0), "gpu": float(hub.get("GpuTemp") or 0)}
                status = {"time": round(self.clock()), "cpu": round(ours["cpu"], 1), "gpu": round(ours["gpu"], 1),
                          "openlinkhubCpu": round(theirs["cpu"], 1), "openlinkhubGpu": round(theirs["gpu"], 1),
                          "channels": plan(hub, profiles, ours),
                          "openlinkhubChannels": plan(hub, profiles, theirs)}
                with self.lock:
                    self.hubs[serial] = status
                self._log(serial, status)
            self.error = ""
        except (OSError, ValueError, AttributeError, TypeError) as e:
            self.error = str(e)

    def _log(self, serial, status):
        speeds = {k: (c["speed"], status["openlinkhubChannels"].get(k, {}).get("speed"))
                  for k, c in status["channels"].items()}
        if self.last_logged.get(serial) == speeds:
            return
        self.last_logged[serial] = speeds
        line = {"time": status["time"], "hub": serial, "cpu": status["cpu"], "openlinkhubCpu": status["openlinkhubCpu"],
                "channels": {k: {"speed": c["speed"], "openlinkhub": speeds[k][1], "rpm": c["rpm"],
                                 "profile": c["profile"]} for k, c in status["channels"].items()}}
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if self.log_path.exists() and self.log_path.stat().st_size > LOG_LIMIT:
                self.log_path.replace(self.log_path.with_suffix(".old.jsonl"))
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(line) + "\n")
        except OSError as e:
            self.error = str(e)

    def status(self, serial=None):
        with self.lock:
            if serial is not None:
                return self.hubs.get(serial)
            return {"hubs": dict(self.hubs), "error": self.error, "log": str(self.log_path)}
