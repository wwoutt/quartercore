# Raw HID access through /dev/hidraw, with the Python standard library only
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Finds devices by vendor and product id in /sys/class/hidraw and exchanges
# 64-byte reports with them, like the go-hid calls in OpenLinkHub by Nikola
# Jurkovic. Access to /dev/hidrawN needs a udev rule (data/udev/).

import hashlib
import os
import select
import time
from pathlib import Path

SYS_HIDRAW = Path("/sys/class/hidraw")


def find(vendor, products, root=SYS_HIDRAW):
    """[{"node": "/dev/hidrawN", "product": id, "interface": n, "usbPath": "/devices/..."}]."""
    found = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return found
    for entry in entries:
        device = Path(root) / entry / "device"
        try:
            uevent = (device / "uevent").read_text()
        except OSError:
            continue
        hid_id = next((line.split("=", 1)[1] for line in uevent.splitlines() if line.startswith("HID_ID=")), "")
        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        vid, pid = int(parts[1], 16), int(parts[2], 16)
        if vid != vendor or pid not in products:
            continue
        found.append({"node": "/dev/" + entry, "product": pid, "interface": interface(device),
                      "usbPath": usb_path(device), "name": hid_name(uevent)})
    return found


def hid_name(uevent):
    return next((line.split("=", 1)[1] for line in uevent.splitlines() if line.startswith("HID_NAME=")), "")


def interface(device):
    """bInterfaceNumber of the USB interface the HID device belongs to."""
    try:
        resolved = Path(os.path.realpath(device))
        return int((resolved.parent / "bInterfaceNumber").read_text().strip(), 16)
    except (OSError, ValueError):
        return -1


def usb_path(device):
    """The USB device node above a hidraw device, like GetShortUSBDevPath in OpenLinkHub."""
    path = Path(os.path.realpath(device))
    while path != path.parent:
        if (path / "idVendor").exists():
            text = str(path)
            return text[len("/sys"):] if text.startswith("/sys") else text
        path = path.parent
    return ""


def serial_for(usb):
    """OpenLinkHub's id for power supplies: md5 of the USB device path."""
    return hashlib.md5(usb.encode()).hexdigest()


class HidDevice:
    """One open /dev/hidrawN."""

    def __init__(self, node, size=64):
        self.node = node
        self.size = size
        self.fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def write(self, data):
        return os.write(self.fd, bytes(data))

    def read(self, timeout):
        """One report, or b"" when nothing came within timeout seconds."""
        ready, _, _ = select.select([self.fd], [], [], max(0, timeout))
        if not ready:
            return b""
        try:
            return os.read(self.fd, self.size)
        except BlockingIOError:
            return b""

    def transfer(self, packet, match, timeout=1.0):
        """Writes a packet and waits for the reply whose first bytes equal match."""
        self.write(packet)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("no matching reply from " + self.node)
            reply = self.read(remaining)
            if reply and reply[:len(match)] == bytes(match):
                return reply
