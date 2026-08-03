"""Embedded YouTube player backed by QtWebEngine (Chromium).

Loads ``player.html`` (bundled as package data), which hosts the YouTube IFrame Player API.
Native code drives playback by calling ``window.playVideo`` / ``playList`` / ``next`` / ``prev``
through ``runJavaScript``. Calls made before the page finishes loading are buffered and flushed
on ``loadFinished``; the page itself queues calls until the IFrame API player is ready.

The page auto-advances to the next shuffled video when one ends, and reports the now-playing
video id back to native via a QtWebChannel bridge (``currentChanged`` signal), so the UI can
highlight the current row.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from .server import PlayerServer

_PLAYER_HTML = Path(__file__).parent / "player.html"


class _PlayerBridge(QObject):
    """Object exposed to the page's JS via QWebChannel (registered as 'bridge')."""

    currentChanged = Signal(str)

    @Slot(str)
    def report_current(self, video_id: str) -> None:
        """Invokable from JS (QWebChannel exposes slots, not signals) to report the
        now-playing video; re-emitted as ``currentChanged`` for the native UI."""
        self.currentChanged.emit(video_id)


class PlayerView(QWebEngineView):
    # Emitted by the page whenever the now-playing video changes (load, next, prev, auto-advance).
    currentChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._pending: list[str] = []

        self._bridge = _PlayerBridge(self)
        self._bridge.currentChanged.connect(self.currentChanged)

        channel = QWebChannel(self)
        channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(channel)

        # YouTube embeds require an http origin (file:// is rejected with
        # "embedder.identity.missing.referrer"), so serve the page locally.
        self._server = PlayerServer(_PLAYER_HTML)
        self._server.start()

        self.loadFinished.connect(self._on_load_finished)
        self.load(QUrl(self._server.url))

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            return
        self._ready = True
        for script in self._pending:
            self.page().runJavaScript(script)
        self._pending.clear()

    def _run(self, script: str) -> None:
        if self._ready:
            self.page().runJavaScript(script)
        else:
            self._pending.append(script)

    def play_video(self, video_id: str) -> None:
        self._run(f"window.playVideo && window.playVideo({video_id!r});")

    def play_list(self, video_ids: list[str], index: int = 0) -> None:
        ids_js = "[" + ",".join(repr(i) for i in video_ids) + "]"
        self._run(f"window.playList && window.playList({ids_js}, {int(index)});")

    def set_list(self, video_ids: list[str], index: int = 0) -> None:
        """Reorder the player's list *without* reloading the current video: sets the new
        play order and the current index, leaving what's playing untouched (used by the
        shuffle toggle so playback isn't interrupted)."""
        ids_js = "[" + ",".join(repr(i) for i in video_ids) + "]"
        self._run(f"window.setList && window.setList({ids_js}, {int(index)});")

    def next(self) -> None:
        self._run("window.next && window.next();")

    def prev(self) -> None:
        self._run("window.prev && window.prev();")

    def set_auto_advance(self, enabled: bool) -> None:
        flag = "true" if enabled else "false"
        self._run(f"window.setAutoAdvance && window.setAutoAdvance({flag});")

    def set_quality(self, key: str) -> None:
        """Set playback quality: medium|hd720|hd1080|hd1440|cinema (best)."""
        self._run(f"window.setQuality && window.setQuality({key!r});")
