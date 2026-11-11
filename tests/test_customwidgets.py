# Tests for the own HTML widgets: library, widget server, store and layout
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests
# Everything in temporary folders; the store uses a fake catalog on localhost.

import hashlib
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quartercore import edgelayout  # noqa: E402
from quartercore.customwidgets import library as lib  # noqa: E402
from quartercore.customwidgets.server import WidgetServer  # noqa: E402
from quartercore.customwidgets.store import Store, StoreError  # noqa: E402

HTML = "<div id='v'></div><script>function onData(d){document.getElementById('v').textContent=d.value}</script>"


def write_widget(folder, widget_id, manifest, files=None):
    path = Path(folder) / widget_id
    path.mkdir(parents=True)
    (path / "widget.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "widget.html").write_text(HTML, encoding="utf-8")
    for name, text in (files or {}).items():
        (path / name).write_text(text, encoding="utf-8")
    return path


class FakeWeb:
    """Serves a dict of path -> bytes on localhost, and records the request headers."""

    def __init__(self, files):
        self.files = files
        self.headers = []
        web = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                web.headers.append(dict(self.headers))
                body = web.files.get(self.path.split("?")[0])
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.library = lib.Library(Path(self.tmp.name) / "widgets")
        self.library.dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_and_public_manifest(self):
        write_widget(self.library.dir, "clock", {"name": "Clock", "size": {"w": 30, "h": 2}, "refresh": 0})
        write_widget(self.library.dir, "Bad Name", {"name": "x"})
        (self.library.dir / "broken").mkdir()
        (self.library.dir / "broken" / "widget.json").write_text("{", encoding="utf-8")
        widgets = self.library.list()
        self.assertEqual([w["id"] for w in widgets], ["clock"])
        self.assertEqual(widgets[0]["size"], {"w": 24, "h": 2})
        self.assertEqual(widgets[0]["refresh"], 60)
        self.assertEqual(widgets[0]["source"], "none")
        self.assertFalse(widgets[0]["action"])

    def test_settings_keep_secrets_private(self):
        write_widget(self.library.dir, "ha", {"settings": [
            {"name": "HA_URL", "type": "url", "default": "http://127.0.0.1:8123"},
            {"name": "HA_TOKEN", "type": "secret", "default": "leak"},
            {"name": "bad name"}]})
        self.assertEqual(self.library.public_settings("ha"),
                         {"HA_URL": {"value": "http://127.0.0.1:8123"}, "HA_TOKEN": {"set": False}})
        self.library.save_settings("ha", {"HA_URL": " http://ha:8123 ", "HA_TOKEN": "secret", "OTHER": "x"})
        self.assertEqual(self.library.load_settings("ha"), {"HA_URL": "http://ha:8123", "HA_TOKEN": "secret"})
        self.assertEqual(self.library.public_settings("ha")["HA_TOKEN"], {"set": True})
        self.assertNotIn("secret", json.dumps(self.library.public_settings("ha")))
        # An empty secret keeps the stored one
        self.library.save_settings("ha", {"HA_TOKEN": ""})
        self.assertEqual(self.library.load_settings("ha")["HA_TOKEN"], "secret")
        with self.assertRaises(ValueError):
            self.library.save_settings("ha", {"HA_URL": "ftp://x"})
        mode = stat.S_IMODE(os.stat(self.library.settings_file("ha")).st_mode)
        self.assertEqual(mode, 0o600)

    def test_script_source_and_action(self):
        write_widget(self.library.dir, "echo", {
            "refresh": 60, "source": {"type": "script"}, "action": {"type": "script"},
            "settings": [{"name": "WORD", "type": "text"}]}, {
            "data.py": "import json, os\n"
                       "print(json.dumps({'value': json.load(open(os.environ['OLH_SETTINGS_FILE']))['WORD']}))\n",
            "action.py": "import json, sys\nprint(json.dumps({'got': json.load(sys.stdin)}))\n"})
        self.library.save_settings("echo", {"WORD": "hallo"})
        data = self.library.data("echo")
        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["data"], {"value": "hallo"})
        self.assertEqual(self.library.action("echo", {"press": 1}), {"ok": True, "data": {"got": {"press": 1}},
                                                                    "error": None})
        self.assertNotIn("echo", self.library.cache)    # refreshed after an action

    def test_failing_script_and_missing_action(self):
        write_widget(self.library.dir, "fail", {"source": {"type": "script"}},
                     {"data.py": "import sys\nprint('broken', file=sys.stderr)\nsys.exit(3)\n"})
        data = self.library.data("fail")
        self.assertFalse(data["ok"])
        self.assertIn("broken", data["error"])
        self.assertFalse(self.library.action("fail", {})["ok"])

    def test_url_source_fills_settings(self):
        web = FakeWeb({"/value": b'{"value": 42}'})
        self.addCleanup(web.stop)
        write_widget(self.library.dir, "web", {"settings": [{"name": "KEY", "type": "secret"}], "source": {
            "type": "url", "url": web.url + "/value", "headers": {"Authorization": "Bearer ${KEY}"}}})
        self.library.save_settings("web", {"KEY": "abc"})
        self.assertEqual(self.library.data("web")["data"], {"value": 42})
        self.assertEqual(web.headers[-1].get("Authorization"), "Bearer abc")

    def test_import_from_openlinkhub_once(self):
        old = Path(self.tmp.name) / "openlinkhub-widgets"
        write_widget(old, "ha", {"name": "Home Assistant"}, {".olh-store.json": '{"kind": "catalog", "ref": "ha"}'})
        (old / "ha" / "__pycache__").mkdir()
        lib.write_private(old / ".settings" / "ha.json", {"HA_TOKEN": "t"})
        lib.write_private(old / "secrets.json", {"GITHUB_TOKEN": "g"})
        library = lib.Library(Path(self.tmp.name) / "new")
        self.assertEqual(library.import_openlinkhub(old), ["ha"])
        self.assertEqual(library.record("ha"), {"kind": "catalog", "ref": "ha"})
        self.assertFalse((library.dir / "ha" / "__pycache__").exists())
        self.assertEqual(library.load_settings("ha"), {"HA_TOKEN": "t"})
        self.assertEqual(library.secrets()["GITHUB_TOKEN"], "g")
        # Not again once Quartercore has its own folder
        self.assertEqual(library.import_openlinkhub(old), [])


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.library = lib.Library(Path(self.tmp.name))
        write_widget(self.library.dir, "echo", {"name": "Echo", "action": {"type": "script"}},
                     {"action.py": "import json, sys\nprint(json.dumps(json.load(sys.stdin)))\n"})
        self.server = WidgetServer(self.library).start()

    def tearDown(self):
        self.server.stop()
        self.tmp.cleanup()

    def request(self, path, token=None, host=None, body=None):
        headers = {}
        if token:
            headers["X-Quartercore-Token"] = token
        if host:
            headers["Host"] = host
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.server.base_url.rstrip("/") + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as reply:
                return reply.status, reply.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read()

    def test_frame_needs_the_token(self):
        url = self.server.frame_url("echo")
        status, page = self.request(url[len(self.server.base_url) - 1:])
        self.assertEqual(status, 200)
        self.assertIn(b'"id": "echo"', page)
        self.assertIn(b'sandbox="allow-scripts"', page)
        self.assertEqual(self.request("/frame/echo?token=wrong")[0], 403)

    def test_api_needs_token_and_host(self):
        self.assertEqual(self.request("/api/widgets/echo/html")[0], 403)
        self.assertEqual(self.request("/api/widgets/echo/html", self.server.token, "evil.example:80")[0], 403)
        status, body = self.request("/api/widgets/echo/html", self.server.token)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["html"], HTML)
        self.assertEqual(self.request("/api/widgets/nope/data", self.server.token)[0], 404)

    def test_action(self):
        status, body = self.request("/api/widgets/echo/action", self.server.token, body={"data": {"a": 1}})
        self.assertEqual(json.loads(body), {"ok": True, "data": {"a": 1}, "error": None})
        self.assertEqual(self.request("/api/widgets/echo/action", body={"data": {}})[0], 403)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "widgets"
        files = {"widget.json": json.dumps({"name": "Clock", "version": "1.0.0"}).encode(),
                 "widget.html": HTML.encode()}
        code = {"widget.json": json.dumps({"name": "Code", "source": {"type": "script"}}).encode(),
                "widget.html": HTML.encode(), "data.py": b"print('{}')\n"}
        index = {"version": 1, "widgets": [
            {"id": "clock", "name": "Clock", "path": "widgets/clock", "runsCode": False,
             "files": {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}},
            {"id": "code", "name": "Code", "path": "widgets/code", "runsCode": True,
             "files": {n: hashlib.sha256(d).hexdigest() for n, d in code.items()}},
            {"id": "bad", "name": "Bad", "path": "widgets/bad", "files": {"widget.json": "0" * 64,
                                                                         "widget.html": "0" * 64}}]}
        served = {"/index.json": json.dumps(index).encode()}
        served.update({"/widgets/clock/" + n: d for n, d in files.items()})
        served.update({"/widgets/code/" + n: d for n, d in code.items()})
        served.update({"/widgets/bad/" + n: d for n, d in files.items()})
        self.web = FakeWeb(served)
        os.environ["QUARTERCORE_STORE_CATALOG"] = self.web.url + "/"
        self.changed = []
        self.store = Store(str(self.dir), str(self.dir / "secrets.json"), self.changed.append)

    def tearDown(self):
        os.environ.pop("QUARTERCORE_STORE_CATALOG", None)
        self.web.stop()
        self.tmp.cleanup()

    def test_install_update_and_remove(self):
        entries = {e["id"]: e for e in self.store.list("catalog", "")}
        self.assertFalse(entries["clock"]["installed"])
        self.store.install("catalog", "clock", None, False)
        self.assertTrue((self.dir / "clock" / "widget.html").is_file())
        self.assertEqual(lib.Library(self.dir).record("clock")["kind"], "catalog")
        self.store.cache.clear()
        self.assertTrue({e["id"]: e for e in self.store.list("catalog", "")}["clock"]["installed"])
        lib.write_private(self.dir / ".settings" / "clock.json", {"TOKEN": "x"})
        self.store.uninstall("clock")
        self.assertFalse((self.dir / "clock").exists())
        self.assertFalse((self.dir / ".settings" / "clock.json").exists())
        self.assertEqual(self.changed, ["clock", "clock"])

    def test_code_needs_confirmation(self):
        self.assertTrue(self.store.preview("catalog", "code")["runsCode"])
        with self.assertRaises(StoreError):
            self.store.install("catalog", "code", None, False)
        self.store.install("catalog", "code", None, True)
        self.assertTrue(os.access(self.dir / "code" / "data.py", os.X_OK))

    def test_checksum_mismatch_is_refused(self):
        with self.assertRaises(StoreError):
            self.store.install("catalog", "bad", None, False)
        self.assertFalse((self.dir / "bad").exists())

    def test_only_store_widgets_can_be_removed(self):
        write_widget(self.dir, "mine", {"name": "Mine"})
        with self.assertRaises(StoreError):
            self.store.uninstall("mine")


class LayoutTest(unittest.TestCase):
    def test_custom_items_load_and_fit_side_by_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text(json.dumps({"items": [
                {"widgetId": 1, "x": 0, "y": 0, "w": 8, "h": 4},
                {"widgetId": 0, "custom": "ha", "x": 16, "y": 0, "w": 8, "h": 12},
                {"widgetId": 0, "custom": "clock", "x": 8, "y": 0, "w": 4, "h": 4},
                {"widgetId": 0, "custom": "ha", "x": 0, "y": 8, "w": 2, "h": 2},
                {"widgetId": 0, "custom": "../etc", "x": 0, "y": 8, "w": 2, "h": 2}]}), encoding="utf-8")
            layout = edgelayout.load(path)
        customs = [i for i in layout["items"] if i.get("custom")]
        self.assertEqual([i["custom"] for i in customs], ["ha", "clock"])
        shown = edgelayout.shown_items(layout)
        self.assertEqual({i["key"] for i in shown}, {"widget:1", "custom:ha", "custom:clock"})
        # Two own widgets (both widgetId 0) can't overlap
        moved = dict(customs[1], x=17)
        self.assertFalse(edgelayout.fits(moved, layout["items"]))
        self.assertTrue(edgelayout.fits(dict(customs[1], x=12), layout["items"]))
        self.assertEqual(edgelayout.fields("custom"), [])
        self.assertIsNone(edgelayout.check_settings(customs[0]["settings"]))


if __name__ == "__main__":
    unittest.main()
