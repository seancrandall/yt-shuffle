"""Main application window: playlist input, embedded player, and shuffled list.

Loading a playlist runs the (synchronous, network) fetch on a QThread so the UI stays
responsive; the resulting videos are shuffled (full-coverage Fisher–Yates) before display.
"""

from __future__ import annotations

import httpx
from PySide6.QtCore import QByteArray, QEvent, QSize, Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
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
    get_geometry,
    get_last_playlist_id,
    get_playlists,
    get_resolution,
    set_api_key,
    set_auto_advance,
    set_geometry,
    set_last_playlist_id,
    set_resolution,
)

CONSOLE_URL = "https://console.cloud.google.com/apis/library/youtube.googleapis.com"

# Player pixel size targeted per quality. YouTube caps embedded quality by the player's
# on-screen size, so selecting a resolution resizes the window to give the player (close to)
# these dimensions — clamped to the available screen. The player shares vertical space with
# the playlist list (stretch 3:2) plus the top bar and controls, so the window is sized taller
# than the raw resolution so the *player* reaches it.
QUALITY_PLAYER_SIZE = {
    "medium": (640, 360),
    "hd720": (1280, 720),
    "hd1080": (1920, 1080),
    "hd1440": (2560, 1440),
}


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
        self._canonical: list[Video] = []  # original fetched order (never mutated)
        self._shuffled = False  # whether _order is currently shuffled vs canonical
        self._current_id = ""  # id of the now-playing video (for reorder-without-restart)
        self._model = PlaylistModel(self)
        self._thread: LoadThread | None = None
        self._pending_input: str = ""
        self._pending_autoplay = True
        self._pending_silent = False
        self._build_ui()
        # Restore last window position/size before the first show.
        geo = get_geometry()
        if geo:
            try:
                self.restoreGeometry(QByteArray(bytes.fromhex(geo)))
            except (ValueError, TypeError):
                pass
        # Application-wide key filter for media hotkeys (Space/Ctrl+arrows/Ctrl+S) so they
        # work regardless of focus, while leaving typing in the search/combo box alone.
        QApplication.instance().installEventFilter(self)
        # Auto-load the last-used playlist on launch (but don't auto-play it). Skipped when
        # there's no stored API key (we don't want to prompt on launch) or no last playlist.
        last = get_last_playlist_id()
        if last and get_api_key():
            self._start_load(last, autoplay=False, silent=True)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        self._top_bar = QWidget()
        top = QVBoxLayout(self._top_bar)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        # Row 1 — playlist entry + load/manage (the primary action).
        row1 = QHBoxLayout()
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
        row1.addWidget(QLabel("Playlist:"))
        row1.addWidget(self.playlist_input, 1)
        row1.addWidget(self.load_btn)
        row1.addWidget(self.manage_btn)
        top.addLayout(row1)

        # Row 2 — secondary controls, on their own line so the bar fits portrait widths.
        row2 = QHBoxLayout()
        self.shuffle_btn = QPushButton("Shuffle")
        self.shuffle_btn.setToolTip("Toggle between shuffled and canonical (original) order")
        self.shuffle_btn.clicked.connect(self.on_toggle_shuffle)
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
        row2.addWidget(self.shuffle_btn)
        row2.addWidget(self.search_input, 1)
        row2.addWidget(self.auto_advance_cb)
        row2.addWidget(QLabel("Quality:"))
        row2.addWidget(self.quality_combo)
        top.addLayout(row2)
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

    def closeEvent(self, event):
        # Persist window position/size for next launch (skip while fullscreen — the
        # normal geometry is what we want to restore, not the fullscreen one).
        if not self.isFullScreen():
            try:
                set_geometry(bytes(self.saveGeometry()).hex())
            except (OSError, ValueError):
                pass
        super().closeEvent(event)

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

    def _start_load(self, playlist_input: str, *, autoplay: bool = True,
                     silent: bool = False) -> None:
        key = self._api_key() if not silent else get_api_key()
        if not key:
            if not silent:
                QMessageBox.warning(
                    self, "No API key", "A YouTube Data API key is required to load playlists."
                )
            return
        self._pending_input = playlist_input
        self._pending_autoplay = autoplay
        self._pending_silent = silent
        self.load_btn.setEnabled(False)
        self._thread = LoadThread(playlist_input, key, self)
        self._thread.videos_ready.connect(self._on_loaded)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _on_loaded(self, videos: list, playlist_id: str, name: str) -> None:
        self.load_btn.setEnabled(True)
        if not videos:
            if not self._pending_silent:
                QMessageBox.information(self, "Empty", "No videos found in that playlist.")
            return
        # Save to history (deduped by id) and reflect it in the combo by name.
        url = self._pending_input if "://" in self._pending_input else None
        add_playlist(playlist_id, name or playlist_id, url=url)
        set_last_playlist_id(playlist_id)
        self._refresh_playlist_combo(select_id=playlist_id)
        self._canonical = list(videos)  # preserve original order for unshuffle
        self._order = shuffle(videos)
        self._shuffled = True
        self._current_id = ""
        self._update_shuffle_button()
        self._apply_order(autoplay=self._pending_autoplay)

    def _on_failed(self, message: str) -> None:
        self.load_btn.setEnabled(True)
        # Silent loads (the launch auto-load) don't pop a modal — e.g. no network on start.
        if not self._pending_silent:
            QMessageBox.critical(self, "Load failed", message)

    def on_toggle_shuffle(self) -> None:
        """Toggle the Shuffle button: shuffle the canonical order, or restore it.

        Switching either way keeps the currently-playing video going (no restart) and
        re-points next/prev into the new order at the current video's position — so you
        can flip between random and original order mid-playback."""
        if not self._order:
            return
        if self._shuffled:
            self._order = list(self._canonical)
            self._shuffled = False
        else:
            self._order = shuffle(self._canonical)
            self._shuffled = True
        self._update_shuffle_button()
        self._apply_order_preserve()

    def _update_shuffle_button(self) -> None:
        # Label = the action clicking will take: unshuffle while shuffled, shuffle while ordered.
        self.shuffle_btn.setText("Unshuffle" if self._shuffled else "Shuffle")

    def _order_ids(self) -> list[str]:
        return [v.id for v in self._order]

    def _current_index(self) -> int:
        """Index of the now-playing video in the current order (0 if none/unknown)."""
        if self._current_id:
            for i, v in enumerate(self._order):
                if v.id == self._current_id:
                    return i
        return 0

    def _refresh_model(self) -> None:
        """Show the current order in the list, filtered by any active search text."""
        text = self.search_input.text().strip()
        self._model.set_videos(search(self._order, text) if text else self._order)

    def _apply_order(self, *, autoplay: bool = True) -> None:
        """Initial apply: refresh the list and start (or cue) the player at the top of the order."""
        self._refresh_model()
        if autoplay:
            self.player.play_list(self._order_ids(), 0)
        else:
            self.player.cue_list(self._order_ids(), 0)

    def _apply_order_preserve(self) -> None:
        """Reorder without restarting playback: keep the current video playing and point
        next/prev into the new order at its position (used by the shuffle toggle)."""
        self._refresh_model()
        self.player.set_list(self._order_ids(), self._current_index())

    def on_search(self, text: str) -> None:
        if not self._order:
            return
        self._refresh_model()

    def on_row_clicked(self, index) -> None:
        v = self._model.video_at(index.row())
        if v:
            self.player.play_video(v.id)

    def on_auto_advance_toggled(self, enabled: bool) -> None:
        set_auto_advance(enabled)
        self.player.set_auto_advance(enabled)

    def on_current_changed(self, video_id: str) -> None:
        """Track the now-playing video and select its row in the list (if visible)."""
        self._current_id = video_id
        for i in range(self._model.rowCount()):
            if self._model.data(self._model.index(i, 0), ID_ROLE) == video_id:
                self.list_view.setCurrentIndex(self._model.index(i, 0))
                return

    def on_quality_changed(self, _index: int) -> None:
        """Apply the chosen resolution; cinema mode hides chrome for a big player, the numeric
        tiers resize the window so the player is large enough for YouTube to serve that quality."""
        key = self.quality_combo.currentData()
        if not key:
            return
        self._cinema = key == "cinema"
        set_resolution(key)
        self.player.set_quality(key)
        if key != "cinema":
            self._resize_for_quality(key)
        self._apply_layout()

    def _resize_for_quality(self, key: str) -> None:
        """Resize the window so the player reaches the chosen resolution's size, clamped to
        the available screen (so it still fits a small/portrait display)."""
        if self.isFullScreen():
            return
        target = QUALITY_PLAYER_SIZE.get(key)
        if not target:
            return
        res_w, res_h = target
        # Player shares vertical space with the playlist list (stretch 3:2) plus the two
        # control rows (~80px), so make the window tall enough that the *player* hits res_h.
        window_w = res_w + 24
        window_h = int(res_h * 5 / 3) + 90
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            window_w = min(window_w, avail.width())
            window_h = min(window_h, avail.height())
        self.resize(window_w, window_h)

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

    def _is_text_input(self, widget) -> bool:
        """True when the focused widget is a text entry field (so we leave keystrokes alone)."""
        if isinstance(widget, QLineEdit):
            return True
        if isinstance(widget, QComboBox) and widget.isEditable():
            return True
        return False

    def eventFilter(self, obj, event):
        """Media hotkeys that work from anywhere, without fighting the search/combo box.

        Space        play/pause (but if the player itself has focus, let the YouTube embed
                     handle Space — otherwise both it and we would toggle and cancel out).
        Ctrl+Right   next track      Ctrl+Left   previous track
        Ctrl+S       shuffle / unshuffle toggle

        All are ignored while typing in a text field so the keys still type/edit normally.
        """
        if event.type() != QEvent.KeyPress:
            return False
        focus = QApplication.focusWidget()
        if self._is_text_input(focus):
            return False  # never hijack typing
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key_Space and mods == Qt.NoModifier:
            # The embedded player already play/pauses on Space when it has focus; let it, to
            # avoid a double-toggle. Buttons/checkboxes also use Space (activate/toggle).
            if focus is self.player or isinstance(focus, (QPushButton, QCheckBox, QComboBox)):
                return False
            self.player.toggle_play_pause()
            return True
        if key == Qt.Key_Right and mods == Qt.ControlModifier:
            self.player.next()
            return True
        if key == Qt.Key_Left and mods == Qt.ControlModifier:
            self.player.prev()
            return True
        if key == Qt.Key_S and mods == Qt.ControlModifier:
            self.on_toggle_shuffle()
            return True
        return False
