from __future__ import annotations

import sys
from pathlib import Path


REPO_PROCESSING_DEFAULTS = Path(__file__).resolve().parents[3] / "processing_defaults"


def processing_defaults_dir() -> Path:
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "processing_defaults")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "processing_defaults")
    candidates.extend(
        [
            REPO_PROCESSING_DEFAULTS,
            Path.cwd() / "processing_defaults",
        ]
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0] if candidates else REPO_PROCESSING_DEFAULTS


def bundled_holodoppler_settings_dir() -> Path:
    return processing_defaults_dir() / "holodoppler"

