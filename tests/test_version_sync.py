"""Enforce that the version stays in sync across __version__, README, and the installed dist.

The canonical version is ``youtube_mixer.__version__``. If the README's ``**Version:**`` line
or the installed distribution metadata drifts from it, this test fails — which is the real
guarantee that the README always shows the current version.
"""

from __future__ import annotations

import importlib.metadata
import re

import youtube_mixer

README_VERSION_RE = re.compile(r"^\*\*Version:\*\*\s*(\S+)", re.MULTILINE)


def _readme_version() -> str:
    from pathlib import Path

    readme = Path(__file__).resolve().parents[1] / "README.md"
    match = README_VERSION_RE.search(readme.read_text(encoding="utf-8"))
    assert match, "README.md is missing a '**Version:** <x.y.z>' line"
    return match.group(1)


def test_readme_version_matches_init_version():
    assert _readme_version() == youtube_mixer.__version__


def test_installed_distribution_matches_init_version():
    assert importlib.metadata.version("youtube-mixer") == youtube_mixer.__version__
