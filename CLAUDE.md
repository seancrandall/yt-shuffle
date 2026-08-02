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

# cut a release (bumps version in lockstep; see Versioning below)
python scripts/bump_version.py 0.2.0
```

The app needs a **YouTube Data API v3 key**, prompted on first load and stored in the OS user
config dir (`~/.config/youtube-mixer/config.json` on Linux). See README for how to get one.

## Versioning

Semantic Versioning, pre-1.0 convention (while major is `0`, minors may break). The version has
a **single source of truth**: `youtube_mixer.__version__` in `src/youtube_mixer/__init__.py`.
`pyproject.toml` reads it dynamically (`[tool.setuptools.dynamic] version = {attr = ...}`), so
never set a literal version in `pyproject.toml`. The README's `**Version:**` line must always
match `__version__`; `tests/test_version_sync.py` fails if the README, `__version__`, or the
installed distribution metadata drift. To change the version, run `scripts/bump_version.py
<x.y.z>` — it updates `__init__.py` and the README together and prints the commit/tag commands.

## Architecture

The app is a Qt desktop app split into data, player, and UI layers. The key cross-file flow:

`app.py` (MainWindow) orchestrates everything:
- User pastes a playlist URL/ID → `LoadThread` (a QThread) calls `api.fetch_playlist` off the UI
  thread → emits the `list[Video]` back via a signal.
- `playlist.shuffle` does a full-coverage Fisher–Yates shuffle of the entire list (the core fix;
  optional `seed` for reproducibility). The shuffled order is the canonical playback order.
- `PlaylistModel` (a `QAbstractListModel` in `models.py`) backs the bottom `QListView`; it exposes
  display title, `Qt.DecorationRole` (thumbnail as `QIcon`), `Qt.ToolTipRole` (full title), plus
  `ID_ROLE`/`THUMB_ROLE`. The `QListView` is in list mode with a 120×68 icon size and uniform row
  sizes, so each row shows its thumbnail and the selected/now-playing row is clearly highlighted.
  Thumbnails are fetched async via `QNetworkAccessManager` and **cached by video ID** so
  re-shuffle/search does not refetch; `dataChanged` is emitted for both `THUMB_ROLE` and
  `Qt.DecorationRole` when a thumbnail arrives.
- `PlayerView` (a `QWebEngineView` in `player.py`) loads the bundled `player.html` (package data,
  shipped inside the package for packaging robustness) which hosts the YouTube IFrame Player API.
  Python drives playback via `page.runJavaScript(...)` calling `window.playVideo` /
  `playList` / `next` / `prev`. Calls before page load are buffered in Python; the page itself
  queues calls until the IFrame API player is ready (two-stage buffering).
- **Why the page is served over http://localhost, not file://** (`server.py` `PlayerServer`):
  YouTube's embed auth check rejects `file://` (`embedder.identity.missing.referrer`) and also
  rejects `http://127.0.0.1` (error 150 / `auth`, video won't play) — but it accepts
  `http://localhost`. So `PlayerServer` serves `player.html` on an ephemeral `localhost` port and
  the view loads that URL. `main.py` also sets `QTWEBENGINE_CHROMIUM_FLAGS=--autoplay-policy=no-user-gesture-required`
  (before `QApplication`) so `loadVideoById` can autoplay with sound — Qt button clicks don't count
  as webview user gestures, so without this flag Chromium blocks autoplay. Both are required for
  videos to actually load and play. `scripts/diagnose_player.py` reproduces the player flow
  headlessly-ish and prints the JS console + a player-state probe — use it if playback breaks.
- **Why video frames actually render (not black):** QtWebEngine 6.11 (Chromium 140) regressed
  hardware video decode on Linux — the DMA-BUF → GL frame-import path produces a `Y_UV` mailbox
  the Skia renderer can't sample, so the GPU context is lost and decoded frames never reach the
  screen while audio keeps playing (`SharedImageBackingFactory` / `ProduceSkia … non-existent
  mailbox` errors; tracked in KDE Falkon #520199 and qutebrowser #8909/#8841). `main.py` adds
  `--disable-features=AcceleratedVideoDecodeLinuxGL` to `QTWEBENGINE_CHROMIUM_FLAGS`. This
  disables only the broken *hardware video-decode* path — full GPU compositing of the page and
  video stays on; the video stream is just software-decoded (cheap for H.264). Do NOT replace this
  with `--disable-gpu`, which would force full software rendering. `scripts/diagnose_embed.py` is
  the visual oracle for this (auto-plays a known muted video in a window).
- **Auto-advance + current-track signaling:** the page auto-advances to the next shuffled video
  on the IFrame API's `onStateChange` ENDED event (JS-side, no Python round-trip), gated by a JS
  `autoAdvance` flag driven from native via `window.setAutoAdvance`. A top-bar "Auto-advance"
  checkbox toggles it (default on, persisted in `settings.get_auto_advance`). A `QtWebChannel`
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