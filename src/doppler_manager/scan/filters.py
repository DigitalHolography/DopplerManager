from __future__ import annotations

from pathlib import Path
from typing import Optional, Set, Tuple


def holo_filter_ids_from_text(text: str) -> Set[str]:
    ids: Set[str] = set()
    for entry in holo_filter_entries_from_text(text):
        normalized = normalize_holo_filter_entry(entry)
        if normalized:
            ids.add(normalized)
    return ids


def holo_filter_entries_from_text(text: str) -> Tuple[str, ...]:
    return tuple(
        entry
        for line in text.splitlines()
        if (entry := clean_holo_filter_entry(line))
    )


def holo_filter_allows(
    acquisition_id: str,
    holo_filter_ids: set[str] | None,
) -> bool:
    return holo_filter_ids is None or acquisition_id in holo_filter_ids


def clean_holo_filter_entry(value: object) -> Optional[str]:
    candidate = str(value).strip().lstrip("\ufeff").strip("\"'")
    if not candidate or candidate.startswith("#"):
        return None
    return candidate


def normalize_holo_filter_entry(value: object) -> Optional[str]:
    candidate = clean_holo_filter_entry(value)
    if candidate is None:
        return None

    name = candidate.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if name.lower().endswith(".holo"):
        name = name[: -len(".holo")]
    return name or None


def holo_filter_entry_path(entry: str, root: Path) -> Optional[Path]:
    value = clean_holo_filter_entry(entry)
    if value is None:
        return None

    path_like = (
        value.lower().endswith(".holo")
        or "\\" in value
        or "/" in value
    )
    if not path_like:
        return None

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate
