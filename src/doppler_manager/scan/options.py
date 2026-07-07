from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, Tuple

from doppler_manager.scan.filters import (
    clean_holo_filter_entry,
    normalize_holo_filter_entry,
)


DEFAULT_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "cache",
    "output",
}


@dataclass
class ScanOptions:
    max_depth: int = 8
    max_entries: int = 250_000
    preview_limit_per_stage: int = 40
    read_versions: bool = True
    max_text_bytes: int = 4_096
    skip_dirs: Set[str] = field(default_factory=lambda: set(DEFAULT_SKIP_DIRS))
    holo_filter_ids: Optional[Set[str]] = None
    holo_filter_entries: Optional[Tuple[str, ...]] = None

    def __post_init__(self) -> None:
        if self.holo_filter_ids is not None:
            self.holo_filter_ids = {
                normalized
                for value in self.holo_filter_ids
                if (normalized := normalize_holo_filter_entry(value))
            }
        if self.holo_filter_entries is not None:
            self.holo_filter_entries = tuple(
                entry
                for value in self.holo_filter_entries
                if (entry := clean_holo_filter_entry(value))
            )
