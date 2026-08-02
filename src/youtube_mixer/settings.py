"""Persistent settings (API key) stored in the OS user config directory."""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "youtube-mixer"


def config_path() -> Path:
    """Return the config file path, creating its parent directory if needed."""
    path = Path(user_config_dir(APP_NAME)) / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_settings() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(data: dict) -> None:
    config_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_api_key() -> str | None:
    return load_settings().get("api_key")


def set_api_key(key: str) -> None:
    data = load_settings()
    data["api_key"] = key.strip()
    save_settings(data)


def get_auto_advance() -> bool:
    """Auto-advance defaults to on when unset."""
    return bool(load_settings().get("auto_advance", True))


def set_auto_advance(enabled: bool) -> None:
    data = load_settings()
    data["auto_advance"] = bool(enabled)
    save_settings(data)


# --- Saved playlists (history + manager) -------------------------------------
# Stored as a list of {"id": <playlist id>, "name": <title>, "url": <str | None>},
# in display/reorder order.

def get_playlists() -> list[dict]:
    """Return saved playlists as a list of {id, name, url} dicts (in order)."""
    raw = load_settings().get("playlists", [])
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("id"):
            continue
        out.append(
            {
                "id": str(entry["id"]),
                "name": str(entry.get("name") or entry["id"]),
                "url": entry.get("url"),
            }
        )
    return out


def set_playlists(items: list[dict]) -> None:
    """Replace the saved-playlists list (used by the manager for reorder/delete)."""
    data = load_settings()
    data["playlists"] = [
        {"id": str(i["id"]), "name": str(i.get("name") or i["id"]), "url": i.get("url")}
        for i in items
        if i.get("id")
    ]
    save_settings(data)


def add_playlist(playlist_id: str, name: str, url: str | None = None) -> None:
    """Add or update a saved playlist (deduped by id); appends if new."""
    items = get_playlists()
    for entry in items:
        if entry["id"] == playlist_id:
            entry["name"] = name or playlist_id
            if url:
                entry["url"] = url
            set_playlists(items)
            return
    items.append({"id": playlist_id, "name": name or playlist_id, "url": url})
    set_playlists(items)


def remove_playlist(playlist_id: str) -> None:
    set_playlists([i for i in get_playlists() if i["id"] != playlist_id])


def rename_playlist(playlist_id: str, name: str) -> None:
    items = get_playlists()
    for entry in items:
        if entry["id"] == playlist_id:
            entry["name"] = name or playlist_id
            set_playlists(items)
            return


def move_playlist(playlist_id: str, to_index: int) -> None:
    """Move a saved playlist to ``to_index`` (clamped to the list bounds)."""
    items = get_playlists()
    src = next((i for i, e in enumerate(items) if e["id"] == playlist_id), None)
    if src is None:
        return
    to_index = max(0, min(to_index, len(items) - 1))
    items.insert(to_index, items.pop(src))
    set_playlists(items)


# --- Playback resolution -----------------------------------------------------
# One of: "medium" (360), "hd720", "hd1080", "hd1440", "cinema". Defaults to 720p.

RESOLUTIONS = ("medium", "hd720", "hd1080", "hd1440", "cinema")


def get_resolution() -> str:
    value = load_settings().get("resolution", "hd720")
    return value if value in RESOLUTIONS else "hd720"


def set_resolution(value: str) -> None:
    if value not in RESOLUTIONS:
        return
    data = load_settings()
    data["resolution"] = value
    save_settings(data)
