# System sensors read by Quartercore itself: CPU, GPU, memory, storage
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/temperatures/temperatures.go
# and src/systeminfo/systeminfo.go), so the XENEON EDGE kiosk doesn't need
# OpenLinkHub for these values. The answers have the same shape as the
# OpenLinkHub API (/api/cpuTemp/clean, /api/stats/memory, ...).
#
# Everything here only reads files in /sys and /proc; the NVIDIA values come
# from nvidia-smi, started without blocking the interface (QProcess).

import os
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

HWMON = Path("/sys/class/hwmon")
CPU_CHIPS = ("k10temp", "zenpower", "coretemp")   # OpenLinkHub's cpuPackages, in this order
STORAGE_CHIPS = ("nvme", "drivetemp")
FILESYSTEMS = {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "vfat", "exfat", "ntfs", "ntfs3", "zfs"}
MOUNT_ESCAPES = (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\"))


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def hwmon_chips(root=HWMON):
    """[(name, folder)] of every hwmon chip, sorted like os.ReadDir."""
    chips = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return chips
    for entry in entries:
        name = read(Path(root) / entry / "name")
        if name is not None:
            chips.append((name, Path(root) / entry))
    return chips


def millidegrees(path):
    text = read(path)
    try:
        return int(text) / 1000 if text is not None else None
    except ValueError:
        return None


def cpu_temperature(root=HWMON, chip=None):
    """temp1_input of the first CPU chip (Package id 0 on Intel), like GetCpuTemperature."""
    wanted = (chip,) if chip else CPU_CHIPS
    chips = hwmon_chips(root)
    for name in wanted:
        for chip_name, folder in chips:
            if chip_name == name:
                value = millidegrees(folder / "temp1_input")
                if value:
                    return int(value * 100) / 100
    return None


def amd_gpu_temperature(root=HWMON):
    for name, folder in hwmon_chips(root):
        if name == "amdgpu":
            value = millidegrees(folder / "temp1_input")
            if value is not None:
                return value
    return None


def amd_gpu_load(drm=Path("/sys/class/drm")):
    try:
        cards = sorted(os.listdir(drm))
    except OSError:
        return None
    for card in cards:
        value = read(Path(drm) / card / "device" / "gpu_busy_percent")
        if value is not None and value.isdigit():
            return int(value)
    return None


def storage_temperatures(root=HWMON):
    """Like GetStorageTemperatures: nvme and drivetemp chips with their model."""
    sensors = []
    for name, folder in hwmon_chips(root):
        if name not in STORAGE_CHIPS:
            continue
        value = millidegrees(folder / "temp1_input")
        model = read(folder / "device" / "model")
        if value is None or model is None:
            continue
        sensors.append({"Key": folder.name, "Model": model, "Temperature": int(value),
                        "TemperatureString": "%.1f °C" % int(value)})
    return sensors


class CpuLoad:
    """CPU use since the previous call, from /proc/stat (GetCpuUtilization)."""

    def __init__(self, path="/proc/stat"):
        self.path = path
        self.total = self.idle = 0

    def read(self):
        text = read(self.path)
        if not text:
            return None
        fields = text.splitlines()[0].split()
        if fields[0] != "cpu" or len(fields) < 8:
            return None
        user, nice, system, idle, iowait, irq, softirq = (int(f) for f in fields[1:8])
        total = user + nice + system + idle + iowait + irq + softirq
        idle_time = idle + iowait
        total_diff, idle_diff = total - self.total, idle_time - self.idle
        self.total, self.idle = total, idle_time
        if total_diff <= 0:
            return None
        return (total_diff - idle_diff) / total_diff * 100


def memory_usage(path="/proc/meminfo"):
    """Like parseMemoryUsage: used memory without the reclaimable part."""
    text = read(path)
    if not text:
        return None
    values = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] == "kB":
            values[fields[0].rstrip(":")] = int(fields[1]) * 1024
    try:
        total, available = values["MemTotal"], values["MemAvailable"]
        swap_total, swap_free = values["SwapTotal"], values["SwapFree"]
    except KeyError:
        return None
    if total == 0 or available > total or swap_free > swap_total:
        return None
    used, swap_used = total - available, swap_total - swap_free
    return {"Total": total, "Available": available, "Used": used, "UsedPercent": used / total * 100,
            "SwapTotal": swap_total, "SwapUsed": swap_used,
            "SwapPercent": swap_used / swap_total * 100 if swap_total else 0}


def decode_mount(text):
    for escaped, plain in MOUNT_ESCAPES:
        text = text.replace(escaped, plain)
    return text


def storage_mounts(path="/proc/self/mountinfo"):
    """Local file systems, one row per mount point (parseStorageMounts)."""
    text = read(path)
    rows, seen = [], set()
    for line in (text or "").splitlines():
        parts = line.split(" - ", 1)
        if len(parts) != 2:
            continue
        mount, device = parts[0].split(), parts[1].split()
        if len(mount) < 6 or len(device) < 3 or device[0] not in FILESYSTEMS:
            continue
        point = decode_mount(mount[4])
        if point in seen:
            continue
        seen.add(point)
        rows.append({"MountPoint": point, "Device": decode_mount(device[1]), "Filesystem": device[0],
                     "Total": 0, "Used": 0, "Available": 0, "UsedPercent": 0, "AvailableData": False})
    return rows


def storage_usage(path="/proc/self/mountinfo"):
    rows = storage_mounts(path)
    for row in rows:
        try:
            st = os.statvfs(row["MountPoint"])
        except OSError:
            continue
        if st.f_frsize <= 0 or st.f_blocks == 0 or st.f_bfree > st.f_blocks or st.f_bavail > st.f_bfree:
            continue
        size = st.f_frsize
        row.update(Total=st.f_blocks * size, Used=(st.f_blocks - st.f_bfree) * size,
                   Available=st.f_bavail * size, AvailableData=True)
        row["UsedPercent"] = row["Used"] / row["Total"] * 100
    return rows


def parse_nvidia(output):
    """"39, 23" from nvidia-smi --query-gpu=temperature.gpu,utilization.gpu -> (39.0, 23.0)."""
    line = (output or "").strip().splitlines()[0] if (output or "").strip() else ""
    try:
        temperature, load = (float(v) for v in line.split(","))
    except ValueError:
        return None, None
    return temperature, load


class GpuReader(QObject):
    """GPU temperature and load: NVIDIA through nvidia-smi (asynchronous), else AMD from /sys."""
    updated = Signal()

    def __init__(self, parent=None, program="nvidia-smi"):
        super().__init__(parent)
        self.program = program
        self.temperature = self.load = None
        self._process = None
        self._nvidia = None   # unknown until the first try

    def refresh(self):
        if self._nvidia is False:
            self.temperature, self.load = amd_gpu_temperature(), amd_gpu_load()
            self.updated.emit()
            return
        if self._process is not None:
            return
        process = QProcess(self)
        process.finished.connect(lambda code, _status: self._finished(process, code))
        process.errorOccurred.connect(lambda _e: self._finished(process, -1))
        self._process = process
        process.start(self.program, ["--query-gpu=temperature.gpu,utilization.gpu",
                                     "--format=csv,noheader,nounits", "-i", "0"])

    def _finished(self, process, code):
        if self._process is not process:
            return
        self._process = None
        temperature, load = (parse_nvidia(bytes(process.readAllStandardOutput()).decode(errors="replace"))
                             if code == 0 else (None, None))
        process.deleteLater()
        if temperature is None and self._nvidia is None:
            # No NVIDIA card (or no nvidia-smi): use the AMD values from now on
            self._nvidia = False
            self.refresh()
            return
        self._nvidia = self._nvidia or temperature is not None
        self.temperature, self.load = temperature, load
        self.updated.emit()
