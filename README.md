# YouTube Randomizer

A native desktop YouTube playlist randomizer. Built because YouTube's built-in playlist
shuffle is broken for long playlists — it tends to grab ~10 videos and loop them instead of
covering the whole list. This app fetches the full playlist and does a real **Fisher–Yates
shuffle** so every video plays once before any repeats.

Inspired by https://youtube-playlist-randomizer.bitbucket.io/, but as a native app with an
embedded player.

## Features

- Paste a YouTube playlist URL or ID to load it.
- Full-coverage shuffle (every video reached once before repeats).
- Search/filter within the loaded list.
- Embedded YouTube player (Chromium via QtWebEngine).
- The playlist is displayed in the shuffled playback order.

## Requirements

- Python 3.10+
- A **YouTube Data API v3 key** (free). Create one at the
  [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com):
  enable the "YouTube Data API v3", then create an API key under *Credentials*. The free quota
  (10,000 units/day; ~1 unit per 50 playlist items) is more than enough for personal use.

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

On first load, the app prompts for your YouTube Data API key, which it stores in your OS user
config directory (`~/.config/youtube-mixer/config.json` on Linux).

## Tests & lint

```bash
pytest                 # run all tests
pytest tests/test_shuffle.py   # run a single test file
ruff check .           # lint
```

## License

MIT — see [LICENSE](LICENSE).