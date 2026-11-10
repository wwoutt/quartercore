# CPU and GPU temperature for the temperature effects
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Like OpenLinkHub's temperatures.GetCpuTemperature (by Nikola Jurkovic): the
# first k10temp, zenpower or coretemp chip in /sys/class/hwmon. The GPU: an
# AMD card from hwmon, otherwise nvidia-smi, at most every 5 seconds.

import os
import subprocess
import time
from pathlib import Path

HWMON = Path("/sys/class/hwmon")
CPU_CHIPS = ("k10temp", "zenpower", "coretemp")
GPU_INTERVAL = 5


def chips(root=HWMON):
    found = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return found
    for entry in entries:
        try:
            found.append(((Path(root) / entry / "name").read_text().strip(), Path(root) / entry))
        except OSError:
            continue
    return found


def temp1(folder):
    try:
        return int((folder / "temp1_input").read_text().strip()) / 1000
    except (OSError, ValueError):
        return None


class Temperatures:
    def __init__(self, root=HWMON, clock=time.monotonic, run=subprocess.run):
        self.root = root
        self.clock = clock
        self.run = run
        self.gpu_value = 0.0
        self.gpu_time = None

    def cpu(self):
        found = chips(self.root)
        for name in CPU_CHIPS:
            for chip, folder in found:
                value = temp1(folder) if chip == name else None
                if value:
                    return value
        return 0.0

    def gpu(self):
        if self.gpu_time is not None and self.clock() - self.gpu_time < GPU_INTERVAL:
            return self.gpu_value
        self.gpu_time = self.clock()
        for chip, folder in chips(self.root):
            if chip == "amdgpu" and temp1(folder) is not None:
                self.gpu_value = temp1(folder)
                return self.gpu_value
        try:
            out = self.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=2)
            self.gpu_value = float(out.stdout.split()[0])
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            self.gpu_value = 0.0
        return self.gpu_value


def hwmon_input(path):
    """GetHwMonTemperature: a hwmon temp*_input file in millidegrees, rounded to 0.01 degree."""
    try:
        return round(int(Path(path).read_text().strip()) / 10.0) / 100.0
    except (OSError, ValueError):
        return 0.0
