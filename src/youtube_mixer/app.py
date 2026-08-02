"""Main application window: playlist input, embedded player, and shuffled list.

Loading a playlist runs the (synchronous, network) fetch on a QThread so the UI stays
responsive; the resulting videos are shuffled (full-coverage Fisher–Yates) before display.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .api import YouTubeError, fetch_playlist
from .models import PlaylistModel
from .player import PlayerView
from .playlist import Video, search, shuffle
from .settings import get_api_key, set_api_key

CONSOLE_URL = "https://console.cloud.google.com/apis/library/youtube.googleapis.com"


class LoadThread(QThread):
    videos_ready = Signal(list)
    failed = Signal(str)

    def __init__(self, playlist_input: str, api_key: str, parent=None):
        super().__init__(parent)
        self._input = playlist_input
        self._key = api_key

    def run(self) -> None:
        try:
            videos = fetch_playlist(self._input, self._key)
            self.videos_ready.emit(videos)
        except YouTubeError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001 — surface any failure to the UI
            self.failed.emit(f"{type(e).__name__}: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Randomizer")
        self.resize(900, 720)
        self._order: list[Video] = []
        self._model = PlaylistModel(self)
        self._thread: LoadThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        self.playlist_input = QLineEdit()
        self.playlist_input.setPlaceholderText("Paste a YouTube playlist URL or ID…")
        self.playlist_input.returnPressed.connect(self.on_load)
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.on_load)
        self.reshuffle_btn = QPushButton("Shuffle")
        self.reshuffle_btn.clicked.connect(self.on_reshuffle)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search…")
        self.search_input.textChanged.connect(self.on_search)
        top.addWidget(QLabel("Playlist:"))
        top.addWidget(self.playlist_input, 3)
        top.addWidget(self.load_btn)
        top.addWidget(self.reshuffle_btn)
        top.addWidget(self.search_input, 2)
        root.addLayout(top)

        self.player = PlayerView()
        root.addWidget(self.player, 3)

        controls = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.clicked.connect(self.player.prev)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.player.next)
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.next_btn)
        controls.addStretch()
        root.addLayout(controls)

        self.list_view = QListView()
        self.list_view.setModel(self._model)
        self.list_view.clicked.connect(self.on_row_clicked)
        root.addWidget(self.list_view, 2)

    def _api_key(self) -> str | None:
        key = get_api_key()
        if key:
            return key
        key, ok = QInputDialog.getText(
            self,
            "YouTube Data API key",
            (
                "A YouTube Data API v3 key is required.\n"
                f"Get one at:\n{CONSOLE_URL}\n\nPaste your key:"
            ),
        )
        if ok and key.strip():
            set_api_key(key.strip())
            return key.strip()
        return None

    def on_load(self) -> None:
        text = self.playlist_input.text().strip()
        if not text:
            return
        key = self._api_key()
        if not key:
            QMessageBox.warning(
                self, "No API key", "A YouTube Data API key is required to load playlists."
            )
            return
        self.load_btn.setEnabled(False)
        self._thread = LoadThread(text, key, self)
        self._thread.videos_ready.connect(self._on_loaded)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _on_loaded(self, videos: list) -> None:
        self.load_btn.setEnabled(True)
        if not videos:
            QMessageBox.information(self, "Empty", "No videos found in that playlist.")
            return
        self._order = shuffle(videos)
        self._apply_order()

    def _on_failed(self, message: str) -> None:
        self.load_btn.setEnabled(True)
        QMessageBox.critical(self, "Load failed", message)

    def on_reshuffle(self) -> None:
        if self._order:
            self._order = shuffle(self._order)
            self._apply_order()

    def _apply_order(self) -> None:
        self._model.set_videos(self._order)
        self.player.play_list(self._model.ids(), 0)

    def on_search(self, text: str) -> None:
        if not self._order:
            return
        self._model.set_videos(search(self._order, text))

    def on_row_clicked(self, index) -> None:
        v = self._model.video_at(index.row())
        if v:
            self.player.play_video(v.id)
