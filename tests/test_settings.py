"""Tests for saved-playlist and resolution settings (isolated to a temp config file)."""


import pytest

import youtube_mixer.settings as settings


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_path", lambda: cfg)
    return cfg


def test_get_playlists_empty_when_unset(tmp_config):
    assert settings.get_playlists() == []


def test_add_playlist_appends_and_dedupes(tmp_config):
    settings.add_playlist("PL1", "Rock")
    settings.add_playlist("PL2", "Jazz")
    assert [p["id"] for p in settings.get_playlists()] == ["PL1", "PL2"]
    # Re-adding PL1 updates the name instead of duplicating.
    settings.add_playlist("PL1", "Rock Updated")
    items = settings.get_playlists()
    assert [p["id"] for p in items] == ["PL1", "PL2"]
    assert items[0]["name"] == "Rock Updated"


def test_add_playlist_falls_back_to_id_as_name(tmp_config):
    settings.add_playlist("PL1", "")
    assert settings.get_playlists()[0]["name"] == "PL1"


def test_remove_playlist(tmp_config):
    settings.add_playlist("PL1", "Rock")
    settings.add_playlist("PL2", "Jazz")
    settings.remove_playlist("PL1")
    assert [p["id"] for p in settings.get_playlists()] == ["PL2"]


def test_rename_playlist(tmp_config):
    settings.add_playlist("PL1", "Rock")
    settings.rename_playlist("PL1", "Classic Rock")
    assert settings.get_playlists()[0]["name"] == "Classic Rock"


def test_move_playlist(tmp_config):
    for i in range(3):
        settings.add_playlist(f"PL{i}", f"Name{i}")
    settings.move_playlist("PL0", 2)  # PL0 -> end
    assert [p["id"] for p in settings.get_playlists()] == ["PL1", "PL2", "PL0"]
    settings.move_playlist("PL0", 0)  # back to front
    assert [p["id"] for p in settings.get_playlists()] == ["PL0", "PL1", "PL2"]


def test_move_playlist_clamps_out_of_range(tmp_config):
    settings.add_playlist("PL0", "A")
    settings.add_playlist("PL1", "B")
    settings.move_playlist("PL0", 99)  # clamps to last slot
    assert [p["id"] for p in settings.get_playlists()] == ["PL1", "PL0"]


def test_set_playlists_replaces(tmp_config):
    settings.add_playlist("PL1", "Rock")
    settings.set_playlists([{"id": "PX", "name": "X"}, {"id": "PY", "name": "Y"}])
    assert [p["id"] for p in settings.get_playlists()] == ["PX", "PY"]


def test_get_playlists_ignores_malformed_entries(tmp_config):
    # Write a malformed config directly.
    tmp_config.write_text('{"playlists": [{"id": "OK", "name": "Ok"}, {"name": "no id"}, 5]}')
    assert [p["id"] for p in settings.get_playlists()] == ["OK"]


def test_resolution_default(tmp_config):
    assert settings.get_resolution() == "hd720"


def test_resolution_round_trip(tmp_config):
    for value in settings.RESOLUTIONS:
        settings.set_resolution(value)
        assert settings.get_resolution() == value


def test_resolution_rejects_unknown(tmp_config):
    settings.set_resolution("hd720")
    settings.set_resolution("bogus")
    assert settings.get_resolution() == "hd720"


def test_resolution_falls_back_when_garbage(tmp_config):
    tmp_config.write_text('{"resolution": "not-a-quality"}')
    assert settings.get_resolution() == "hd720"
