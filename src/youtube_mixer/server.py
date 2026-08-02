"""Tiny localhost HTTP server for the embedded player page.

YouTube's IFrame embed API rejects pages served from a ``file://`` origin — it returns
``embedder.identity.missing.referrer`` and never loads a video (the player appears blank).
Serving the page from a real ``http://127.0.0.1`` origin gives the embed a usable Referer,
so videos load and play. This serves only ``player.html`` on an ephemeral localhost port.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _make_handler(player_html_path: Path):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/player.html"):
                data = player_html_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)

        def log_message(self, *args, **kwargs):
            pass

    return _Handler


class PlayerServer:
    def __init__(self, player_html_path: Path) -> None:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(player_html_path))
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def url(self) -> str:
        # YouTube's embed auth check accepts "localhost" but rejects "127.0.0.1"
        # (error 150 / "auth"), so the page must be served from the localhost host.
        port = self._httpd.server_address[1]
        return f"http://localhost:{port}/player.html"

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
