#!/usr/bin/env bash
# Install YouTube Randomizer as a desktop app.
#
# Creates a dedicated, self-contained venv (separate from any dev .venv),
# installs the app into it, installs the icon, and writes a .desktop launcher
# into the user's applications directory so it shows up in the application menu.
#
#   bash scripts/install.sh         # install / upgrade
#
# Re-running this script upgrades the installed app to the current source.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/youtube-mixer"
VENV_DIR="${YT_MIXER_VENV:-"$DATA_DIR/venv"}"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_SRC="$PROJECT_DIR/resources/icon.svg"
ICON_DST="$DATA_DIR/icon.svg"
WRAPPER="$PROJECT_DIR/scripts/youtube-mixer-launch.sh"
DESKTOP_FILE="$APPS_DIR/youtube-mixer.desktop"

echo "Installing YouTube Randomizer"
echo "  project: $PROJECT_DIR"
echo "  venv:    $VENV_DIR"
echo "  launcher: $DESKTOP_FILE"
echo

mkdir -p "$DATA_DIR" "$APPS_DIR"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Creating venv..."
  python3 -m venv "$VENV_DIR"
fi

echo "Installing app + dependencies into the venv (needs network on first run)..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --no-input "$PROJECT_DIR"

echo "Installing icon..."
cp "$ICON_SRC" "$ICON_DST"

echo "Writing desktop launcher..."
chmod +x "$WRAPPER"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=YouTube Randomizer
Comment=Real Fisher-Yates shuffle for long YouTube playlists
Exec=$WRAPPER
Icon=$ICON_DST
Terminal=false
Categories=AudioVideo;Video;Player;Qt;
StartupWMClass=youtube-mixer
EOF

# Refresh the application-menu index if the helper is available.
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi

echo
echo "Done. Launch \"YouTube Randomizer\" from your application menu, or run:"
echo "  $WRAPPER"