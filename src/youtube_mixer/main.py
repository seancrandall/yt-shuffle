"""Entry point for the YouTube Randomizer."""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from .app import MainWindow


def main() -> None:
    # Let the embedded YouTube player autoplay without a user gesture inside the webview
    # (Qt button clicks aren't webview gestures). Must be set before QApplication starts
    # QtWebEngine, which reads QTWEBENGINE_CHROMIUM_FLAGS at initialization.
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS", "--autoplay-policy=no-user-gesture-required"
    )
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Randomizer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
