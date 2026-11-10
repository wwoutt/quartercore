# Media player for the XENEON EDGE kiosk: what plays now (MPRIS) and the buttons
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/media/media.go): the first
# MPRIS player (sorted by bus name) that is playing. The player properties are
# read with busctl (part of systemd), because PySide6 can't unpack the D-Bus
# dictionaries (a{sv}) of MPRIS. OpenLinkHub sends media keys through a virtual
# keyboard; Quartercore calls the MPRIS methods of that player instead, and
# sets the volume with wpctl (PipeWire). Upstream's "play" button sends
# "previous"; here it toggles play/pause.

import json

from PySide6.QtCore import QObject, QProcess, Signal
from PySide6.QtDBus import QDBusConnection, QDBusInterface

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
METHODS = {"previous": "Previous", "stop": "Stop", "play": "PlayPause", "next": "Next"}
VOLUME = {"volumeDown": ["set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"],
          "volumeUp": ["set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%+"],
          "mute": ["set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]}


def unwrap(value):
    """busctl --json values are {"type": ..., "data": ...}; returns plain Python values."""
    if isinstance(value, dict) and set(value) == {"type", "data"}:
        return unwrap(value["data"])
    if isinstance(value, dict):
        return {k: unwrap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    return value


def parse_busctl(output):
    """Output of busctl --json=short call ... GetAll s org.mpris.MediaPlayer2.Player -> properties."""
    try:
        data = json.loads(output)
    except ValueError:
        return None
    items = data.get("data") if isinstance(data, dict) else None
    return unwrap(items[0]) if items else None


def now_playing(properties):
    """The fields of /api/media/playback from the MPRIS player properties."""
    meta = properties.get("Metadata") or {}
    artists = meta.get("xesam:artist") or []
    if isinstance(artists, str):
        artists = [artists]
    return {
        "playing": properties.get("PlaybackStatus") == "Playing",
        "title": meta.get("xesam:title") or "",
        "artists": list(artists),
        "album": meta.get("xesam:album") or "",
        "position": int(properties.get("Position") or 0) / 1e6,
        "length": int(meta.get("mpris:length") or 0) / 1e6,
    }


def choose(players):
    """The first playing player, like getCurrentlyPlaying; (None, None) when nothing plays."""
    for name in sorted(players):
        info = players[name]
        if info and info["playing"]:
            return name, info
    return None, None


class Media(QObject):
    """Asks the MPRIS players what plays, without blocking the interface."""
    updated = Signal()

    def __init__(self, parent=None, bus=None, program="busctl"):
        super().__init__(parent)
        self.bus = bus or QDBusConnection.sessionBus()
        self.program = program
        self.player = ""
        self.playing = None
        self._pending = {}
        self._results = {}

    def players(self):
        reply = self.bus.interface().registeredServiceNames()
        names = reply.value() if reply.isValid() else []
        return sorted(n for n in names if n.startswith(MPRIS_PREFIX))

    def refresh(self):
        if self._pending:
            return
        names = self.players()
        if not names:
            self.player, self.playing = "", None
            self.updated.emit()
            return
        self._results = {}
        for name in names:
            process = QProcess(self)
            process.finished.connect(lambda code, _s, n=name, p=process: self._finished(n, p, code))
            process.errorOccurred.connect(lambda _e, n=name, p=process: self._finished(n, p, -1))
            self._pending[name] = process
            process.start(self.program, ["--user", "--json=short", "call", name, MPRIS_PATH,
                                         "org.freedesktop.DBus.Properties", "GetAll", "s", PLAYER])

    def _finished(self, name, process, code):
        if self._pending.get(name) is not process:
            return
        del self._pending[name]
        properties = parse_busctl(bytes(process.readAllStandardOutput()).decode(errors="replace")) if code == 0 else None
        process.deleteLater()
        self._results[name] = now_playing(properties) if properties else None
        if self._pending:
            return
        player, info = choose(self._results)
        self.player = player or (self.player if self.player in self._results else "")
        self.playing = info
        self.updated.emit()

    def control(self, action):
        if action in VOLUME:
            QProcess.startDetached("wpctl", VOLUME[action])
            return
        method = METHODS.get(action)
        if not method:
            return
        player = self.player or next(iter(self.players()), "")
        if player:
            QDBusInterface(player, MPRIS_PATH, PLAYER, self.bus).call(method)
