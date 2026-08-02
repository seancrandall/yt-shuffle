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
