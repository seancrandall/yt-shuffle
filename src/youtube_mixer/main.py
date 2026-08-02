"""Entry point for the YouTube Randomizer."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .app import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Randomizer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
