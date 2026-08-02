"""Main application window: playlist input, embedded player, and shuffled list.

Loading a playlist runs the (synchronous, network) fetch on a QThread so the UI stays
responsive; the resulting videos are shuffled (full-coverage Fisher–Yates) before display.
"""

from __future__ import annotations

import httpx
from PySide6.QtCore import QSize, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from .api import YouTubeError, fetch_playlist, fetch_playlist_meta, parse_playlist_id
from .models import ID_ROLE, PlaylistModel
from .player import PlayerView
from .playlist import Video, search, shuffle
from .settings import (
    add_playlist,
    get_api_key,
    get_auto_advance,
    get_playlists,
    set_api_key,
    set_auto_advance,
)

CONSOLE_URL = "https://console.cloud.google.com/apis/library/youtube.googleapis.com"


class LoadThread(QThread):
    videos_ready = Signal(list, str, str)  # videos, playlist_id, name
    failed = Signal(str)

    def __init__(self, playlist_input: str, api_key: str, parent=None):
        super().__init__(parent)
        self._input = playlist_input
        self._key = api_key

    def run(self) -> None:
        try:
            playlist_id = parse_playlist_id(self._input)
            client = httpx.Client(timeout=30.0)
            try:
                videos = fetch_playlist(playlist_id, self._key, client=client)
                name = fetch_playlist_meta(playlist_id, self._key, client=client)
            finally:
                client.close()
            self.videos_ready.emit(videos, playlist_id, name)
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
        self._pending_input: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        self.playlist_input = QComboBox()
        self.playlist_input.setEditable(True)
        self.playlist_input.setInsertPolicy(QComboBox.NoInsert)
        self.playlist_input.lineEdit().setPlaceholderText("Paste a YouTube playlist URL or ID…")
        self.playlist_input.lineEdit().returnPressed.connect(self.on_load)
        # Picking a saved playlist from the dropdown loads it directly by id.
        self.playlist_input.activated.connect(self._load_history_item)
        self._refresh_playlist_combo()
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.on_load)
        self.reshuffle_btn = QPushButton("Shuffle")
        self.reshuffle_btn.clicked.connect(self.on_reshuffle)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search…")
        self.search_input.textChanged.connect(self.on_search)
        self.auto_advance_cb = QCheckBox("Auto-advance")
        self.auto_advance_cb.setChecked(get_auto_advance())
        self.auto_advance_cb.toggled.connect(self.on_auto_advance_toggled)
        top.addWidget(QLabel("Playlist:"))
        top.addWidget(self.playlist_input, 3)
        top.addWidget(self.load_btn)
        top.addWidget(self.reshuffle_btn)
        top.addWidget(self.search_input, 2)
        top.addWidget(self.auto_advance_cb)
        root.addLayout(top)

        self.player = PlayerView()
        self.player.set_auto_advance(self.auto_advance_cb.isChecked())
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
        self.list_view.setIconSize(QSize(120, 68))
        self.list_view.setUniformItemSizes(True)
        self.list_view.setSpacing(2)
        self.list_view.clicked.connect(self.on_row_clicked)
        root.addWidget(self.list_view, 2)

        # Highlight the now-playing row as the player advances (manual or auto-advance).
        self.player.currentChanged.connect(self.on_current_changed)

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
        """Load from the combo's typed text (a pasted URL or bare playlist ID)."""
        text = self.playlist_input.currentText().strip()
        if not text:
            return
        self._start_load(text)

    def _load_history_item(self, index: int) -> None:
        """Load a saved playlist chosen from the dropdown (by its stored id)."""
        pid = self.playlist_input.itemData(index)
        if not pid:
            return
        self._start_load(pid)

    def _refresh_playlist_combo(self, select_id: str | None = None) -> None:
        """Rebuild the combo's saved-playlist items (text=name, data=id)."""
        self.playlist_input.blockSignals(True)
        typed = self.playlist_input.currentText()
        self.playlist_input.clear()
        for p in get_playlists():
            self.playlist_input.addItem(p["name"], p["id"])
        if select_id is not None:
            idx = self.playlist_input.findData(select_id)
            if idx >= 0:
                self.playlist_input.setCurrentIndex(idx)
        else:
            self.playlist_input.setEditText(typed)
        self.playlist_input.blockSignals(False)

    def _start_load(self, playlist_input: str) -> None:
        key = self._api_key()
        if not key:
            QMessageBox.warning(
                self, "No API key", "A YouTube Data API key is required to load playlists."
            )
            return
        self._pending_input = playlist_input
        self.load_btn.setEnabled(False)
        self._thread = LoadThread(playlist_input, key, self)
        self._thread.videos_ready.connect(self._on_loaded)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _on_loaded(self, videos: list, playlist_id: str, name: str) -> None:
        self.load_btn.setEnabled(True)
        if not videos:
            QMessageBox.information(self, "Empty", "No videos found in that playlist.")
            return
        # Save to history (deduped by id) and reflect it in the combo by name.
        url = self._pending_input if "://" in self._pending_input else None
        add_playlist(playlist_id, name or playlist_id, url=url)
        self._refresh_playlist_combo(select_id=playlist_id)
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

    def on_auto_advance_toggled(self, enabled: bool) -> None:
        set_auto_advance(enabled)
        self.player.set_auto_advance(enabled)

    def on_current_changed(self, video_id: str) -> None:
        """Select the now-playing row in the list (if currently visible)."""
        for i in range(self._model.rowCount()):
            if self._model.data(self._model.index(i, 0), ID_ROLE) == video_id:
                self.list_view.setCurrentIndex(self._model.index(i, 0))
                return
