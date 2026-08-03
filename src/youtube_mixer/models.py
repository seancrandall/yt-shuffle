"""Qt model backing the shuffled-playlist list view.

Exposes the display title plus custom roles for the video ID and (async-fetched) thumbnail.
Thumbnails are fetched lazily via QNetworkAccessManager and cached by video ID so re-shuffling
or filtering does not refetch them.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from .playlist import Video

THUMB_ROLE = Qt.UserRole + 1
ID_ROLE = Qt.UserRole + 2

# Thumbnails are cached scaled to ~2x the list icon size (240x136 — crisp on HiDPI) rather
# than the source resolution (YouTube "medium" is 320x180, ~230 KB per pixmap), so a long
# playlist costs tens of MB of pixmaps instead of hundreds. The cache is also capped so
# loading many different playlists can't grow it without bound; evicted entries refetch
# on the next shuffle/search (set_videos only fetches ids not already cached).
THUMB_PIXEL_SIZE = QSize(240, 136)
MAX_THUMBS = 3000


class PlaylistModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._videos: list[Video] = []
        self._thumbs: dict[str, QPixmap] = {}
        self._nam = QNetworkAccessManager(self)

    def set_videos(self, videos: list[Video]) -> None:
        self.beginResetModel()
        self._videos = list(videos)
        self.endResetModel()
        for v in self._videos:
            if v.thumbnail_url and v.id not in self._thumbs:
                self._fetch_thumb(v)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._videos)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._videos)):
            return None
        v = self._videos[index.row()]
        if role == Qt.DisplayRole:
            return f"{index.row() + 1}. {v.title}"
        if role == Qt.DecorationRole:
            pix = self._thumbs.get(v.id)
            return QIcon(pix) if pix is not None else None
        if role == Qt.ToolTipRole:
            return v.title
        if role == THUMB_ROLE:
            return self._thumbs.get(v.id)
        if role == ID_ROLE:
            return v.id
        if role == Qt.SizeHintRole:
            return QSize(0, 72)
        return None

    def video_at(self, row: int) -> Video | None:
        return self._videos[row] if 0 <= row < len(self._videos) else None

    def ids(self) -> list[str]:
        return [v.id for v in self._videos]

    def _fetch_thumb(self, v: Video) -> None:
        reply = self._nam.get(QNetworkRequest(QUrl(v.thumbnail_url)))
        reply.finished.connect(lambda r=reply, vid=v.id: self._on_thumb(r, vid))

    def _on_thumb(self, reply, vid: str) -> None:
        reply.deleteLater()
        data = reply.readAll()
        if not data:
            return
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        if not pix.isNull():
            # Store scaled-to-display-size so the cache holds small pixmaps, not the full
            # source image; the original large pixmap is dropped (no remaining reference).
            pix = pix.scaled(THUMB_PIXEL_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._thumbs[vid] = pix
        self._prune_thumbs()
        for i, v in enumerate(self._videos):
            if v.id == vid:
                idx = self.index(i, 0)
                self.dataChanged.emit(idx, idx, [THUMB_ROLE, Qt.DecorationRole])
                break

    def _prune_thumbs(self) -> None:
        """Bound the thumbnail cache (FIFO by fetch order — most recent playlist last)."""
        while len(self._thumbs) > MAX_THUMBS:
            self._thumbs.pop(next(iter(self._thumbs)))
