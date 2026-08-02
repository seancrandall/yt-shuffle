"""Embedded YouTube player backed by QtWebEngine (Chromium).

Loads ``player.html`` (bundled as package data), which hosts the YouTube IFrame Player API.
Native code drives playback by calling ``window.playVideo`` / ``playList`` / ``next`` / ``prev``
through ``runJavaScript``. Calls made before the page finishes loading are buffered and flushed
on ``loadFinished``; the page itself queues calls until the IFrame API player is ready.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

_PLAYER_HTML = Path(__file__).parent / "player.html"


class PlayerView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._pending: list[str] = []
        self.loadFinished.connect(self._on_load_finished)
        self.load(QUrl.fromLocalFile(str(_PLAYER_HTML)))

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

    def next(self) -> None:
        self._run("window.next && window.next();")

    def prev(self) -> None:
        self._run("window.prev && window.prev();")
