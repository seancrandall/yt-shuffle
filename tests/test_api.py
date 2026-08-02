import httpx
import pytest

from youtube_mixer.api import (
    YouTubeError,
    fetch_playlist,
    fetch_playlist_meta,
    parse_playlist_id,
)


def _client(pages_by_token: dict):
    """httpx client backed by a MockTransport, keyed by the pageToken query param (None=first)."""
    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        page = pages_by_token.get(token)
        if page is None:
            return httpx.Response(403, json={"error": {"message": "no page for token"}})
        return httpx.Response(200, json=page)
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.youtube.com/playlist?list=PLabc", "PLabc"),
        ("https://www.youtube.com/watch?v=xyz&list=PLabc", "PLabc"),
        ("https://youtu.be/xyz?list=PLabc", "PLabc"),
        ("PLabc", "PLabc"),
        ("  PLabc  ", "PLabc"),
    ],
)
def test_parse_playlist_id(value, expected):
    assert parse_playlist_id(value) == expected


def test_parse_playlist_id_empty_raises():
    with pytest.raises(YouTubeError):
        parse_playlist_id("   ")


def test_parse_playlist_id_url_without_list_raises():
    with pytest.raises(YouTubeError):
        parse_playlist_id("https://www.youtube.com/watch?v=xyz")


def test_fetch_playlist_paginates_and_maps_videos():
    client = _client({
        None: {
            "items": [
                {"snippet": {"title": "A", "resourceId": {"videoId": "v1"},
                             "thumbnails": {"default": {"url": "u1"}}}},
            ],
            "nextPageToken": "T2",
        },
        "T2": {
            "items": [
                {"snippet": {"title": "B", "resourceId": {"videoId": "v2"}}},
            ],
        },
    })
    videos = fetch_playlist("PLabc", "KEY", client=client)
    assert [v.id for v in videos] == ["v1", "v2"]
    assert videos[0].title == "A"
    assert videos[0].thumbnail_url == "u1"
    assert videos[1].thumbnail_url is None


def test_fetch_playlist_skips_items_without_video_id():
    client = _client({
        None: {"items": [
            {"snippet": {"title": "good", "resourceId": {"videoId": "v1"}}},
            {"snippet": {"title": "bad", "resourceId": {}}},
        ]},
    })
    assert [v.id for v in fetch_playlist("PLabc", "KEY", client=client)] == ["v1"]


def test_fetch_playlist_api_error_raises():
    client = _client({None: None})
    with pytest.raises(YouTubeError):
        fetch_playlist("PLabc", "KEY", client=client)


def test_fetch_playlist_missing_key_raises():
    with pytest.raises(YouTubeError):
        fetch_playlist("PLabc", "")


def _meta_client(title_by_id: dict, *, status: int = 200):
    """MockTransport client for playlists.list, keyed by the id query param."""
    def handler(request: httpx.Request) -> httpx.Response:
        pid = request.url.params.get("id")
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "boom"}})
        title = title_by_id.get(pid)
        if title is None:
            return httpx.Response(200, json={"items": []})
        return httpx.Response(200, json={"items": [{"snippet": {"title": title}}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_playlist_meta_returns_title():
    client = _meta_client({"PLabc": "My Mix"})
    assert fetch_playlist_meta("PLabc", "KEY", client=client) == "My Mix"


def test_fetch_playlist_meta_empty_when_not_found():
    client = _meta_client({})
    assert fetch_playlist_meta("PLmissing", "KEY", client=client) == ""


def test_fetch_playlist_meta_api_error_raises():
    client = _meta_client({}, status=403)
    with pytest.raises(YouTubeError):
        fetch_playlist_meta("PLabc", "KEY", client=client)


def test_fetch_playlist_meta_missing_key_raises():
    with pytest.raises(YouTubeError):
        fetch_playlist_meta("PLabc", "")
