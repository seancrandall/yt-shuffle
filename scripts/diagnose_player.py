#!/usr/bin/env python3
"""Diagnostic: verify a YouTube video actually loads/plays inside our QtWebEngine page.

Serves player.html over http://localhost (the fix for the file:// "missing referrer" and
127.0.0.1 "auth" rejections), asks the page to play a known video, forwards JS console
messages, and probes the player state. Prints findings and exits.

    python scripts/diagnose_player.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow autoplay-with-sound in the embedded Chromium (no user gesture in the webview).
# Must be set before importing/initializing QtWebEngine.
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS", "--autoplay-policy=no-user-gesture-required"
)

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtWebEngineCore import QWebEnginePage  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from youtube_mixer.server import PlayerServer  # noqa: E402

HTML = Path(__file__).resolve().parents[1] / "src" / "youtube_mixer" / "player.html"

_LEVELS = {
    QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "info",
    QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "warn",
    QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "error",
}


class DiagPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f"[JS {_LEVELS.get(level, level)}] {message}  ({source}:{line})", flush=True)


def main() -> None:
    app = QApplication(sys.argv)
    server = PlayerServer(HTML)
    server.start()
    print(f"serving player.html at {server.url}", flush=True)

    view = QWebEngineView()
    page = DiagPage(view)
    view.setPage(page)
    view.load(QUrl(server.url))
    view.resize(640, 360)
    view.show()

    def on_loaded(ok):
        print(f"loadFinished ok={ok}", flush=True)
        if ok:
            page.runJavaScript('window.playList && window.playList(["dQw4w9WgXcQ"], 0);')

    page.loadFinished.connect(on_loaded)

    def muted_play():
        print("muted_play: sending mute() + playVideo()", flush=True)
        page.runJavaScript("try { player.mute(); player.playVideo(); } catch (e) {}")

    QTimer.singleShot(2500, muted_play)

    probe_js = """
    (function () {
      var r = {};
      r.playerState = (player && player.getPlayerState) ? player.getPlayerState() : null;
      try { r.videoData = player.getVideoData(); } catch (e) { r.videoData = 'err:' + e; }
      r.currentTime = (player && player.getCurrentTime) ? player.getCurrentTime() : null;
      var f = document.querySelector('iframe');
      r.iframeSrc = f ? f.src : null;
      return JSON.stringify(r);
    })()
    """

    def probe():
        print("probe: requesting page state...", flush=True)

        def cb(value):
            print("PROBE RESULT:", value, flush=True)
            app.quit()

        page.runJavaScript(probe_js, cb)

    QTimer.singleShot(7000, probe)
    QTimer.singleShot(12000, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
