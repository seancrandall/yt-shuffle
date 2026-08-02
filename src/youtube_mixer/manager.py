"""Playlist Manager dialog: add / delete / reorder saved playlists.

Shows saved playlists by name (id in the tooltip) and lets the user remove or
reorder them, or add a new one by URL/ID. On accept the edited list is written
back via :func:`settings.set_playlists`.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .api import YouTubeError, fetch_playlist_meta, parse_playlist_id
from .settings import get_api_key, get_playlists, set_playlists


class PlaylistManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playlist Manager")
        self.resize(460, 360)
        self._items: list[dict] = [dict(p) for p in get_playlists()]
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        self.add_btn = QPushButton("Add…")
        self.add_btn.clicked.connect(self._on_add)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        self.up_btn = QPushButton("Move Up")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = QPushButton("Move Down")
        self.down_btn.clicked.connect(lambda: self._move(1))
        for b in (self.add_btn, self.delete_btn, self.up_btn, self.down_btn):
            buttons.addWidget(b)
        buttons.addStretch()
        layout.addLayout(buttons)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    # --- list rendering -----------------------------------------------------

    def _refresh_list(self, select_row: int | None = None) -> None:
        self.list_widget.clear()
        for p in self._items:
            item = QListWidgetItem(p["name"])
            item.setToolTip(f"{p['id']}  —  {p.get('name')}")
            item.setData(0x0100, p["id"])  # Qt.UserRole
            self.list_widget.addItem(item)
        if select_row is not None and 0 <= select_row < self.list_widget.count():
            self.list_widget.setCurrentRow(select_row)

    def _selected_row(self) -> int:
        return self.list_widget.currentRow()

    # --- actions ------------------------------------------------------------

    def _on_add(self) -> None:
        text, ok = QInputDialog.getText(self, "Add playlist", "YouTube playlist URL or ID:")
        if not (ok and text.strip()):
            return
        try:
            pid = parse_playlist_id(text.strip())
        except YouTubeError as e:
            QMessageBox.warning(self, "Invalid playlist", str(e))
            return
        # Skip if already present.
        for p in self._items:
            if p["id"] == pid:
                self._refresh_list(select_row=self._items.index(p))
                return
        name = pid
        key = get_api_key()
        if key:
            try:
                name = fetch_playlist_meta(pid, key) or pid
            except Exception:  # noqa: BLE001 — name is a cosmetic fallback
                name = pid
        self._items.append(
            {"id": pid, "name": name, "url": text.strip() if "://" in text.strip() else None}
        )
        self._refresh_list(select_row=len(self._items) - 1)

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row < 0:
            return
        del self._items[row]
        self._refresh_list(select_row=min(row, len(self._items) - 1) if self._items else None)

    def _move(self, delta: int) -> None:
        row = self._selected_row()
        if row < 0:
            return
        new_row = row + delta
        if not (0 <= new_row < len(self._items)):
            return
        self._items[row], self._items[new_row] = self._items[new_row], self._items[row]
        self._refresh_list(select_row=new_row)

    def _on_accept(self) -> None:
        set_playlists(self._items)
        self.accept()
