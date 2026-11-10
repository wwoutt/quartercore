# Settings of the devices quartercore-core drives (fan mode, ...)
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# One JSON file per device in ~/.config/Quartercore/core/. The first time a
# device is taken over, its settings are read from OpenLinkHub's profile when
# that file can be read.

import json
import os
from pathlib import Path

OPENLINKHUB_PROFILES = Path("/var/opt/OpenLinkHub/database/profiles")


def default_folder():
    home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return home / "Quartercore" / "core"


class Store:
    def __init__(self, folder=None, openlinkhub_profiles=OPENLINKHUB_PROFILES):
        self.folder = Path(folder or default_folder())
        self.openlinkhub_profiles = Path(openlinkhub_profiles)

    def _path(self, serial):
        return self.folder / ("%s.json" % "".join(c for c in serial if c.isalnum() or c == "-"))

    def load(self, serial, defaults):
        settings = dict(defaults)
        for path in (self._path(serial), self.openlinkhub_profiles / ("%s.json" % serial)):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            settings.update({k: data[k] for k in defaults if k in data})
            break
        return settings

    def save(self, serial, settings):
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self._path(serial)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
