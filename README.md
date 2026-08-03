# YouTube Randomizer

A native desktop YouTube playlist randomizer with an embedded player and full-coverage shuffle.

**Version:** 0.2.0 · **License:** MIT

## What this is

A small native desktop app (Python + PySide6/Qt, with an embedded Chromium web player) that
loads a YouTube playlist, shuffles the **entire** list, and plays it back in that order with
auto-advance.

## Why

YouTube's built-in playlist shuffle is broken for long playlists: it tends to grab about ten
videos and loop them, instead of covering the whole list. This app fetches the full playlist and
does a real **Fisher–Yates shuffle** so every video plays once before any repeats. Inspired by
the web tool at https://youtube-playlist-randomizer.bitbucket.io/, but as a native app.

## Features

- Paste a YouTube playlist URL or ID to load it.
- **Saved playlists:** previously-loaded playlists are remembered by name in a dropdown for
  one-click recall, and a **Playlist Manager** (Manage…) lets you add, delete, and reorder them.
- Full-coverage shuffle (every video is reached once before repeats).
- Search/filter within the loaded list.
- Embedded YouTube player (Chromium via QtWebEngine).
- **Resolution selector:** 360p / 720p / 1080p / 1440p, plus **Cinema mode** (theater layout +
  best-available quality). Note: YouTube caps embedded quality by the player's on-screen size, so
  1080p/1440p only actually arrive when the player is large — Cinema mode and fullscreen enable it.
- **Fullscreen:** press **F11** to toggle full-window fullscreen (chrome hidden). **Esc** exits
  fullscreen, then exits Cinema mode.
- **Shuffle toggle:** the Shuffle button toggles between shuffled and canonical (original)
  order — switching keeps the current video playing and continues next/prev from it.
- **Hotkeys:** **Space** play/pause, **Ctrl+→** next, **Ctrl+←** previous, **Ctrl+S**
  shuffle/unshuffle (suppressed while you're typing in the search/playlist box).
- Remembers your last playlist, quality, and window size/position — on launch it reloads the
  last playlist (cued, not auto-playing) and restores the window.
- Auto-advance to the next video when one ends (toggleable, remembered between runs).
- The playlist is displayed in the shuffled playback order, with thumbnails; the now-playing
  row is highlighted as playback advances.

## Requirements

- Python 3.10+
- A **YouTube Data API v3 key** (free). Create one in the
  [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com):
  enable "YouTube Data API v3", then create an API key under *Credentials*. The free quota
  (10,000 units/day; ~1 unit per 50 playlist items) is plenty for personal use.

## Install (desktop launcher)

To install as a normal desktop application (shows up in your application menu, launches from
its own self-contained venv):

```bash
bash scripts/install.sh
```

This creates a dedicated venv under `~/.local/share/youtube-mixer/venv`, installs the app into
it (non-editable, so it doesn't depend on the source tree at run time), installs the icon, and
writes a `.desktop` launcher to `~/.local/share/applications/youtube-mixer.desktop`. Re-run the
script to upgrade to the current source.

The launcher (`scripts/youtube-mixer-launch.sh`) is self-contained: if its venv is missing it
recreates it and reinstalls the app, so the menu entry keeps working even after the venv is
deleted. You can also launch directly:

```bash
bash scripts/youtube-mixer-launch.sh
```

## Install (development)

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```bash
youtube-mixer          # via console script
# or
python -m youtube_mixer
```

On first load the app prompts for your YouTube Data API key, which it stores in your OS user
config directory (`~/.config/youtube-mixer/config.json` on Linux).

## Tests & lint

```bash
pytest                              # all tests
pytest tests/test_shuffle.py        # single file
pytest tests/test_shuffle.py::test_shuffle_seed_is_reproducible   # single test
ruff check .                        # lint
```

## Versioning

This project uses [Semantic Versioning](https://semver.org/). While the major version is `0`
(pre-1.0), minor bumps may include breaking changes; patches are bug fixes only.

The canonical version lives in **one place**: `youtube_mixer.__version__`
(`src/youtube_mixer/__init__.py`). `pyproject.toml` reads it dynamically, and the **Version**
line at the top of this README must always match it — a test (`tests/test_version_sync.py`)
fails if they drift.

To cut a new release, use the bump script so the version stays in sync everywhere:

```bash
python scripts/bump_version.py 0.2.0
# then commit and tag, e.g.:
#   git add -A && git commit -m "Release v0.2.0"
#   git tag v0.2.0
```

## License

MIT — see [LICENSE](LICENSE). PySide6 is LGPL (compatible).