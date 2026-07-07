from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from . import defaults
from doppler_manager.processing.core.paths import safe_resolve


REQUIRED_HOLODOPPLER_SETTINGS_KEYS = ("temporal_transformation",)


def discover_holodoppler_settings(root: Path | str) -> list[Path]:
    root_path = Path(root).expanduser()
    candidates: list[Path] = []

    env_file = os.getenv("DM_HOLODOPPLER_SETTINGS")
    if env_file:
        candidates.append(Path(env_file).expanduser())

    env_dir = os.getenv("DM_HOLODOPPLER_SETTINGS_DIR")
    if env_dir:
        candidates.append(Path(env_dir).expanduser())

    candidates.extend(
        [
            defaults.bundled_holodoppler_settings_dir(),
            Path.cwd() / "processing_defaults" / "holodoppler",
            Path.cwd() / "parameters",
            Path.cwd() / "HoloDopplerPython" / "parameters",
            root_path / "parameters",
            root_path / "HoloDopplerPython" / "parameters",
        ]
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


def holodoppler_settings_from_path(path: Path | str) -> list[Path]:
    value = str(path).strip()
    if not value:
        return []

    candidate = Path(value).expanduser()
    if candidate.is_file() and candidate.suffix.lower() == ".json":
        return [candidate]
    if candidate.is_dir():
        return sorted(candidate.glob("*.json"), key=lambda item: item.name.lower())
    return []


def preferred_holodoppler_settings(settings: Sequence[Path]) -> Optional[Path]:
    if not settings:
        return None
    compatible = [path for path in settings if has_settings_keys(path, REQUIRED_HOLODOPPLER_SETTINGS_KEYS)]
    if compatible:
        settings = compatible
    preferred_names = (
        "default_parameters.json",
        "default_parameters_debug.json",
        "default_parameters_lightest.json",
        "default_parameters_cine.json",
    )
    by_name = {path.name.lower(): path for path in settings}
    for name in preferred_names:
        if name in by_name:
            return by_name[name]
    return settings[0]


def has_settings_keys(path: Path, keys: Sequence[str]) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return all(key in payload for key in keys)
