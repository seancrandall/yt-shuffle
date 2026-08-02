"""Entry point for the YouTube Randomizer."""

from __future__ import annotations

import os
import sys
from importlib.resources import files

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .app import MainWindow


def _app_icon() -> QIcon:
    """The bundled app icon (icons/youtube-mixer.png), shipped as package data so
    it's available in a non-editable install, not just when running from source."""
    try:
        path = files("youtube_mixer").joinpath("icons/youtube-mixer.png")
        return QIcon(str(path))
    except Exception:  # noqa: BLE001 — never fail to start over a missing icon
        return QIcon()


def main() -> None:
    # Chromium flags for the embedded YouTube player. Must be set before QApplication
    # starts QtWebEngine, which reads QTWEBENGINE_CHROMIUM_FLAGS at initialization.
    #
    # --autoplay-policy=no-user-gesture-required: let the embed autoplay with sound
    #   (Qt button clicks aren't webview user gestures, so without this Chromium
    #   blocks autoplay).
    #
    # --disable-features=AcceleratedVideoDecodeLinuxGL: QtWebEngine 6.11 (Chromium
    #   140) regressed hardware video decode on Linux — the DMA-BUF -> GL frame
    #   import path produces a Y_UV mailbox the Skia renderer can't sample, so the
    #   GPU context is lost and decoded frames never reach the screen (audio plays,
    #   video is black; "SharedImageBackingFactory"/"ProduceSkia non-existent mailbox"
    #   errors). Disabling this one feature keeps full GPU *compositing* of the page
    #   and video while falling back to software decode of the video stream only —
    #   the page stays hardware-accelerated. Tracked in KDE Falkon #520199 and
    #   qutebrowser #8909/#8841.
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--autoplay-policy=no-user-gesture-required "
        "--disable-features=AcceleratedVideoDecodeLinuxGL",
    )
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Randomizer")
    app.setWindowIcon(_app_icon())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
