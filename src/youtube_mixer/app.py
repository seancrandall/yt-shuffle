"""Main application window: playlist input, embedded player, and shuffled list.

Loading a playlist runs the (synchronous, network) fetch on a QThread so the UI stays
responsive; the resulting videos are shuffled (full-coverage Fisher–Yates) before display.
"""

from __future__ import annotations

import httpx
from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut
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
from .manager import PlaylistManagerDialog
from .models import ID_ROLE, PlaylistModel
from .player import PlayerView
from .playlist import Video, search, shuffle
from .settings import (
    add_playlist,
    get_api_key,
    get_auto_advance,
    get_playlists,
    get_resolution,
    set_api_key,
    set_auto_advance,
    set_resolution,
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

        self._top_bar = QWidget()
        top = QHBoxLayout(self._top_bar)
        top.setContentsMargins(0, 0, 0, 0)
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
        self.manage_btn = QPushButton("Manage…")
        self.manage_btn.clicked.connect(self._open_manager)
        self.reshuffle_btn = QPushButton("Shuffle")
        self.reshuffle_btn.clicked.connect(self.on_reshuffle)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search…")
        self.search_input.textChanged.connect(self.on_search)
        self.auto_advance_cb = QCheckBox("Auto-advance")
        self.auto_advance_cb.setChecked(get_auto_advance())
        self.auto_advance_cb.toggled.connect(self.on_auto_advance_toggled)
        self.quality_combo = QComboBox()
        for label, key in (
            ("360p", "medium"),
            ("720p", "hd720"),
            ("1080p", "hd1080"),
            ("1440p", "hd1440"),
            ("Cinema mode", "cinema"),
        ):
            self.quality_combo.addItem(label, key)
        self.quality_combo.currentIndexChanged.connect(self.on_quality_changed)
        top.addWidget(QLabel("Playlist:"))
        top.addWidget(self.playlist_input, 3)
        top.addWidget(self.load_btn)
        top.addWidget(self.manage_btn)
        top.addWidget(self.reshuffle_btn)
        top.addWidget(self.search_input, 2)
        top.addWidget(self.auto_advance_cb)
        top.addWidget(QLabel("Quality:"))
        top.addWidget(self.quality_combo)
        root.addWidget(self._top_bar)

        self.player = PlayerView()
        self.player.set_auto_advance(self.auto_advance_cb.isChecked())
        root.addWidget(self.player, 3)
        # Restore last resolution without firing the handler during init.
        init_res = get_resolution()
        idx = self.quality_combo.findData(init_res)
        self.quality_combo.blockSignals(True)
        self.quality_combo.setCurrentIndex(max(0, idx))
        self.quality_combo.blockSignals(False)
        self._cinema = init_res == "cinema"
        self.player.set_quality(init_res)

        self._controls_bar = QWidget()
        controls = QHBoxLayout(self._controls_bar)
        controls.setContentsMargins(0, 0, 0, 0)
        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.clicked.connect(self.player.prev)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.player.next)
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.next_btn)
        controls.addStretch()
        root.addWidget(self._controls_bar)

        self.list_view = QListView()
        self.list_view.setModel(self._model)
        self.list_view.setIconSize(QSize(120, 68))
        self.list_view.setUniformItemSizes(True)
        self.list_view.setSpacing(2)
        self.list_view.clicked.connect(self.on_row_clicked)
        root.addWidget(self.list_view, 2)

        # Highlight the now-playing row as the player advances (manual or auto-advance).
        self.player.currentChanged.connect(self.on_current_changed)

        # Floating "Exit" button shown over the player when chrome is hidden
        # (cinema mode / fullscreen) — a visible way out, since Esc isn't discoverable.
        self._exit_btn = QPushButton("✕  Exit", self)
        self._exit_btn.setCursor(Qt.PointingHandCursor)
        self._exit_btn.setStyleSheet(
            "QPushButton { background: rgba(0,0,0,170); color: #fff;"
            " padding: 6px 14px; border: 1px solid rgba(255,255,255,40); border-radius: 6px; }"
            "QPushButton:hover { background: rgba(40,40,40,210); }"
        )
        self._exit_btn.clicked.connect(self._exit_immersive)
        self._exit_btn.hide()

        # F11 toggles fullscreen; Esc exits fullscreen or cinema mode.
        QShortcut(QKeySequence("F11"), self, activated=self.on_toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self, activated=self.on_escape)
        self._apply_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_exit_button()

    def _set_chrome_visible(self, visible: bool) -> None:
        """Show/hide everything except the player (top bar, controls, playlist list)."""
        self._top_bar.setVisible(visible)
        self._controls_bar.setVisible(visible)
        self.list_view.setVisible(visible)

    def _apply_layout(self) -> None:
        """Hide chrome when fullscreen or in cinema mode; otherwise show it."""
        hidden = self.isFullScreen() or self._cinema
        self._set_chrome_visible(not hidden)
        self._exit_btn.setVisible(hidden)
        if hidden:
            self._position_exit_button()

    def _position_exit_button(self) -> None:
        """Pin the floating Exit button to the top-right corner (over the player)."""
        if not self._exit_btn.isVisible():
            return
        self._exit_btn.adjustSize()
        x = max(0, self.width() - self._exit_btn.width() - 14)
        self._exit_btn.move(x, 12)
        self._exit_btn.raise_()

    def _exit_immersive(self) -> None:
        """Leave both fullscreen and cinema mode (the visible way out)."""
        if self.isFullScreen():
            self.showNormal()
        if self._cinema:
            idx = self.quality_combo.findData("hd720")
            self.quality_combo.setCurrentIndex(max(0, idx))  # fires on_quality_changed
        else:
            self._apply_layout()

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

    def _open_manager(self) -> None:
        """Open the Playlist Manager; refresh the combo if anything changed."""
        current_id = self.playlist_input.currentData()
        dlg = PlaylistManagerDialog(self)
        if dlg.exec():
            self._refresh_playlist_combo(select_id=current_id)

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

    def on_quality_changed(self, _index: int) -> None:
        """Apply the chosen resolution; cinema mode also hides chrome for a big player."""
        key = self.quality_combo.currentData()
        if not key:
            return
        self._cinema = key == "cinema"
        set_resolution(key)
        self.player.set_quality(key)
        self._apply_layout()

    def on_toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._apply_layout()

    def on_escape(self) -> None:
        """Esc exits fullscreen, then cinema mode (the selector is hidden in cinema)."""
        if self.isFullScreen():
            self.showNormal()
            self._apply_layout()
            return
        if self._cinema:
            # Drop back to 720p (a safe default for a normal-sized player).
            idx = self.quality_combo.findData("hd720")
            self.quality_combo.setCurrentIndex(max(0, idx))  # fires on_quality_changed
