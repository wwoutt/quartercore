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

    def test_scroll_and_zoom(self):
        self.inputs.scroll(True)
        self.inputs.scroll_horizontal(False)
        self.assertEqual(self.fake.events(0), [(2, 8, 1), (0, 0, 0), (2, 6, -1), (0, 0, 0)])
        self.inputs.zoom(False)
        self.assertEqual(self.fake.events(0), [(1, 29, 1), (0, 0, 0), (2, 8, -1), (0, 0, 0), (1, 29, 0), (0, 0, 0)])

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
            (Path(tmp) / "mmm.json").write_text(json.dumps({"id": 3, "name": "mmm", "actions": {
                "0": {"actionType": 3, "actionCommand": 30, "actionHold": True},
                "1": {"actionType": 5, "actionDelay": 250},
                "2": {"actionType": 6, "actionText": "hi", "actionRepeat": 2, "actionRepeatDelay": 100},
                "3": {"actionType": 9, "actionCommand": 91},
                "10": {"actionType": 20, "mousePositionX": 4, "mousePositionY": 0}}}))
            fake, sleeps = RecordingInputs(), []
            player = macros.Player(fake, macros.MacroStore(tmp, Path(tmp) / "none"), sleeps.append)
            self.assertEqual(player.play(3), "")
            self.assertEqual(player.play(4), "Invalid macro profile")
        self.assertEqual(fake.calls, [("key", 30, True), ("text", "hi"), ("text", "hi"), ("click", 91),
                                      ("move", 4, 0)])
        self.assertEqual(sleeps, [0.25, 0.1])
        player.release()
        self.assertEqual(fake.calls[-1], ("key_hold", 30, False))

    def test_keyboard_repeats_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "rep.json").write_text(json.dumps({"id": 1, "name": "rep", "actions": {
                "0": {"actionType": 9, "actionCommand": 91, "actionRepeat": 2},
                "1": {"actionType": 9, "actionCommand": 92, "actionHold": True}}}))
            fake = RecordingInputs()
            player = macros.Player(fake, macros.MacroStore(tmp, Path(tmp) / "none"), lambda s: None)
            player.play(1, keyboard=True)
        self.assertEqual(fake.calls, [("click", 91), ("click", 91), ("click_hold", 92, True)])
        player.release()
        self.assertEqual(fake.calls[-1], ("click_hold", 92, False))



class MacroStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "olh").mkdir()
        (root / "olh" / "hello.json").write_text(json.dumps({"id": 4, "name": "Hello", "repeat": 0, "repeatDelay": 0,
                                                            "actions": {"0": macros.step(3, 30)}}))
        (root / "olh" / "broken.json").write_text("{")
        self.store = macros.MacroStore(root / "own", root / "olh")

    def tearDown(self):
        self.tmp.cleanup()

    def test_takes_over_openlinkhubs_macros_once(self):
        self.assertEqual(list(self.store.all()), ["4"])
        self.assertTrue((Path(self.tmp.name) / "own" / "hello.json").exists())
        (Path(self.tmp.name) / "olh" / "other.json").write_text(json.dumps({"id": 9, "name": "Other", "actions": {}}))
        self.assertEqual(list(macros.MacroStore(Path(self.tmp.name) / "own", Path(self.tmp.name) / "olh").all()), ["4"])

    def test_make_change_and_delete(self):
        s = self.store
        self.assertEqual(s.handle("PUT", "/api/macro/new", {"macroName": "ab"}), "A macro name needs at least 3 characters")
        self.assertEqual(s.handle("PUT", "/api/macro/new", {"macroName": "hello"}), "Unable to create macro profile")
        self.assertEqual(s.handle("PUT", "/api/macro/new", {"macroName": "Copy"}), "")
        self.assertEqual(s.get(5)["name"], "Copy")
        step = {"macroId": 5, "macroType": 3, "macroValue": 30, "macroDelay": 0, "macroText": "",
                "mousePositionX": 0, "mousePositionY": 0, "mousePositionAbsolute": False}
        self.assertEqual(s.handle("POST", "/api/macro/newValue", step), "")
        self.assertEqual(s.handle("POST", "/api/macro/newValue", dict(step, macroType=5, macroDelay=100)), "")
        self.assertEqual(s.handle("POST", "/api/macro/newValue", dict(step, macroValue=31)), "")
        self.assertEqual(s.handle("DELETE", "/api/macro/value", {"macroId": 5, "macroIndex": 1}), "")
        # A new step after the gap gets number 3, it doesn't replace step 2 (upstream would)
        self.assertEqual(s.handle("POST", "/api/macro/newValue", dict(step, macroValue=32)), "")
        self.assertEqual({k: a["actionCommand"] for k, a in s.get(5)["actions"].items()}, {"0": 30, "2": 31, "3": 32})
        self.assertEqual(s.handle("POST", "/api/macro/newValue", dict(step, macroType=2)), "Invalid macro type")
        self.assertEqual(s.handle("POST", "/api/macro/newValue", dict(step, macroType=6)), "Invalid macro text")
        hold = {"macroId": 5, "macroIndex": 0, "pressAndHold": True, "actionRepeatValue": 0, "actionRepeatDelay": 0,
                "mousePositionX": 0, "mousePositionY": 0}
        self.assertEqual(s.handle("POST", "/api/macro/updateValue", hold), "")
        self.assertEqual(s.handle("POST", "/api/macro/updateValue", dict(hold, macroIndex=2)), "")
        self.assertEqual(s.handle("POST", "/api/macro/updateValue", dict(hold, macroIndex=3)),
                         "Not every step of a macro can be held")
        self.assertEqual(s.handle("POST", "/api/macro/updateValue", dict(hold, actionRepeatValue=101)),
                         "Invalid macro repeat value")
        self.assertEqual(s.handle("POST", "/api/macro/updateSettings", {"macroId": 5, "macroRepeat": 3,
                                                                       "macroRepeatDelay": 50}), "")
        saved = json.loads((Path(self.tmp.name) / "own" / "copy.json").read_text())
        self.assertEqual((saved["repeat"], saved["actions"]["0"]["actionHold"]), (3, True))
        self.assertEqual(s.handle("DELETE", "/api/macro/profile", {"macroId": 5}), "")
        self.assertFalse((Path(self.tmp.name) / "own" / "copy.json").exists())
        self.assertEqual(s.handle("DELETE", "/api/macro/profile", {"macroId": 5}), "Invalid macro selected")
        self.assertIsNone(s.handle("POST", "/api/macro/other", {"macroId": 4}))
        self.assertTrue(s.all()["4"]["gapsAllowed"])


class ServerMacroTest(unittest.TestCase):
    def test_macros_through_the_server(self):
        import threading
        import urllib.request
        from quartercore.core.server import Core, serve
        with tempfile.TemporaryDirectory() as tmp:
            store = macros.MacroStore(Path(tmp) / "own", Path(tmp) / "none")
            core = Core("http://127.0.0.1:1", lambda: [], log=lambda text: None, macros=store)
            server = serve(core, 0)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = "http://127.0.0.1:%d" % server.server_port

            def call(method, path, body=None):
                request = urllib.request.Request(url + path, method=method,
                                                 data=json.dumps(body).encode() if body is not None else None)
                with urllib.request.urlopen(request, timeout=5) as reply:
                    return json.loads(reply.read())
            try:
                self.assertEqual(call("PUT", "/api/macro/new", {"macroName": "Hello"})["status"], 1)
                self.assertEqual(call("GET", "/api/macro/")["data"]["1"]["name"], "Hello")
                self.assertEqual(call("GET", "/api/macro/1")["data"]["id"], 1)
                self.assertEqual(call("GET", "/api/macro/keyInfo/6")["data"], "Play")
                answer = call("POST", "/api/macro/newValue", {"macroId": 1, "macroType": 2})
                self.assertEqual((answer["status"], answer["message"]), (0, "Invalid macro type"))
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
