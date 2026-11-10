# Virtual keyboard and mouse through /dev/uinput, for button actions and macros
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/inputmanager: keyboard.go,
# mouse.go, inputmanager.go). ACTIONS is OpenLinkHub's table of input actions
# (the numbers stored in key assignments and macros) with the Linux key code
# of each, read from its /api/input/media, /keyboard and /mouse (QWERTY
# layout; the controller actions need a virtual gamepad and are left out).
# Access to /dev/uinput needs the udev rule in data/udev/.

import fcntl
import os
import struct
import threading
import time

UINPUT = "/dev/uinput"
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
EV_SYN, EV_KEY, EV_REL = 0, 1, 2
REL_X, REL_Y, REL_HWHEEL, REL_WHEEL = 0x00, 0x01, 0x06, 0x08
BUTTONS = (272, 273, 274, 275, 276)                 # left, right, middle, back, forward
KEY_LEFTSHIFT, KEY_LEFTCTRL, KEY_RIGHTCTRL, KEY_LEFTALT = 42, 29, 97, 56
VENDOR, PRODUCT = 5840, 5175                        # the ids OpenLinkHub gives its virtual devices
EVENT = struct.Struct("llHHi")                      # struct input_event (timeval, type, code, value)

# Text typing (charToKey and shiftedToBase of inputmanager.go), as Linux key codes
_ROWS = (("1234567890-=", 2), ("qwertyuiop[]", 16), ("asdfghjkl;'`", 30), ("\\zxcvbnm,./", 43))
CHAR_KEYS = {c: start + i for row, start in _ROWS for i, c in enumerate(row)}
CHAR_KEYS.update({" ": 57, "\n": 28, "\r": 28, "\t": 15, "\b": 14})
SHIFTED = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+{}|:"<>?~',
                   "abcdefghijklmnopqrstuvwxyz1234567890-=[]\\;',./`"))

ACTIONS = {
    0: ('None', 0, 'key'), 1: ('Volume Up', 115, 'key'), 2: ('Volume Down', 114, 'key'), 3: ('Mute', 113, 'key'),
    4: ('Stop', 166, 'key'), 5: ('Previous', 165, 'key'), 6: ('Play', 164, 'key'), 7: ('Next', 163, 'key'),
    8: ('Number 1', 2, 'key'), 9: ('Number 2', 3, 'key'), 10: ('Number 3', 4, 'key'), 11: ('Number 4', 5, 'key'),
    12: ('Number 5', 6, 'key'), 13: ('Number 6', 7, 'key'), 14: ('Number 7', 8, 'key'), 15: ('Number 8', 9, 'key'),
    16: ('Number 9', 10, 'key'), 17: ('Number 0', 11, 'key'), 18: ('Minus (-)', 12, 'key'),
    19: ('Equals (=)', 13, 'key'), 20: ('Q', 16, 'key'), 21: ('W', 17, 'key'), 22: ('E', 18, 'key'),
    23: ('R', 19, 'key'), 24: ('T', 20, 'key'), 25: ('Y', 21, 'key'), 26: ('U', 22, 'key'), 27: ('I', 23, 'key'),
    28: ('O', 24, 'key'), 29: ('P', 25, 'key'), 30: ('A', 30, 'key'), 31: ('S', 31, 'key'), 32: ('D', 32, 'key'),
    33: ('F', 33, 'key'), 34: ('G', 34, 'key'), 35: ('H', 35, 'key'), 36: ('J', 36, 'key'), 37: ('K', 37, 'key'),
    38: ('L', 38, 'key'), 39: ('Z', 44, 'key'), 40: ('X', 45, 'key'), 41: ('C', 46, 'key'), 42: ('V', 47, 'key'),
    43: ('B', 48, 'key'), 44: ('N', 49, 'key'), 45: ('M', 50, 'key'), 46: ('F1', 59, 'key'), 47: ('F2', 60, 'key'),
    48: ('F3', 61, 'key'), 49: ('F4', 62, 'key'), 50: ('F5', 63, 'key'), 51: ('F6', 64, 'key'),
    52: ('F7', 65, 'key'), 53: ('F8', 66, 'key'), 54: ('F9', 67, 'key'), 55: ('F10', 68, 'key'),
    56: ('F11', 87, 'key'), 57: ('F12', 88, 'key'), 58: ('Back', 14, 'key'), 59: ('Tab', 15, 'key'),
    60: ('Esc', 1, 'key'), 61: ('Tilde (`)', 41, 'key'), 62: ('Left Square [{', 26, 'key'),
    63: ('Right Square }]', 27, 'key'), 64: ('Backslash (\\)', 43, 'key'), 65: ('Capslock', 58, 'key'),
    66: ('Semicolon (;)', 39, 'key'), 67: ("Single Quote (')", 40, 'key'), 68: ('Enter', 28, 'key'),
    69: ('Left Shift', 42, 'key'), 70: ('Comma (,)', 51, 'key'), 71: ('Dot (.)', 52, 'key'),
    72: ('Slash (/)', 53, 'key'), 73: ('Right Shift', 54, 'key'), 74: ('Up', 103, 'key'),
    75: ('Left Ctrl', 29, 'key'), 76: ('Windows Key', 125, 'key'), 77: ('Left Alt', 56, 'key'),
    78: ('Space', 57, 'key'), 79: ('Right Alt', 100, 'key'), 80: ('Menu', 127, 'key'),
    81: ('Right Ctrl', 97, 'key'), 82: ('Left', 105, 'key'), 83: ('Down', 108, 'key'), 84: ('Right', 106, 'key'),
    85: ('Insert', 110, 'key'), 86: ('Home', 102, 'key'), 87: ('Pg Up', 104, 'key'), 88: ('Delete', 111, 'key'),
    89: ('End', 107, 'key'), 90: ('Pg Dn', 109, 'key'), 91: ('(Mouse) Left Click', 272, 'mouse'),
    92: ('(Mouse) Right Click', 273, 'mouse'), 93: ('(Mouse) Middle Click', 274, 'mouse'),
    94: ('(Mouse) Back', 275, 'mouse'), 95: ('(Mouse) Forward', 276, 'mouse'), 96: ('Numpad 1', 79, 'key'),
    97: ('Numpad 2', 80, 'key'), 98: ('Numpad 3', 81, 'key'), 99: ('Numpad 4', 75, 'key'),
    100: ('Numpad 5', 76, 'key'), 101: ('Numpad 6', 77, 'key'), 102: ('Numpad 7', 71, 'key'),
    103: ('Numpad 8', 72, 'key'), 104: ('Numpad 9', 73, 'key'), 105: ('Numpad 0', 82, 'key'),
    106: ('Numpad Dot (.)', 83, 'key'), 107: ('Numpad Plus (+)', 78, 'key'), 108: ('Numpad Minus (-)', 74, 'key'),
    109: ('Numpad Multiply (*)', 55, 'key'), 110: ('Numpad Divide (/)', 98, 'key'),
    111: ('Numpad Enter', 96, 'key'), 112: ('F13', 183, 'key'), 113: ('F14', 184, 'key'), 114: ('F15', 185, 'key'),
    115: ('F16', 186, 'key'), 116: ('F17', 187, 'key'), 117: ('F18', 188, 'key'), 118: ('F19', 189, 'key'),
    119: ('F20', 190, 'key'), 120: ('F21', 191, 'key'), 121: ('F22', 192, 'key'), 122: ('F23', 193, 'key'),
    123: ('F24', 194, 'key'), 124: ('Screen Brightness (-)', 224, 'key'),
    125: ('Screen Brightness (+)', 225, 'key'), 126: ('PrtSc', 99, 'key'), 127: ('Pause', 119, 'key'),
}


def user_dev(name, bus):
    """struct uinput_user_dev: name, id, ff_effects_max and four absolute axis tables."""
    return struct.pack("80sHHHHI", name.encode()[:79], bus, VENDOR, PRODUCT, 1, 0) + bytes(4 * 64 * 4)


class Device:
    """One virtual device; opener and ioctl can be replaced in tests."""

    def __init__(self, name, bus, evbits, keybits, relbits=(), opener=None, ioctl=None):
        self.name, self.bus = name, bus
        self.evbits, self.keybits, self.relbits = evbits, keybits, relbits
        self.opener = opener or (lambda: os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK))
        self.ioctl = ioctl or fcntl.ioctl
        self.fd = None
        self.error = ""

    def open(self):
        if self.fd is not None:
            return True
        try:
            fd = self.opener()
            for bit in self.evbits:
                self.ioctl(fd, UI_SET_EVBIT, bit)
            for bit in self.keybits:
                self.ioctl(fd, UI_SET_KEYBIT, bit)
            for bit in self.relbits:
                self.ioctl(fd, UI_SET_RELBIT, bit)
            os.write(fd, user_dev(self.name, self.bus))
            self.ioctl(fd, UI_DEV_CREATE, 0)
        except OSError as e:
            self.error = "%s: %s" % (UINPUT, e)
            return False
        self.fd, self.error = fd, ""
        return True

    def send(self, events):
        if not self.open():
            return False
        try:
            for kind, code, value in events:
                os.write(self.fd, EVENT.pack(0, 0, kind, code, value))
            return True
        except OSError as e:
            self.error = str(e)
            return False

    def close(self):
        if self.fd is not None:
            try:
                self.ioctl(self.fd, UI_DEV_DESTROY, 0)
            except OSError:
                pass
            os.close(self.fd)
            self.fd = None


def _press(code, value):
    return [(EV_KEY, code, value), (EV_SYN, 0, 0)]


class Inputs:
    """InputControlKeyboard, -KeyboardHold, -Mouse, -MouseHold, -Move and -KeyboardText."""

    def __init__(self, opener=None, ioctl=None, sleep=time.sleep):
        self.keyboard = Device("Quartercore Virtual Keyboard", 0x06, (EV_KEY, EV_SYN), range(255),
                               opener=opener, ioctl=ioctl)
        self.mouse = Device("Quartercore Virtual Mouse", 0x03, (EV_KEY, EV_REL, EV_SYN),
                            BUTTONS + (KEY_LEFTCTRL, KEY_RIGHTCTRL, KEY_LEFTALT, KEY_LEFTSHIFT),
                            (REL_X, REL_Y, REL_WHEEL, REL_HWHEEL), opener=opener, ioctl=ioctl)
        self.sleep = sleep
        self.lock = threading.Lock()

    @property
    def error(self):
        return self.keyboard.error or self.mouse.error

    @staticmethod
    def code(action):
        entry = ACTIONS.get(int(action))
        return entry[1] if entry and entry[1] else None

    def key(self, action, hold=False):
        """Press and release (after 20 ms), or only press when hold."""
        code = self.code(action)
        if code is None:
            return
        with self.lock:
            self.keyboard.send(_press(code, 1))
            if not hold:
                self.sleep(0.02)
                self.keyboard.send(_press(code, 0))

    def key_hold(self, action, press):
        code = self.code(action)
        if code is not None:
            with self.lock:
                self.keyboard.send(_press(code, 1 if press else 0))

    def click(self, action):
        code = self.code(action)
        if code is not None:
            with self.lock:
                self.mouse.send(_press(code, 1) + _press(code, 0))

    def click_hold(self, action, press):
        code = self.code(action)
        if code is not None:
            with self.lock:
                self.mouse.send(_press(code, 1 if press else 0))

    def move(self, x, y):
        events = ([(EV_REL, REL_X, int(x))] if x else []) + ([(EV_REL, REL_Y, int(y))] if y else [])
        with self.lock:
            self.mouse.send(events + [(EV_SYN, 0, 0)])

    def text(self, text):
        for char in text or "":
            base = SHIFTED.get(char, char)
            code = CHAR_KEYS.get(base)
            if code is None:
                continue
            with self.lock:
                if base != char:
                    self.keyboard.send(_press(KEY_LEFTSHIFT, 1))
                self.keyboard.send(_press(code, 1))
                self.sleep(0.02)
                self.keyboard.send(_press(code, 0))
                if base != char:
                    self.keyboard.send(_press(KEY_LEFTSHIFT, 0))
            self.sleep(0.04)

    def close(self):
        self.keyboard.close()
        self.mouse.close()


_shared = None


def shared():
    """One virtual keyboard and mouse for all devices, made when first used."""
    global _shared
    if _shared is None:
        _shared = Inputs()
    return _shared


def close_shared():
    if _shared is not None:
        _shared.close()
