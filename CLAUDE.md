# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A native desktop "YouTube Randomizer." It exists because YouTube's built-in playlist shuffle is
broken for long playlists — it tends to grab ~10 videos and loop them instead of covering the
whole list. This app fetches the full playlist and does a real **Fisher–Yates shuffle** so every
video plays once before any repeats. Inspired by https://youtube-playlist-randomizer.bitbucket.io/,
but as a native app. Licensed MIT.

## Stack

- **Python 3.10+ / PySide6 / QtWebEngine** (embedded Chromium hosts the YouTube IFrame Player).
- **httpx** for the YouTube Data API v3 calls. **platformdirs** for config storage.
- src layout, setuptools build. Dev tooling: pytest + pytest-qt, ruff.

## Commands

```bash
# one-time dev setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# run the app
youtube-mixer                       # console script
python -m youtube_mixer             # equivalent

# tests / lint
pytest                              # all tests
pytest tests/test_shuffle.py        # single file
pytest tests/test_shuffle.py::test_shuffle_seed_is_reproducible   # single test
ruff check .                        # lint
```

The app needs a **YouTube Data API v3 key**, prompted on first load and stored in the OS user
config dir (`~/.config/youtube-mixer/config.json` on Linux). See README for how to get one.

## Architecture

The app is a Qt desktop app split into data, player, and UI layers. The key cross-file flow:

`app.py` (MainWindow) orchestrates everything:
- User pastes a playlist URL/ID → `LoadThread` (a QThread) calls `api.fetch_playlist` off the UI
  thread → emits the `list[Video]` back via a signal.
- `playlist.shuffle` does a full-coverage Fisher–Yates shuffle of the entire list (the core fix;
  optional `seed` for reproducibility). The shuffled order is the canonical playback order.
- `PlaylistModel` (a `QAbstractListModel` in `models.py`) backs the bottom `QListView`; it exposes
  display title + `ID_ROLE`/`THUMB_ROLE`. Thumbnails are fetched async via
  `QNetworkAccessManager` and **cached by video ID** so re-shuffle/search does not refetch.
- `PlayerView` (a `QWebEngineView` in `player.py`) loads the bundled `player.html` (package data,
  shipped inside the package for packaging robustness) which hosts the YouTube IFrame Player API.
  Python drives playback via `page.runJavaScript(...)` calling `window.playVideo` /
  `playList` / `next` / `prev`. Calls before page load are buffered in Python; the page itself
  queues calls until the IFrame API player is ready (two-stage buffering).
- **Auto-advance + current-track signaling:** the page auto-advances to the next shuffled video
  on the IFrame API's `onStateChange` ENDED event (JS-side, no Python round-trip). A `QtWebChannel`
  bridge (`_PlayerBridge` registered as `"bridge"`) lets the page call back
  `bridge.currentChanged(videoId)` whenever the now-playing video changes; `PlayerView.currentChanged`
  forwards it to `MainWindow.on_current_changed`, which selects the matching row in the list.
  `playVideo(id)` jumps to that id *within* the existing shuffled list (preserving order) so
  next/prev and auto-advance continue through the full playlist after a manual row click.

Cross-cutting details worth knowing:
- `api.fetch_playlist` accepts an injected `httpx.Client` (used in tests with `httpx.MockTransport`
  keyed by the `pageToken` query param). Don't add network calls that bypass this seam if you want
  them testable.
- `playlist.Video` is a frozen dataclass — pass it around by value, never mutate.
- Search (`playlist.search`) only filters the *display* model; it does not change the player's
  shuffled order. Next/prev always walk the full shuffled order.

## License

MIT — see `LICENSE`. PySide6 is LGPL (compatible).