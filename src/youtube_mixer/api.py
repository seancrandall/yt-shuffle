"""YouTube Data API v3 client for fetching playlist contents.

Lists a playlist's videos (IDs, titles, thumbnails) by paginating the ``playlistItems.list``
endpoint at 50 items per page. Accepts a playlist URL or a bare playlist ID.

A user-supplied API key is required; it is passed as the ``key`` query parameter. Quota cost
is ~1 unit per 50 items (free tier: 10,000 units/day).
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from .playlist import Video

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_RESULTS = 50


class YouTubeError(Exception):
    """Raised for input-parsing or API-level errors surfaced to the UI."""


def parse_playlist_id(value: str) -> str:
    """Extract a playlist ID from a YouTube URL, or accept a bare ID.

    Handles ``playlist?list=``, ``watch?v=...&list=``, and ``youtu.be/...?list=`` forms.
    """
    value = value.strip()
    if not value:
        raise YouTubeError("No playlist provided.")
    if "list=" in value:
        params = parse_qs(urlparse(value).query)
        ids = params.get("list")
        if ids and ids[0]:
            return ids[0]
        raise YouTubeError(f"Could not find a playlist ID in URL: {value!r}")
    # No list= param: accept as a bare playlist ID only if it isn't a URL.
    if "://" in value or value.startswith("www.") or "youtube.com" in value or "youtu.be" in value:
        raise YouTubeError(f"Could not find a playlist ID in URL: {value!r}")
    return value


def fetch_playlist(
    playlist_input: str,
    api_key: str,
    *,
    client: httpx.Client | None = None,
) -> list[Video]:
    """Fetch all videos in a playlist as a list of :class:`Video`.

    If ``client`` is omitted, a short-lived ``httpx.Client`` is created and closed here.
    Passing a client in (e.g. an ``httpx.MockTransport`` for tests) avoids that.
    """
    playlist_id = parse_playlist_id(playlist_input)
    if not api_key:
        raise YouTubeError("Missing YouTube Data API key.")

    own_client = client is None
    if client is None:
        client = httpx.Client(timeout=30.0)
    try:
        videos: list[Video] = []
        page_token: str | None = None
        while True:
            params: dict[str, str] = {
                "part": "snippet",
                "maxResults": str(MAX_RESULTS),
                "playlistId": playlist_id,
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            resp = client.get(f"{YOUTUBE_API_BASE}/playlistItems", params=params)
            if resp.status_code != 200:
                try:
                    message = resp.json().get("error", {}).get("message", resp.text)
                except ValueError:
                    message = resp.text
                raise YouTubeError(f"YouTube API error {resp.status_code}: {message}")

            data = resp.json()
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = snippet.get("resourceId", {}).get("videoId")
                if not video_id:
                    continue
                thumbs = snippet.get("thumbnails", {}) or {}
                thumb = (thumbs.get("medium") or thumbs.get("default") or {})
                videos.append(
                    Video(
                        id=video_id,
                        title=snippet.get("title", "") or "",
                        thumbnail_url=thumb.get("url"),
                    )
                )

            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return videos
    finally:
        if own_client:
            client.close()


def fetch_playlist_meta(
    playlist_id: str,
    api_key: str,
    *,
    client: httpx.Client | None = None,
) -> str:
    """Fetch a playlist's title via the ``playlists.list`` endpoint.

    Returns the playlist's ``snippet.title``, or ``""`` if the playlist is not
    found / has no items (so callers can fall back to the id as the display name).
    Uses the same ``client`` injection seam as :func:`fetch_playlist`.
    """
    if not api_key:
        raise YouTubeError("Missing YouTube Data API key.")

    own_client = client is None
    if client is None:
        client = httpx.Client(timeout=30.0)
    try:
        resp = client.get(
            f"{YOUTUBE_API_BASE}/playlists",
            params={"part": "snippet", "id": playlist_id, "key": api_key},
        )
        if resp.status_code != 200:
            try:
                message = resp.json().get("error", {}).get("message", resp.text)
            except ValueError:
                message = resp.text
            raise YouTubeError(f"YouTube API error {resp.status_code}: {message}")

        items = resp.json().get("items", [])
        if not items:
            return ""
        return items[0].get("snippet", {}).get("title", "") or ""
    finally:
        if own_client:
            client.close()
