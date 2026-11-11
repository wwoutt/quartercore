# Widget store for Quartercore's own widgets
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from the store of the fork wwoutt/OpenLinkHub
# (extras/widget-helper/olh_store.py, same author), with its own catalog
# (wwoutt/quartercore-widgets) and GitHub topic (quartercore-widget).
#
# Two sources:
# - catalog:   a reviewed GitHub repository with index.json; every file is
#              checked against the SHA-256 in the index
# - community: GitHub repositories with a topic; not reviewed, installed at a
#              fixed commit so the reviewed code is the installed code
# Nothing is updated automatically, and widgets that run code need an explicit
# confirmation.

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .library import RECORD

# Keep these rules in sync with tools/build-index.py in the catalog repository
WIDGET_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REPO_NAME = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
EXTENSIONS = {".json", ".html", ".css", ".js", ".py", ".sh", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".md", ".txt"}
TEXT_EXTENSIONS = {".json", ".html", ".css", ".js", ".py", ".sh", ".md", ".txt"}
CODE_EXTENSIONS = {".py", ".sh"}
MAX_FILES = 30
MAX_FILE_SIZE = 512 * 1024
MAX_TOTAL_SIZE = 2 * 1024 * 1024
CACHE_SECONDS = 300

DEFAULTS = {
    "catalog": "https://raw.githubusercontent.com/wwoutt/quartercore-widgets/main/",
    "community": True,
    "topic": "quartercore-widget",
}


class StoreError(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


class Store:
    def __init__(self, config_dir, secrets_file, on_change):
        self.config_dir = config_dir
        self.secrets_file = secrets_file
        self.on_change = on_change
        self.github_api = os.environ.get("QUARTERCORE_GITHUB_API", "https://api.github.com").rstrip("/")
        self.github_raw = os.environ.get("QUARTERCORE_GITHUB_RAW", "https://raw.githubusercontent.com").rstrip("/")
        self.cache = {}
        self.mutex = threading.Lock()

    # Configuration and HTTP

    def settings(self):
        settings = dict(DEFAULTS)
        try:
            with open(os.path.join(self.config_dir, "store.json"), encoding="utf-8") as f:
                settings.update(json.load(f))
        except (OSError, ValueError):
            pass
        if os.environ.get("QUARTERCORE_STORE_CATALOG"):
            settings["catalog"] = os.environ["QUARTERCORE_STORE_CATALOG"]
        if not settings["catalog"].endswith("/"):
            settings["catalog"] += "/"
        return settings

    def github_headers(self):
        headers = {"Accept": "application/vnd.github+json"}
        try:
            with open(self.secrets_file, encoding="utf-8") as f:
                token = json.load(f).get("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = "Bearer " + token
        except (OSError, ValueError, AttributeError):
            pass
        return headers

    def get(self, url, headers=None, max_size=MAX_FILE_SIZE):
        if not url.startswith(("https://", "http://")):
            raise StoreError("invalid url")
        request = urllib.request.Request(url, headers=dict({"User-Agent": "Quartercore-widgets"}, **(headers or {})))
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read(max_size + 1)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise StoreError("GitHub rate limit reached, try again later or add GITHUB_TOKEN to secrets.json", 502)
            raise StoreError("download failed (HTTP %d): %s" % (e.code, url), 502)
        except (urllib.error.URLError, OSError) as e:
            raise StoreError("download failed: %s" % e, 502)
        if len(data) > max_size:
            raise StoreError("file too large: %s" % url)
        return data

    def get_json(self, url, headers=None, max_size=MAX_FILE_SIZE):
        try:
            return json.loads(self.get(url, headers, max_size))
        except ValueError:
            raise StoreError("invalid JSON: %s" % url, 502)

    def cached(self, key, load):
        with self.mutex:
            entry = self.cache.get(key)
            if entry and time.time() - entry[0] < CACHE_SECONDS:
                return entry[1]
        value = load()
        with self.mutex:
            self.cache[key] = (time.time(), value)
        return value

    # Installed widgets

    def record(self, widget_id):
        try:
            with open(os.path.join(self.config_dir, widget_id, RECORD), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def status(self, widget_id, kind, ref, version_key):
        """installed / update / conflict (folder in use by another widget)"""
        if not os.path.exists(os.path.join(self.config_dir, widget_id)):
            return {"installed": False}
        record = self.record(widget_id)
        if not record or record.get("kind") != kind or record.get("ref") != ref:
            return {"installed": False, "conflict": True}
        return {"installed": True, "update": version_key is not None and record.get("version") != version_key}

    # Listing

    def catalog_index(self):
        settings = self.settings()
        index = self.cached("catalog:" + settings["catalog"],
                            lambda: self.get_json(settings["catalog"] + "index.json", max_size=MAX_TOTAL_SIZE))
        if not isinstance(index, dict) or not isinstance(index.get("widgets"), list):
            raise StoreError("invalid catalog index", 502)
        return index["widgets"]

    def catalog_entry(self, widget_id):
        for entry in self.catalog_index():
            if entry.get("id") == widget_id:
                return entry
        raise StoreError("widget not in catalog", 404)

    def list(self, kind, query):
        query = (query or "").strip().lower()
        if kind == "catalog":
            entries = []
            for entry in self.catalog_index():
                widget_id = str(entry.get("id", ""))
                if not WIDGET_ID.match(widget_id):
                    continue
                text = " ".join(str(entry.get(k, "")) for k in ("name", "description", "author")).lower()
                if query and query not in text:
                    continue
                files_key = hashlib.sha256(json.dumps(entry.get("files", {}), sort_keys=True).encode()).hexdigest()
                item = {k: entry.get(k) for k in ("id", "name", "description", "author", "license", "version", "source", "runsCode")}
                item.update(ref=widget_id, reviewed=True, **self.status(widget_id, "catalog", widget_id, files_key))
                entries.append(item)
            return entries

        if kind == "community":
            settings = self.settings()
            if not settings.get("community"):
                return []
            q = "topic:%s %s" % (settings["topic"], query)
            url = "%s/search/repositories?%s" % (self.github_api, urllib.parse.urlencode({"q": q.strip(), "sort": "stars", "per_page": 30}))
            result = self.cached("community:" + url, lambda: self.get_json(url, self.github_headers()))
            entries = []
            for repo in result.get("items", []):
                full_name = repo.get("full_name", "")
                if not REPO_NAME.match(full_name):
                    continue
                widget_id = safe_id(repo.get("name", ""))
                if not widget_id:
                    continue
                item = {
                    "id": widget_id,
                    "ref": full_name,
                    "name": repo.get("name"),
                    "description": repo.get("description") or "",
                    "author": (repo.get("owner") or {}).get("login", ""),
                    "license": (repo.get("license") or {}).get("spdx_id") or "",
                    "stars": repo.get("stargazers_count", 0),
                    "url": repo.get("html_url"),
                    "reviewed": False,
                    "runsCode": None,
                }
                item.update(self.status(widget_id, "community", full_name, None))
                entries.append(item)
            return entries

        raise StoreError("unknown store")

    # Fetching widget files

    def fetch_catalog(self, widget_id):
        entry = self.catalog_entry(widget_id)
        files = entry.get("files")
        path = str(entry.get("path", ""))
        if not isinstance(files, dict) or not re.match(r"^widgets/[a-z0-9][a-z0-9_-]{0,63}$", path):
            raise StoreError("invalid catalog entry", 502)
        base = self.settings()["catalog"] + path + "/"
        contents = {}
        for name, digest in files.items():
            check_name(name)
            data = self.get(base + urllib.parse.quote(name))
            if hashlib.sha256(data).hexdigest() != digest:
                raise StoreError("checksum mismatch for %s, the catalog is being updated, try again later" % name, 502)
            contents[name] = data
        version = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        return widget_id, contents, version, [], None

    def fetch_community(self, full_name, commit=None):
        if not REPO_NAME.match(full_name or ""):
            raise StoreError("invalid repository")
        headers = self.github_headers()
        if commit is None:
            repo = self.get_json("%s/repos/%s" % (self.github_api, full_name), headers)
            branch = urllib.parse.quote(repo.get("default_branch") or "main")
            commit = self.get_json("%s/repos/%s/commits/%s" % (self.github_api, full_name, branch), headers).get("sha", "")
        if not COMMIT.match(commit or ""):
            raise StoreError("invalid commit")

        listing = self.get_json("%s/repos/%s/contents?ref=%s" % (self.github_api, full_name, commit), headers)
        if not isinstance(listing, list):
            raise StoreError("unexpected repository listing", 502)
        contents, skipped = {}, []
        for entry in listing:
            name = entry.get("name", "")
            if entry.get("type") != "file" or name.startswith("."):
                continue
            if not allowed_name(name):
                skipped.append(name)
                continue
            if entry.get("size", 0) > MAX_FILE_SIZE:
                raise StoreError("%s is larger than %d KB" % (name, MAX_FILE_SIZE // 1024))
            contents[name] = self.get("%s/%s/%s/%s" % (self.github_raw, full_name, commit, urllib.parse.quote(name)))
        return safe_id(full_name.split("/")[1]), contents, commit, skipped, commit

    def fetch(self, kind, ref, commit=None):
        if kind == "catalog":
            if not WIDGET_ID.match(ref or ""):
                raise StoreError("invalid widget id")
            result = self.fetch_catalog(ref)
        elif kind == "community":
            if not self.settings().get("community"):
                raise StoreError("community widgets are disabled")
            result = self.fetch_community(ref, commit)
        else:
            raise StoreError("unknown store")
        widget_id, contents = result[0], result[1]
        if not widget_id:
            raise StoreError("invalid widget name")
        check_contents(contents)
        return result

    # Actions

    def preview(self, kind, ref):
        widget_id, contents, version, skipped, commit = self.fetch(kind, ref)
        manifest = json.loads(contents["widget.json"])
        source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
        files = []
        for name in sorted(contents):
            ext = os.path.splitext(name)[1].lower()
            text = None
            if (ext in TEXT_EXTENSIONS or name == "LICENSE") and len(contents[name]) <= 64 * 1024:
                text = contents[name].decode("utf-8", errors="replace")
            files.append({"name": name, "size": len(contents[name]), "text": text})
        return {
            "id": widget_id,
            "kind": kind,
            "ref": ref,
            "commit": commit,
            "manifest": manifest,
            "source": source.get("type") or "none",
            "runsCode": runs_code(manifest, contents),
            "files": files,
            "skipped": skipped,
        }

    def install(self, kind, ref, commit, confirmed):
        if kind == "community" and not COMMIT.match(commit or ""):
            raise StoreError("preview the widget first")
        widget_id, contents, version, skipped, commit = self.fetch(kind, ref, commit)
        manifest = json.loads(contents["widget.json"])
        if runs_code(manifest, contents) and not confirmed:
            raise StoreError("this widget runs code, confirm the installation", 409)

        target = os.path.join(self.config_dir, widget_id)
        if os.path.exists(target):
            record = self.record(widget_id)
            if not record or record.get("kind") != kind or record.get("ref") != ref:
                raise StoreError("a widget named '%s' already exists" % widget_id, 409)

        os.makedirs(self.config_dir, exist_ok=True)
        temp = tempfile.mkdtemp(prefix=".store-tmp-", dir=self.config_dir)
        try:
            for name, data in contents.items():
                with open(os.path.join(temp, name), "wb") as f:
                    f.write(data)
                if os.path.splitext(name)[1].lower() in CODE_EXTENSIONS:
                    os.chmod(os.path.join(temp, name), 0o755)
            with open(os.path.join(temp, RECORD), "w", encoding="utf-8") as f:
                json.dump({"kind": kind, "ref": ref, "version": version, "commit": commit,
                           "installed": int(time.time())}, f, indent=2)
            old = None
            if os.path.exists(target):
                old = tempfile.mkdtemp(prefix=".store-old-", dir=self.config_dir)
                os.rename(target, os.path.join(old, "widget"))
            os.rename(temp, target)
            temp = None
            if old:
                shutil.rmtree(old, ignore_errors=True)
        finally:
            if temp:
                shutil.rmtree(temp, ignore_errors=True)
        self.on_change(widget_id)
        return {"id": widget_id, "skipped": skipped}

    def uninstall(self, widget_id):
        if not WIDGET_ID.match(widget_id or ""):
            raise StoreError("invalid widget id")
        if not self.record(widget_id):
            raise StoreError("only widgets installed from the store can be removed here", 409)
        if not os.path.isdir(os.path.join(self.config_dir, widget_id)):
            raise StoreError("widget not found", 404)
        shutil.rmtree(os.path.join(self.config_dir, widget_id))
        # Its settings (gear button) may hold a token, don't leave them behind
        try:
            os.remove(os.path.join(self.config_dir, ".settings", widget_id + ".json"))
        except OSError:
            pass
        self.on_change(widget_id)
        return {"id": widget_id}


def safe_id(name):
    name = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-_")
    return name[:64] if name and WIDGET_ID.match(name[:64]) else ""


def allowed_name(name):
    ext = os.path.splitext(name)[1].lower()
    return bool(FILE_NAME.match(name)) and (ext in EXTENSIONS or name == "LICENSE")


def check_name(name):
    if not allowed_name(name):
        raise StoreError("file name or type not allowed: %s" % name)


def check_contents(contents):
    for required in ("widget.json", "widget.html"):
        if required not in contents:
            raise StoreError("%s is missing" % required)
    if len(contents) > MAX_FILES:
        raise StoreError("more than %d files" % MAX_FILES)
    if sum(len(data) for data in contents.values()) > MAX_TOTAL_SIZE:
        raise StoreError("larger than %d MB in total" % (MAX_TOTAL_SIZE // 1024 // 1024))
    try:
        manifest = json.loads(contents["widget.json"])
    except ValueError:
        raise StoreError("widget.json is not valid JSON")
    if not isinstance(manifest, dict):
        raise StoreError("widget.json is not an object")


def runs_code(manifest, contents):
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    return source.get("type") == "script" or "action" in manifest or any(os.path.splitext(n)[1].lower() in CODE_EXTENSIONS for n in contents)
