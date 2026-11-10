# Tests for the virtual keyboard and mouse (uinput) and macros of quartercore-core
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests
# /dev/uinput is replaced by a pipe; no input reaches the desktop.

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quartercore.core import inputs, macros  # noqa: E402


class FakeUinput:
    def __init__(self):
        self.ioctls = []
        self.pipes = []
        self.header_read = set()

    def open(self):
        r, w = os.pipe()
        os.set_blocking(r, False)
        self.pipes.append(r)
        return w

    def ioctl(self, fd, request, value):
        self.ioctls.append((fd, request, value))

    def events(self, n):
        """(type, code, value) written to device n after its uinput_user_dev."""
        data = b""
        try:
            while True:
                data += os.read(self.pipes[n], 65536)
        except BlockingIOError:
            pass
        if n not in self.header_read:              # the uinput_user_dev comes first
            self.header_read.add(n)
            data = data[1116:]
        return [inputs.EVENT.unpack_from(data, i)[2:] for i in range(0, len(data), inputs.EVENT.size)]


class RecordingInputs:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name,) + args)


class InputsTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeUinput()
        self.sleeps = []
        self.inputs = inputs.Inputs(self.fake.open, self.fake.ioctl, self.sleeps.append)

    def tearDown(self):
        self.inputs.close()
        for fd in self.fake.pipes:
            os.close(fd)

    def test_table(self):
        self.assertEqual(inputs.ACTIONS[6], ("Play", 164, "key"))
        self.assertEqual(inputs.ACTIONS[91], ("(Mouse) Left Click", 272, "mouse"))
        self.assertEqual(inputs.Inputs.code(0), None)
        self.assertEqual(len(inputs.user_dev("x", 6)), 1116)

    def test_key_press_and_release(self):
        self.inputs.key(6)
        requests = [r for _, r, _ in self.fake.ioctls]
        self.assertIn(inputs.UI_DEV_CREATE, requests)
        self.assertEqual(requests.count(inputs.UI_SET_KEYBIT), 255)
        self.assertEqual(self.fake.events(0), [(1, 164, 1), (0, 0, 0), (1, 164, 0), (0, 0, 0)])
        self.assertEqual(self.sleeps, [0.02])
        self.inputs.key_hold(6, True)
        self.assertEqual(self.fake.events(0), [(1, 164, 1), (0, 0, 0)])

    def test_mouse(self):
        self.inputs.click(92)
        self.assertEqual(self.fake.events(0), [(1, 273, 1), (0, 0, 0), (1, 273, 0), (0, 0, 0)])
        self.inputs.move(5, -3)
        self.assertEqual(self.fake.events(0), [(2, 0, 5), (2, 1, -3), (0, 0, 0)])

    def test_text_with_shift(self):
        self.inputs.text("a!")
        keys = [(c, v) for t, c, v in self.fake.events(0) if t == 1]
        self.assertEqual(keys, [(30, 1), (30, 0), (42, 1), (2, 1), (2, 0), (42, 0)])

    def test_no_access(self):
        def refuse():
            raise PermissionError(13, "Permission denied")
        quiet = inputs.Inputs(refuse, self.fake.ioctl, lambda s: None)
        quiet.key(6)
        self.assertIn("Permission denied", quiet.error)


class MacroTest(unittest.TestCase):
    def test_play_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "3.json").write_text(json.dumps({"id": 3, "name": "m", "actions": {
                "0": {"actionType": 3, "actionCommand": 30, "actionHold": True},
                "1": {"actionType": 5, "actionDelay": 250},
                "2": {"actionType": 6, "actionText": "hi", "actionRepeat": 2, "actionRepeatDelay": 100},
                "3": {"actionType": 9, "actionCommand": 91},
                "10": {"actionType": 20, "mousePositionX": 4, "mousePositionY": 0}}}))
            fake, sleeps = RecordingInputs(), []
            player = macros.Player(fake, tmp, sleeps.append)
            self.assertEqual(player.play(3), "")
            self.assertEqual(player.play(4), "Invalid macro profile")
        self.assertEqual(fake.calls, [("key", 30, True), ("text", "hi"), ("text", "hi"), ("click", 91),
                                      ("move", 4, 0)])
        self.assertEqual(sleeps, [0.25, 0.1])
        player.release()
        self.assertEqual(fake.calls[-1], ("key_hold", 30, False))


if __name__ == "__main__":
    unittest.main()
