"""Entry point for the YouTube Randomizer."""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from .app import MainWindow


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
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
