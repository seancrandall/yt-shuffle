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

# install as a desktop app (own self-contained venv + .desktop launcher)
bash scripts/install.sh
```

The app needs a **YouTube Data API v3 key**, prompted on first load and stored in the OS user
config dir (`~/.config/youtube-mixer/config.json` on Linux). See README for how to get one.

`scripts/install.sh` builds a **separate, dedicated venv** at
`~/.local/share/youtube-mixer/venv` (not the dev `.venv`), installs the app non-editable, installs
the icon (`icons/youtube-mixer.png` → `~/.local/share/youtube-mixer/icon.png`), and writes
`~/.local/share/applications/youtube-mixer.desktop` whose `Exec` is
`scripts/youtube-mixer-launch.sh`. That wrapper derives the project dir from its own location,
recreates the venv + reinstalls the app if missing (self-healing), then execs the venv
`youtube-mixer` entry — so the menu entry is fully self-contained.

The app icon is `icons/youtube-mixer.png` (repo root, the canonical source the user edits and
the `.desktop` file points at). A byte-identical copy is bundled into the package at
`src/youtube_mixer/icons/youtube-mixer.png` (declared in `[tool.setuptools.package-data]`) so the
runtime **window icon** resolves in a non-editable install — the launcher ships the package only,
not the top-level `icons/` dir, so the window icon must live inside the package. `main.py` loads
it via `importlib.resources` and sets it with `app.setWindowIcon`. `tests/test_icon.py` fails if
the two copies drift — after editing `icons/youtube-mixer.png`, re-copy it into the package.

`settings.py` also persists the **last-used playlist id** (`get/set_last_playlist_id`) and the
**window geometry** (`get/set_geometry`, the hex of Qt's `saveGeometry` bytes). On launch
`MainWindow.__init__` restores the geometry and, if a last playlist id *and* a stored API key
both exist, kicks off a **silent, non-autoplaying** load of it (`_start_load(last, autoplay=False,
silent=True)`): it populates the list and **cues** (not plays) the first video via
`PlayerView.cue_list` → `window.cueList` → `player.cueVideoById`. Silent means a launch-time
failure (e.g. offline) doesn't pop a modal. `closeEvent` saves geometry (skipped while fullscreen,
so the restored geometry is the normal window's, not the fullscreen one). Quality is likewise
persisted (`get/set_resolution`), restored into the combo on startup.

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
  thread → emits the `list[Video]` back via a signal. Each `LoadThread` is cleaned up on
  `finished` (`_on_load_thread_finished` → `deleteLater` + clears `self._thread`); `_start_load`
  refuses to start a second while one is still running.
- `playlist.shuffle` does a full-coverage Fisher–Yates shuffle of the entire list (the core fix;
  optional `seed` for reproducibility). The shuffled order is the default playback order, but the
  "Shuffle" button is a **toggle**: clicking it again restores canonical (original-fetched) order.
  `MainWindow` keeps both `self._canonical` (original, never mutated) and `self._order` (current
  display/playback order); toggling swaps `_order` between `shuffle(_canonical)` and `_canonical`.
  The toggle **does not restart playback** — it calls `PlayerView.set_list` → `window.setList`
  (player.html), which re-points the play order and current index without `loadVideoById`, so the
  now-playing video keeps going and next/prev continue from it in the new order. (`_apply_order`,
  used only on initial load, still calls `play_list` which loads index 0.)
- `PlaylistModel` (a `QAbstractListModel` in `models.py`) backs the bottom `QListView`; it exposes
  display title, `Qt.DecorationRole` (thumbnail as `QIcon`), `Qt.ToolTipRole` (full title), plus
  `ID_ROLE`/`THUMB_ROLE`. The `QListView` is in list mode with a 120×68 icon size and uniform row
  sizes, so each row shows its thumbnail and the selected/now-playing row is clearly highlighted.
  Thumbnails are fetched async via `QNetworkAccessManager` and **cached by video ID** so
  re-shuffle/search does not refetch; `dataChanged` is emitted for both `THUMB_ROLE` and
  `Qt.DecorationRole` when a thumbnail arrives. Pixmaps are **scaled to ~2x the list icon size
  before caching** (`THUMB_PIXEL_SIZE`, not the full YouTube "medium" 320×180) and the cache is
  **capped** (`MAX_THUMBS`, FIFO) so a long playlist and many different loaded playlists can't
  grow it without bound; evicted entries refetch on the next shuffle/search.
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
  videos to actually load and play. For long unattended runs the flags also bound Chromium's
  footprint: `--renderer-process-limit=1` (single-page embed needs one renderer) and small
  `--disk-cache-size` / `--media-cache-size` caps. `scripts/diagnose_player.py` reproduces the player
  flow headlessly-ish and prints the JS console + a player-state probe — use it if playback breaks.
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
- **Saved playlists + manager:** `settings.py` persists a `playlists` list of `{id, name, url}`
  (add/remove/rename/move helpers) and a `resolution` preference. The playlist input is an
  editable `QComboBox`: dropdown items are saved playlists shown by **name** (id as item data);
  picking one loads it by id (`_load_history_item`), typing a URL/ID + Enter/Load loads it as new.
  `LoadThread` parses the id once, fetches videos **and** the playlist title (`api.fetch_playlist_meta`
  → `playlists.list?part=snippet`) over one shared `httpx.Client`, and emits `(videos, id, name)`;
  `_on_loaded` saves it to history and refreshes the combo. `manager.PlaylistManagerDialog`
  (opened from the "Manage…" button) does add/delete/reorder and writes back via `set_playlists`.
- **Resolution + cinema + fullscreen:** `player.html` keeps a `currentQuality` and exposes
  `window.setQuality(q)` → `player.setPlaybackQualityRange(...)` (`medium`/`hd720`/`hd1080`/
  `hd1440` pinned, `cinema` = `("small","highres")` best-available), re-asserted in `onReady` and
  after every `loadVideoById` (the IFrame player resets quality per video). `PlayerView.set_quality`
  plumbs it. A toolbar `QComboBox` drives `on_quality_changed`, which persists the choice
  (`settings.set_resolution`) and, for **Cinema mode**, hides chrome via `_set_chrome_visible`
  (top bar + controls + list) so the player fills the window — the larger player is what lets
  YouTube actually serve 1080p/1440p. **F11** toggles `showFullScreen`/`showNormal`;
  **Esc** exits fullscreen then cinema. `_apply_layout` hides chrome iff fullscreen or cinema.
- **Media hotkeys:** window-scoped `QShortcut`s on `MainWindow` for **Space** (play/pause),
  **Ctrl+→** (next), **Ctrl+←** (previous), **Ctrl+S** (shuffle/unshuffle toggle) — the same
  mechanism F11/Esc already use. Space is a window shortcut, so when a text field (the search box
  or editable playlist combo) has focus the slot re-posts a Space to it (so the space is typed)
  instead of toggling play; otherwise it toggles via `player.html` `window.togglePlay`
  (`getPlayerState()` → `playVideo`/`pauseVideo`). **Do not** reimplement these with an
  application-wide `installEventFilter` on `QApplication`: Qt routes QtWebEngine's internal
  `QWebEngineUrlRequestJob` events through application event filters, and PySide segfaults in
  `getWrapperForQObject` trying to wrap that job during the localhost player-page load (the
  original hotkey implementation crashed on launch this way). `QShortcut` never sees those
  internal objects, so it's safe.

Cross-cutting details worth knowing:
- `api.fetch_playlist` and `api.fetch_playlist_meta` both accept an injected `httpx.Client`
  (used in tests with `httpx.MockTransport` keyed by the `pageToken` / `id` query param). Don't
  add network calls that bypass this seam if you want them testable.
- `playlist.Video` is a frozen dataclass — pass it around by value, never mutate.
- Search (`playlist.search`) only filters the *display* model; it does not change the player's
  order. Next/prev always walk the full current order (shuffled or canonical).

## License

MIT — see `LICENSE`. PySide6 is LGPL (compatible).