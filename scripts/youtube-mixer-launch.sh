#!/usr/bin/env bash
# Self-contained launcher for YouTube Randomizer.
#
# Ensures a dedicated venv (with the app installed) exists, then runs the app
# from it. The venv lives under $XDG_DATA_HOME/youtube-mixer/venv and is created
# on first launch, so this script is safe to invoke directly from a .desktop
# file — it does not depend on any system-wide Python packages.
set -euo pipefail

# Project root is the parent of this script's directory (scripts/ -> repo root).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/youtube-mixer"
VENV_DIR="${YT_MIXER_VENV:-"$DATA_DIR/venv"}"
ENTRY="$VENV_DIR/bin/youtube-mixer"

ensure_installed() {
  if [ -x "$ENTRY" ]; then
    return 0  # already installed; fast path
  fi
  echo "YouTube Randomizer: setting up its venv at $VENV_DIR" >&2
  mkdir -p "$DATA_DIR"
  if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR"
  fi
  "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
  # Non-editable install so the venv is self-contained (doesn't need the repo at run time).
  "$VENV_DIR/bin/python" -m pip install --no-input "$PROJECT_DIR"
}

ensure_installed
exec "$ENTRY" "$@"