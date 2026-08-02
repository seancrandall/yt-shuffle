#!/usr/bin/env python3
"""Decisive test: can a YouTube IFrame embed autoplay (muted) from our http origin at all?

Serves a minimal page that creates YT.Player with a videoId baked in and autoplay+mute,
over http://127.0.0.1, and probes whether it actually plays.
"""

from __future__ import annotations

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS", "--autoplay-policy=no-user-gesture-required"
)

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtWebEngineCore import QWebEnginePage  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

HTML = b"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>html,body{margin:0;height:100%;background:#000}#player{width:100%;height:100%}</style></head>
<body><div id="player"></div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>
let p;
function onYouTubeIframeAPIReady(){
  p = new YT.Player('player',{width:'100%',height:'100%',videoId:'dQw4w9WgXcQ',
    playerVars:{autoplay:1,mute:1,controls:1,enablejsapi:1,origin:window.location.origin},
    events:{onReady:function(e){console.log('onReady, playing');e.target.playVideo();},
            onStateChange:function(e){console.log('state='+e.data);},
            onError:function(e){console.log('onError code='+e.data);}}});
}
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(HTML)))
        self.end_headers()
        self.wfile.write(HTML)

    def log_message(self, *a, **k):
        pass


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
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://localhost:{httpd.server_address[1]}/"
    print("serving at", url, flush=True)

    view = QWebEngineView()
    page = DiagPage(view)
    view.setPage(page)
    view.load(QUrl(url))
    view.resize(640, 360)
    view.show()

    probe_js = (
        "JSON.stringify({"
        "state:p&&p.getPlayerState?p.getPlayerState():null, "
        "t:p&&p.getCurrentTime?p.getCurrentTime():null, "
        "vd:p&&p.getVideoData?p.getVideoData():null"
        "})"
    )

    def probe():
        print("probe...", flush=True)

        def cb(v):
            print("PROBE RESULT:", v, flush=True)
            app.quit()

        page.runJavaScript(probe_js, cb)

    QTimer.singleShot(8000, probe)
    QTimer.singleShot(13000, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
