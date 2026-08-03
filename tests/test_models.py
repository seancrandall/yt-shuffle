from youtube_mixer.models import ID_ROLE, PlaylistModel
from youtube_mixer.playlist import Video


def test_empty_model_has_no_rows():
    model = PlaylistModel()
    assert model.rowCount() == 0
    assert model.ids() == []


def test_set_videos_populates_rows_and_roles():
    model = PlaylistModel()
    model.set_videos([Video(id="1", title="A"), Video(id="2", title="B")])

    assert model.rowCount() == 2
    assert model.ids() == ["1", "2"]
    assert "A" in model.data(model.index(0, 0))
    assert "B" in model.data(model.index(1, 0))
    assert model.data(model.index(0, 0), ID_ROLE) == "1"


def test_video_at_bounds():
    model = PlaylistModel()
    model.set_videos([Video(id="1", title="A")])
    assert model.video_at(0).id == "1"
    assert model.video_at(99) is None
    assert model.video_at(-1) is None


def test_invalid_index_returns_none():
    model = PlaylistModel()
    model.set_videos([Video(id="1", title="A")])
    from PySide6.QtCore import QModelIndex

    assert model.data(QModelIndex()) is None


def test_decoration_and_tooltip_roles():
    from PySide6.QtCore import Qt

    model = PlaylistModel()
    model.set_videos([Video(id="1", title="Hello World")])  # no thumbnail_url -> no fetch
    idx = model.index(0, 0)
    assert model.data(idx, Qt.DecorationRole) is None  # nothing loaded yet
    assert model.data(idx, Qt.ToolTipRole) == "Hello World"


def test_thumb_cache_is_capped():
    from PySide6.QtGui import QPixmap

    from youtube_mixer.models import MAX_THUMBS

    model = PlaylistModel()
    # Overfill the cache directly; _prune_thumbs should keep it at the cap.
    for i in range(MAX_THUMBS + 500):
        model._thumbs[f"id{i}"] = QPixmap(1, 1)
    model._prune_thumbs()
    assert len(model._thumbs) == MAX_THUMBS
    # FIFO: the oldest entries (id0..) were evicted, the newest (id499..) kept.
    assert "id0" not in model._thumbs
    assert f"id{MAX_THUMBS + 499}" in model._thumbs
