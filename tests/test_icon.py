"""The app icon lives in two places that must stay in sync.

``icons/youtube-mixer.png`` (repo root) is the canonical source the user edits and the file the
desktop launcher points at. ``src/youtube_mixer/icons/youtube-mixer.png`` is the copy bundled
into the package so the runtime window icon resolves in a non-editable install (the launcher
installs the package only — the top-level ``icons/`` dir is not shipped). If these drift, the
window icon and the menu icon can disagree, so this test pins them byte-for-byte.
"""

from __future__ import annotations

import hashlib
from importlib.resources import files
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ICON = REPO_ROOT / "icons" / "youtube-mixer.png"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_icon_exists():
    assert SOURCE_ICON.is_file(), "canonical icon icons/youtube-mixer.png is missing"


def test_bundled_icon_matches_source():
    bundled = Path(str(files("youtube_mixer").joinpath("icons/youtube-mixer.png")))
    assert bundled.is_file(), "package data icon icons/youtube-mixer.png is missing"
    assert _sha(bundled) == _sha(SOURCE_ICON), (
        "Bundled icon (src/youtube_mixer/icons/youtube-mixer.png) differs from the canonical "
        "source (icons/youtube-mixer.png). Re-copy the source into the package."
    )
