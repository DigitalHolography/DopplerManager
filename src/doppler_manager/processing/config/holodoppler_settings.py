from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from doppler_manager import release_defaults
from doppler_manager.processing.core.paths import safe_resolve

from . import defaults


REQUIRED_HOLODOPPLER_SETTINGS_KEYS = ("temporal_transformation",)
PREFERRED_HOLODOPPLER_SETTINGS = (
    "default_parameters_simple.yaml",
    "default_parameters_debug.json",
    "debug_parameters.json",
    "default_parameters.json",
    "default_parameters_lightest.json",
    "default_parameters_cine.json",
)


def discover_holodoppler_settings(root: Path | str) -> list[Path]:
    candidates: tuple[Path | str | None, ...] = (
        os.getenv("DM_HOLODOPPLER_SETTINGS"),
        os.getenv("DM_HOLODOPPLER_SETTINGS_DIR"),
        upstream_holodoppler_settings_dir(),
        defaults.bundled_holodoppler_settings_dir(),
        Path(root).expanduser() / "parameters",
    )

    settings: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        for path in holodoppler_settings_from_path(candidate):
            resolved = safe_resolve(path)
            if resolved not in seen:
                seen.add(resolved)
                settings.append(path)
    return sorted(settings, key=lambda item: item.name.lower())


def upstream_holodoppler_settings_dir() -> Path | None:
    try:
        settings_dir = release_defaults._app_root("holodoppler", "holodoppler") / "parameters"
    except (FileNotFoundError, RuntimeError, release_defaults.metadata.PackageNotFoundError):
        return None
    return settings_dir if settings_dir.is_dir() else None


def holodoppler_settings_from_path(path: Path | str | None) -> list[Path]:
    if path is None:
        return []
    value = str(path).strip()
    if not value:
        return []

    candidate = Path(value).expanduser()
    if candidate.is_file() and candidate.suffix.lower() in release_defaults.HOLODOPPLER_SETTINGS_SUFFIXES:
        return [candidate]
    if candidate.is_dir():
        return sorted(
            (
                item
                for item in candidate.iterdir()
                if item.is_file()
                and item.suffix.lower() in release_defaults.HOLODOPPLER_SETTINGS_SUFFIXES
            ),
            key=lambda item: item.name.lower(),
        )
    return []


def preferred_holodoppler_settings(settings: Sequence[Path]) -> Path | None:
    if not settings:
        return None
    compatible = [
        path
        for path in settings
        if has_settings_keys(path, REQUIRED_HOLODOPPLER_SETTINGS_KEYS)
    ]
    if compatible:
        settings = compatible
    by_name: dict[str, Path] = {}
    for path in settings:
        by_name.setdefault(path.name.lower(), path)
    for name in PREFERRED_HOLODOPPLER_SETTINGS:
        if name in by_name:
            return by_name[name]
    return settings[0]


def has_settings_keys(path: Path, keys: Sequence[str]) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False

    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return False
    else:
        try:
            import yaml
        except ImportError:
            return False
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError:
            return False

    if not isinstance(payload, dict):
        return False
    return all(key in payload for key in keys)
