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
