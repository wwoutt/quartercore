# Own widgets on disk: manifests, settings, data sources and actions
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from the widget helper of the fork wwoutt/OpenLinkHub
# (extras/widget-helper/olh-widget-helper.py). A widget is a flat folder in
# ~/.config/Quartercore/widgets/<id>/ with widget.json and widget.html, and
# optionally scripts:
#   source  "none", "url" (fetched here, so API keys stay out of the page) or
#           "script" (a program that prints JSON, run as the user)
#   action  a script that gets the widget's request as JSON on stdin; it
#           decides what the widget may do
#   settings  fields the user fills in with the gear button (a server, a
#           token); stored in .settings/<id>.json, secrets never go back to
#           the page

import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

WIDGET_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SETTING_NAME = re.compile(r"^[A-Za-z0-9_]{1,64}$")
SETTING_TYPES = ("text", "url", "secret")
MAX_SETTING = 4096
MAX_OUTPUT = 1024 * 1024
DEFAULT_TIMEOUT = 10
MAX_TIMEOUT = 60
RECORD = ".store.json"          # how a widget was installed from the store
OLD_RECORD = ".olh-store.json"  # the same, written by the fork's store


def widgets_dir():
    if os.environ.get("QUARTERCORE_WIDGETS_DIR"):
        return Path(os.environ["QUARTERCORE_WIDGETS_DIR"])
    home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return home / "Quartercore" / "widgets"


def openlinkhub_widgets_dir():
    home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return home / "openlinkhub-widgets"


def write_private(path, value):
    """Writes JSON only the user can read (settings may hold a token)."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(value, f)
    os.replace(temporary, path)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def parse_output(raw, content_type=""):
    text = raw.decode("utf-8", errors="replace")
    if "json" in content_type or text.lstrip()[:1] in ("{", "["):
        try:
            return json.loads(text)
        except ValueError:
            pass
    return text


def timeout_seconds(source):
    try:
        return min(MAX_TIMEOUT, max(1, int(source.get("timeout") or DEFAULT_TIMEOUT)))
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_TIMEOUT


def refresh_seconds(manifest):
    try:
        return max(1, int(manifest.get("refresh") or 60))
    except (TypeError, ValueError):
        return 60


def setting_fields(manifest):
    """The "settings" fields of widget.json, checked: [{name, label, type, help, default}]."""
    fields = []
    for field in manifest.get("settings") or []:
        if not isinstance(field, dict) or not SETTING_NAME.match(str(field.get("name") or "")):
            continue
        kind = field.get("type") if field.get("type") in SETTING_TYPES else "text"
        fields.append({
            "name": field["name"],
            "label": str(field.get("label") or field["name"]),
            "type": kind,
            "help": str(field.get("help") or ""),
            "default": "" if kind == "secret" else str(field.get("default") or ""),
        })
    return fields


class Library:
    def __init__(self, directory=None, log=None):
        self.dir = Path(directory or widgets_dir())
        self.log = log or (lambda message: None)
        self.cache = {}
        self.locks = {}
        self.mutex = threading.Lock()

    @property
    def settings_dir(self):
        return self.dir / ".settings"

    @property
    def secrets_file(self):
        return self.dir / "secrets.json"

    # --- widgets ---

    def widget_dir(self, widget_id):
        if not WIDGET_ID.match(widget_id or ""):
            return None
        path = self.dir / widget_id
        return path if (path / "widget.json").is_file() else None

    def manifest(self, widget_id):
        path = self.widget_dir(widget_id)
        if path is None:
            return None
        try:
            manifest = json.loads((path / "widget.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            self.log("widget %s: invalid widget.json: %s" % (widget_id, e))
            return None
        return manifest if isinstance(manifest, dict) else None

    def modified(self, widget_id):
        """Newest file change in the widget folder, so the kiosk reloads after an edit or update."""
        path = self.widget_dir(widget_id)
        try:
            return int(max(os.path.getmtime(path / name) for name in os.listdir(path)))
        except (OSError, TypeError, ValueError):
            return 0

    def public(self, widget_id, manifest):
        size = manifest.get("size") if isinstance(manifest.get("size"), dict) else {}
        source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}

        def cells(value, default, top):
            try:
                return min(top, max(1, int(value or default)))
            except (TypeError, ValueError):
                return default
        return {
            "id": widget_id,
            "modified": self.modified(widget_id),
            "name": str(manifest.get("name") or widget_id),
            "description": str(manifest.get("description") or ""),
            "author": str(manifest.get("author") or ""),
            "version": str(manifest.get("version") or ""),
            "size": {"w": cells(size.get("w"), 4, 24), "h": cells(size.get("h"), 3, 12)},
            "refresh": refresh_seconds(manifest),
            "source": str(source.get("type") or "none"),
            "action": isinstance(manifest.get("action"), dict),
            "settings": setting_fields(manifest),
            "store": bool(self.record(widget_id)),
        }

    def list(self):
        widgets = []
        try:
            names = sorted(os.listdir(self.dir))
        except OSError:
            names = []
        for name in names:
            manifest = self.manifest(name)
            if manifest is not None:
                widgets.append(self.public(name, manifest))
        return widgets

    def html(self, widget_id):
        path = self.widget_dir(widget_id)
        try:
            return (path / "widget.html").read_text(encoding="utf-8")
        except (OSError, TypeError):
            return "<p>widget.html missing</p>"

    def record(self, widget_id):
        path = self.dir / widget_id
        return read_json(path / RECORD) or None

    # --- settings ---

    def settings_file(self, widget_id):
        return self.settings_dir / (widget_id + ".json")

    def load_settings(self, widget_id):
        return read_json(self.settings_file(widget_id))

    def public_settings(self, widget_id):
        """Values for the settings form; secrets only say whether they are set."""
        manifest = self.manifest(widget_id) or {}
        values = self.load_settings(widget_id)
        result = {}
        for field in setting_fields(manifest):
            value = values.get(field["name"])
            if field["type"] == "secret":
                result[field["name"]] = {"set": bool(value)}
            else:
                result[field["name"]] = {"value": str(value) if value is not None else field["default"]}
        return result

    def save_settings(self, widget_id, new_values):
        """Stores the declared fields only; an empty secret keeps the stored one."""
        manifest = self.manifest(widget_id)
        if manifest is None:
            raise ValueError("unknown widget")
        if not isinstance(new_values, dict):
            raise ValueError("values must be an object")
        values = self.load_settings(widget_id)
        for field in setting_fields(manifest):
            name = field["name"]
            value = new_values.get(name)
            if value is None or (field["type"] == "secret" and value == ""):
                continue
            if not isinstance(value, str) or len(value) > MAX_SETTING:
                raise ValueError("invalid value for %s" % field["label"])
            value = value.strip()
            if field["type"] == "url" and value and not value.startswith(("http://", "https://")):
                raise ValueError("%s must start with http:// or https://" % field["label"])
            values[name] = value
        write_private(self.settings_file(widget_id), values)
        self.forget(widget_id)

    def secrets(self, widget_id=None):
        """secrets.json, with the widget's own settings on top."""
        values = read_json(self.secrets_file)
        if widget_id:
            values.update({k: v for k, v in self.load_settings(widget_id).items() if v})
        return values

    # --- data ---

    def lock(self, widget_id):
        with self.mutex:
            return self.locks.setdefault(widget_id, threading.Lock())

    def forget(self, widget_id):
        self.cache.pop(widget_id, None)

    def fill(self, value, secrets):
        """Replaces ${NAME} with the value of NAME from the settings or secrets.json."""
        return re.sub(r"\$\{([A-Za-z0-9_]+)\}", lambda m: str(secrets.get(m.group(1), "")), value)

    def fetch_url(self, widget_id, source):
        secrets = self.secrets(widget_id)
        url = self.fill(str(source.get("url") or ""), secrets)
        if not url.startswith(("http://", "https://")):
            raise ValueError("source.url must start with http:// or https://")
        headers = {"User-Agent": "Quartercore-widgets"}
        for key, value in (source.get("headers") or {}).items():
            headers[str(key)] = self.fill(str(value), secrets)
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout_seconds(source)) as response:
            raw = response.read(MAX_OUTPUT + 1)
            if len(raw) > MAX_OUTPUT:
                raise ValueError("response larger than 1 MB")
            return parse_output(raw, response.headers.get("Content-Type", ""))

    def run_script(self, widget_id, source, default="data.py", stdin=b""):
        path = self.widget_dir(widget_id)
        command = source.get("command") or ["python3", default]
        if isinstance(command, str):
            command = [command]
        command = [str(part) for part in command]
        env = dict(os.environ, OLH_WIDGET_DIR=str(path), OLH_SECRETS_FILE=str(self.secrets_file),
                   OLH_SETTINGS_FILE=str(self.settings_file(widget_id)))
        result = subprocess.run(command, cwd=path, env=env, capture_output=True, input=stdin,
                                timeout=timeout_seconds(source))
        if result.returncode != 0:
            error = result.stderr.decode("utf-8", errors="replace").strip()[-500:]
            raise RuntimeError("script exited with %d: %s" % (result.returncode, error))
        if len(result.stdout) > MAX_OUTPUT:
            raise ValueError("script output larger than 1 MB")
        return parse_output(result.stdout)

    def data(self, widget_id):
        """The cached data, or fresh data when it is older than the widget's refresh."""
        manifest = self.manifest(widget_id)
        if manifest is None:
            return {"ok": False, "data": None, "error": "unknown widget", "updated": int(time.time())}
        with self.lock(widget_id):
            entry = self.cache.get(widget_id)
            if entry and time.time() - entry["time"] < refresh_seconds(manifest):
                return entry["value"]
            source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
            kind = source.get("type") or "none"
            value = {"ok": True, "data": None, "error": None, "updated": int(time.time())}
            try:
                if kind == "url":
                    value["data"] = self.fetch_url(widget_id, source)
                elif kind == "script":
                    value["data"] = self.run_script(widget_id, source)
                elif kind != "none":
                    raise ValueError("unknown source type: %s" % kind)
            except subprocess.TimeoutExpired:
                value.update(ok=False, error="script timed out")
            except (urllib.error.URLError, OSError, ValueError, RuntimeError) as e:
                value.update(ok=False, error=str(e))
            if not value["ok"]:
                self.log("widget %s: %s" % (widget_id, value["error"]))
            self.cache[widget_id] = {"time": time.time(), "value": value}
            return value

    def action(self, widget_id, request):
        """Runs the action script with the widget's request as JSON on stdin."""
        manifest = self.manifest(widget_id)
        action = (manifest or {}).get("action")
        if not isinstance(action, dict) or (action.get("type") or "script") != "script":
            return {"ok": False, "data": None, "error": "widget has no action script"}
        value = {"ok": True, "data": None, "error": None}
        with self.lock(widget_id):
            try:
                value["data"] = self.run_script(widget_id, action, "action.py",
                                                json.dumps(request).encode("utf-8"))
            except subprocess.TimeoutExpired:
                value.update(ok=False, error="action timed out")
            except (OSError, ValueError, RuntimeError) as e:
                value.update(ok=False, error=str(e))
            # The next data request fetches fresh data, so the widget shows the result
            self.forget(widget_id)
        if not value["ok"]:
            self.log("widget %s action: %s" % (widget_id, value["error"]))
        return value

    # --- taking over the fork's widgets ---

    def import_openlinkhub(self, old=None):
        """Copies the widgets, settings and secrets of the fork's widget helper, once:
        only when Quartercore has no widgets folder yet. Returns the copied widget ids."""
        old = Path(old or openlinkhub_widgets_dir())
        if self.dir.exists() or not old.is_dir():
            return []
        self.dir.mkdir(parents=True)
        copied = []
        for name in sorted(os.listdir(old)):
            source = old / name
            if WIDGET_ID.match(name) and (source / "widget.json").is_file():
                shutil.copytree(source, self.dir / name, ignore=shutil.ignore_patterns("__pycache__"))
                if (self.dir / name / OLD_RECORD).is_file():
                    os.replace(self.dir / name / OLD_RECORD, self.dir / name / RECORD)
                copied.append(name)
        for name in copied:
            values = read_json(old / ".settings" / (name + ".json"))
            if values:
                write_private(self.settings_file(name), values)
        secrets = read_json(old / "secrets.json")
        if secrets:
            write_private(self.secrets_file, secrets)
        return copied

    def snapshot(self):
        """Changes when a widget is added, removed or edited (for watching the folder)."""
        return [(w["id"], w["modified"]) for w in self.list()]
