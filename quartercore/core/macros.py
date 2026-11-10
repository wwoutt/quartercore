# Macros: read OpenLinkHub's macro files and play them on the virtual keyboard and mouse
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/macro/macro.go and the macro
# part of TriggerKeyAssignment in the device drivers). Until OpenLinkHub is
# removed (step G) the macros are still made in OpenLinkHub, so they are read
# from its database/macros/<id>.json every time one is played.

import json
import threading
import time
from pathlib import Path

FOLDER = Path("/var/opt/OpenLinkHub/database/macros")
KEYBOARD, DELAY, TEXT, MOUSE, MOVE = (1, 3), 5, 6, 9, 20


def load(macro_id, folder=FOLDER):
    try:
        data = json.loads((Path(folder) / ("%d.json" % int(macro_id))).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


class Player:
    """Plays macros; held keys are remembered and released when the button is let go."""

    def __init__(self, inputs, folder=FOLDER, sleep=time.sleep):
        self.inputs = inputs
        self.folder = folder
        self.sleep = sleep
        self.lock = threading.Lock()
        self.held = {}
        self.stop_repeat = None

    def play(self, macro_id):
        macro = load(macro_id, self.folder)
        if macro is None:
            return "Invalid macro profile"
        actions = macro.get("actions") or {}
        for index in sorted(actions, key=int):
            a = actions[index]
            kind, command = int(a.get("actionType") or 0), int(a.get("actionCommand") or 0)
            hold = bool(a.get("actionHold"))
            repeat, repeat_delay = int(a.get("actionRepeat") or 0), int(a.get("actionRepeatDelay") or 0)
            if hold:
                with self.lock:
                    self.held[int(index)] = command
            if kind in KEYBOARD:
                self.inputs.key(command, hold)
            elif kind == MOUSE:
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

    def _move(self, a, repeat, repeat_delay, hold):
        if a.get("mousePositionAbsolute"):
            return              # needs a virtual absolute mouse; not ported yet
        x, y = int(a.get("mousePositionX") or 0), int(a.get("mousePositionY") or 0)
        if repeat > 0 and not hold:
            if self.stop_repeat is not None:
                self.stop_repeat.set()
            stop = self.stop_repeat = threading.Event()

            def run():
                for _ in range(repeat):
                    if stop.is_set():
                        return
                    self.inputs.move(x, y)
                    if repeat_delay > 0 and repeat > 1:
                        self.sleep(repeat_delay / 1000)
            threading.Thread(target=run, daemon=True).start()
        else:
            self.inputs.move(x, y)

    def release(self):
        """releaseMacroTracker: lets go of the keys a macro held down."""
        with self.lock:
            held, self.held = self.held, {}
        for index in sorted(held):
            self.inputs.key_hold(held[index], False)
