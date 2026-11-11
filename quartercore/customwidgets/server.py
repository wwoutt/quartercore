# Local HTTP server for the web views of the own widgets
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Each own widget on the kiosk is a web view on /frame/<id>?token=..., a small
# page (frame.html) that shows widget.html in a sandboxed iframe without
# network access and passes it its data, like the kiosk page of the fork
# wwoutt/OpenLinkHub did. The page gets the data from this server:
#   GET  /api/widgets/<id>/html    widget.html
#   GET  /api/widgets/<id>/data    data from the widget source (cached per refresh)
#   POST /api/widgets/<id>/action  runs the widget's action script
#
# Only 127.0.0.1 on a random port; every request needs the token of this run
# (a header for the API), and the Host header must be this server, so other
# websites and programs can't run widget scripts.

import json
import re
import secrets
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FRAME = Path(__file__).resolve().parent / "frame.html"
MAX_BODY = 64 * 1024


class WidgetServer:
    def __init__(self, library, host="127.0.0.1", port=0):
        self.library = library
        self.token = secrets.token_urlsafe(24)
        self.httpd = ThreadingHTTPServer((host, port), make_handler(self))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.hosts = {"127.0.0.1:%d" % self.port, "localhost:%d" % self.port}
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        return "http://127.0.0.1:%d/" % self.port

    def frame_url(self, widget_id, version=0):
        return "%sframe/%s?token=%s&v=%d" % (self.base_url, urllib.parse.quote(widget_id), self.token, version)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def frame_page(widget, token):
    """frame.html with the widget's id, refresh time and the token filled in."""
    config = json.dumps({"id": widget["id"], "refresh": widget["refresh"], "token": token,
                         "action": widget["action"]})
    # </script> can't end the script early: < is escaped in the JSON
    return FRAME.read_text(encoding="utf-8").replace("{{CONFIG}}", config.replace("<", "\\u003c"))


def make_handler(server):
    library = server.library

    class Handler(BaseHTTPRequestHandler):
        server_version = "Quartercore-widgets"

        def log_message(self, *args):
            pass

        def send(self, code, body, content_type="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def allowed(self, query=None):
            # Host check against DNS rebinding; the token proves the caller is our own page
            if self.headers.get("Host") not in server.hosts:
                return False
            token = (query or {}).get("token") if query is not None else self.headers.get("X-Quartercore-Token")
            return secrets.compare_digest(str(token or ""), server.token)

        def widget(self, widget_id):
            manifest = library.manifest(widget_id)
            return None if manifest is None else library.public(widget_id, manifest)

        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            parts = [p for p in url.path.split("/") if p]
            if len(parts) == 2 and parts[0] == "frame":
                query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
                if not self.allowed(query):
                    self.send(403, {"ok": False, "error": "forbidden"})
                    return
                widget = self.widget(parts[1])
                if widget is None:
                    self.send(404, b"<p>unknown widget</p>", "text/html; charset=utf-8")
                    return
                self.send(200, frame_page(widget, server.token).encode("utf-8"), "text/html; charset=utf-8")
                return
            if not self.allowed():
                self.send(403, {"ok": False, "error": "forbidden"})
                return
            if len(parts) == 4 and parts[:2] == ["api", "widgets"] and parts[3] in ("html", "data"):
                widget = self.widget(parts[2])
                if widget is None:
                    self.send(404, {"ok": False, "error": "unknown widget"})
                elif parts[3] == "html":
                    self.send(200, {"ok": True, "widget": widget, "html": library.html(parts[2])})
                else:
                    self.send(200, library.data(parts[2]))
                return
            self.send(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if not self.allowed():
                self.send(403, {"ok": False, "error": "forbidden"})
                return
            match = re.match(r"^/api/widgets/([^/]+)/action$", self.path.split("?")[0])
            if not match:
                self.send(404, {"ok": False, "error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(min(length, MAX_BODY)) or b"{}")
            except ValueError:
                body = None
            if not isinstance(body, dict):
                self.send(400, {"ok": False, "error": "invalid JSON"})
                return
            if self.widget(match.group(1)) is None:
                self.send(404, {"ok": False, "error": "unknown widget"})
                return
            self.send(200, library.action(match.group(1), body.get("data")))

    return Handler
