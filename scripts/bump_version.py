#!/usr/bin/env python3
"""Bump the project version in lockstep across all the places it appears.

The canonical version is ``youtube_mixer.__version__`` in
``src/youtube_mixer/__init__.py``. This script updates that and the
``**Version:**`` line in ``README.md`` together so they never drift, then prints
the suggested commit/tag commands.

Usage:
    python scripts/bump_version.py <new-version>      # e.g. 0.2.0
    python scripts/bump_version.py <new-version> --dry-run

The README/installed-distribution consistency is also enforced by
tests/test_version_sync.py, so a drift would fail CI regardless.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src" / "youtube_mixer" / "__init__.py"
README_FILE = ROOT / "README.md"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
INIT_VERSION_RE = re.compile(r'^(__version__\s*=\s*)["\']([^"\']+)["\']', re.MULTILINE)
README_VERSION_RE = re.compile(r"^(\*\*Version:\*\*\s*)(\S+)", re.MULTILINE)


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def bump(new_version: str, *, dry_run: bool) -> None:
    if not SEMVER_RE.match(new_version):
        _fail(f"{new_version!r} is not a valid SemVer string (e.g. 0.2.0).")

    init_text = INIT_FILE.read_text(encoding="utf-8")
    readme_text = README_FILE.read_text(encoding="utf-8")

    init_match = INIT_VERSION_RE.search(init_text)
    readme_match = README_VERSION_RE.search(readme_text)
    if not init_match:
        _fail(f"could not find __version__ in {INIT_FILE}.")
    if not readme_match:
        _fail(f"could not find a '**Version:**' line in {README_FILE}.")

    current = init_match.group(2)
    if readme_match.group(2) != current:
        _fail(
            f"README version {readme_match.group(2)!r} already out of sync with "
            f"__version__ {current!r}; fix manually before bumping."
        )

    print(f"Bumping version: {current} -> {new_version}")

    new_init = INIT_VERSION_RE.sub(
        lambda m: f'{m.group(1)}"{new_version}"', init_text, count=1
    )
    new_readme = README_VERSION_RE.sub(
        lambda m: f"{m.group(1)}{new_version}", readme_text, count=1
    )

    if dry_run:
        print("--dry-run: no files written.")
        return

    INIT_FILE.write_text(new_init, encoding="utf-8")
    README_FILE.write_text(new_readme, encoding="utf-8")
    print(f"updated {INIT_FILE.relative_to(ROOT)}")
    print(f"updated {README_FILE.relative_to(ROOT)}")
    print(
        "\nNext:\n"
        f"  git add -A && git commit -m 'Release v{new_version}'\n"
        f"  git tag v{new_version}\n"
        f"  git push && git push --tags"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump the project version in lockstep.")
    parser.add_argument("version", help="new SemVer version, e.g. 0.2.0")
    parser.add_argument("--dry-run", action="store_true", help="show changes without writing")
    args = parser.parse_args()
    bump(args.version, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
