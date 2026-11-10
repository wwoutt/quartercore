# Macros: stored by quartercore-core and played on the virtual keyboard and mouse
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/macro/macro.go, the macro
# requests of src/server/requests and the macro part of TriggerKeyAssignment in
# the device drivers). Macros are files <name>.json in
# ~/.config/Quartercore/core/macros, like OpenLinkHub's database/macros; the
# first time, OpenLinkHub's macros are copied. Unlike upstream, a new step gets
# the next free number, so it never replaces a step after a deleted one.

import json
import os
import re
import threading
import time
from pathlib import Path

OPENLINKHUB = Path("/var/opt/OpenLinkHub/database/macros")
KEYBOARD, DELAY, TEXT, MOUSE, MOVE = (1, 3), 5, 6, 9, 20
NAME = re.compile(r"^[a-zA-Z0-9]+$")


def default_folder():
    home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return home / "Quartercore" / "core" / "macros"


def read(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("id"), int) else None


def step(kind=0, command=0, delay=0, text="", x=0, y=0, absolute=False):
    return {"actionType": kind, "actionCommand": command, "actionDelay": delay, "actionHold": False,
            "actionRepeat": 0, "actionRepeatDelay": 0, "actionText": text, "mousePositionX": x,
            "mousePositionY": y, "mousePositionAbsolute": absolute}


class MacroStore:
    """The macros by id; every change is saved right away."""

    def __init__(self, folder=None, openlinkhub=OPENLINKHUB):
        self.folder = Path(folder or default_folder())
        self.openlinkhub = Path(openlinkhub)
        self.lock = threading.RLock()
        self.macros = None

    def _ensure(self):
        if self.macros is not None:
            return
        first = not self.folder.exists()
        self.macros = {}
        for folder in ([self.openlinkhub] if first else []) + [self.folder]:
            try:
                files = sorted(folder.glob("*.json"))
            except OSError:
                continue
            for path in files:
                macro = read(path)
                if macro is not None:
                    macro.setdefault("actions", {})
                    self.macros[macro["id"]] = macro
        if first:
            self.folder.mkdir(parents=True, exist_ok=True)
            for macro in self.macros.values():
                self._write(macro)

    def _path(self, macro):
        return self.folder / ("%s.json" % str(macro["name"]).lower())

    def _write(self, macro):
        path = self._path(macro)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(macro, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def all(self):
        with self.lock:
            self._ensure()
            return {str(k): dict(v, gapsAllowed=True) for k, v in sorted(self.macros.items())}

    def get(self, macro_id):
        with self.lock:
            self._ensure()
            try:
                return self.macros.get(int(macro_id))
            except (TypeError, ValueError):
                return None

    def handle(self, method, path, body):
        """The macro requests of keyboard.py (OpenLinkHub's macros.js); None when not one of them."""
        def number(key, default=0):
            try:
                return int(body.get(key, default) or 0)
            except (TypeError, ValueError):
                return None
        with self.lock:
            self._ensure()
            if method == "PUT" and path == "/api/macro/new":
                name = str(body.get("macroName") or "")
                if len(name) < 3:
                    return "A macro name needs at least 3 characters"
                if not NAME.match(name):
                    return "Use only letters and digits"
                if any(str(m["name"]).lower() == name.lower() for m in self.macros.values()):
                    return "Unable to create macro profile"
                new_id = max(self.macros, default=0) + 1
                self.macros[new_id] = {"id": new_id, "name": name, "repeat": 0, "repeatDelay": 0, "actions": {}}
                self._write(self.macros[new_id])
                return ""
            macro = self.macros.get(number("macroId", -1))
            ours = {("DELETE", "/api/macro/profile"), ("DELETE", "/api/macro/value"),
                    ("POST", "/api/macro/updateSettings"), ("POST", "/api/macro/updateValue"),
                    ("POST", "/api/macro/newValue")}
            if (method, path) not in ours:
                return None
            if macro is None:
                return "Invalid macro selected"
            actions = macro["actions"]
            index = str(number("macroIndex", -1))
            if path == "/api/macro/profile":
                del self.macros[macro["id"]]
                try:
                    self._path(macro).unlink()
                except OSError:
                    pass
                return ""
            if path == "/api/macro/value":
                if actions.pop(index, None) is None:
                    return "Unable to delete macro profile value"
            elif path == "/api/macro/updateSettings":
                repeat, delay = number("macroRepeat"), number("macroRepeatDelay")
                if repeat is None or repeat < -1:
                    return "Invalid macro loop value"
                if delay is None or delay < 0:
                    return "Invalid macro delay value"
                macro["repeat"], macro["repeatDelay"] = repeat, delay
            elif path == "/api/macro/updateValue":
                action = actions.get(index)
                if action is None:
                    return "Unable to update macro profile value"
                repeat, delay = number("actionRepeatValue"), number("actionRepeatDelay")
                x, y = number("mousePositionX"), number("mousePositionY")
                if repeat is None or not 0 <= repeat <= 100:
                    return "Invalid macro repeat value"
                if delay is None or not 0 <= delay <= 10000:
                    return "Invalid macro repeat delay"
                if x is None or y is None or x < 0 or y < 0:
                    return "Invalid mouse position"
                hold = bool(body.get("pressAndHold"))
                if hold and not self._hold_allowed(macro, index):
                    return "Not every step of a macro can be held"
                action.update({"actionHold": hold, "actionRepeat": repeat, "actionRepeatDelay": delay,
                               "mousePositionX": x, "mousePositionY": y,
                               "mousePositionAbsolute": bool(body.get("mousePositionAbsolute"))})
            elif path == "/api/macro/newValue":
                kind, value, delay = number("macroType"), number("macroValue"), number("macroDelay")
                text = str(body.get("macroText") or "")
                if kind is None or not 3 <= kind <= 20:
                    return "Invalid macro type"
                if kind == 3 and not value:
                    return "Invalid macro value"
                if kind == 5 and (delay or 0) < 1:
                    return "Invalid macro delay"
                if kind == 6 and not text:
                    return "Invalid macro text"
                x = y = 0
                absolute = False
                if kind == 20:
                    x, y = number("mousePositionX"), number("mousePositionY")
                    if x is None or y is None or x < 0 or y < 0:
                        return "Invalid mouse position"
                    absolute = bool(body.get("mousePositionAbsolute"))
                new_index = max((int(k) for k in actions), default=-1) + 1
                actions[str(new_index)] = step(kind, value or 0, delay or 0, text, x, y, absolute)
            self._write(macro)
            return ""

    @staticmethod
    def _hold_allowed(macro, index):
        """validatePressAndHold: at least one step that isn't a delay stays without hold."""
        count = length = 0
        for i, a in macro["actions"].items():
            if a.get("actionType") == DELAY:
                continue
            length += 1
            if i == index or a.get("actionHold"):
                count += 1
        return count != length


_store = None


def shared_store():
    global _store
    if _store is None:
        _store = MacroStore()
    return _store


class Player:
    """Plays macros; held keys are remembered and released when the button is let go."""

    def __init__(self, inputs, store=None, sleep=time.sleep):
        self.inputs = inputs
        self.store = store
        self.sleep = sleep
        self.lock = threading.Lock()
        self.held = {}
        self.stop_repeat = None

    def play(self, macro_id, keyboard=False):
        """Plays a macro. keyboard=True repeats keys and mouse buttons like the keyboard drivers do."""
        macro = (self.store or shared_store()).get(macro_id)
        if macro is None:
            return "Invalid macro profile"
        actions = dict(macro.get("actions") or {})
        for index in sorted(actions, key=int):
            a = actions[index]
            kind, command = int(a.get("actionType") or 0), int(a.get("actionCommand") or 0)
            hold = bool(a.get("actionHold"))
            repeat, repeat_delay = int(a.get("actionRepeat") or 0), int(a.get("actionRepeatDelay") or 0)
            if hold:
                with self.lock:
                    self.held[int(index)] = (command, kind)
            if kind in KEYBOARD:
                if keyboard and repeat > 0 and not hold:
                    self._repeat(lambda c=command: self.inputs.key(c), repeat, repeat_delay)
                else:
                    self.inputs.key(command, hold)
            elif kind == MOUSE:
                if keyboard and repeat > 0 and not hold:
                    for n in range(repeat):
                        self.inputs.click(command)
                        if repeat_delay > 0 and repeat > 1:
                            self.sleep(repeat_delay / 1000)
                elif keyboard and hold and repeat == 0:
                    self.inputs.click_hold(command, True)
                else:
                    self.inputs.click(command)
            elif kind == DELAY:
                if int(a.get("actionDelay") or 0) > 0:
                    self.sleep(int(a["actionDelay"]) / 1000)
            elif kind == TEXT:
                for n in range(max(1, repeat)):
                    self.inputs.text(a.get("actionText") or "")
                    if repeat > 1 and repeat_delay > 0 and n < repeat - 1:
                        self.sleep(repeat_delay / 1000)
            elif kind == MOVE:
                self._move(a, repeat, repeat_delay, hold)
        return ""

    def _repeat(self, action, repeat, repeat_delay):
        """Repeats an action in the background; a new repeat stops the previous one."""
        if self.stop_repeat is not None:
            self.stop_repeat.set()
        stop = self.stop_repeat = threading.Event()

        def run():
            for _ in range(repeat):
                if stop.is_set():
                    return
                action()
                if repeat_delay > 0 and repeat > 1:
                    self.sleep(repeat_delay / 1000)
        threading.Thread(target=run, daemon=True).start()

    def _move(self, a, repeat, repeat_delay, hold):
        if a.get("mousePositionAbsolute"):
            return              # needs a virtual absolute mouse; not ported yet
        x, y = int(a.get("mousePositionX") or 0), int(a.get("mousePositionY") or 0)
        if repeat > 0 and not hold:
            self._repeat(lambda: self.inputs.move(x, y), repeat, repeat_delay)
        else:
            self.inputs.move(x, y)

    def release(self):
        """releaseMacroTracker: lets go of the keys a macro held down."""
        with self.lock:
            held, self.held = self.held, {}
        for index in sorted(held):
            command, kind = held[index]
            if kind == MOUSE:
                self.inputs.click_hold(command, False)
            else:
                self.inputs.key_hold(command, False)
