from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from doppler_manager.processing.core.paths import safe_resolve


def ensure_angioeye_postprocess_file(
    cache_dir: Path,
    postprocesses: Sequence[str],
) -> Path:
    names = _dedupe_nonempty(postprocesses)
    if not names:
        raise ValueError("Select at least one AngioEye postprocess.")
    return _ensure_text_file(
        safe_resolve(cache_dir) / "processing" / "angioeye_postprocesses.txt",
        names,
    )


def ensure_angioeye_postprocess_pipeline_file(cache_dir: Path) -> Path:
    """Create the explicit empty pipeline selection for postprocess-only runs."""

    path = (
        safe_resolve(cache_dir)
        / "processing"
        / "angioeye_postprocess_pipelines.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8", errors="replace"):
        path.write_text("", encoding="utf-8")
    return path


def _ensure_text_file(path: Path, lines: Iterable[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    desired = "\n".join(lines) + "\n"
    if (
        not path.exists()
        or path.read_text(encoding="utf-8", errors="replace") != desired
    ):
        path.write_text(desired, encoding="utf-8")
    return path


def _dedupe_nonempty(values: Sequence[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return tuple(deduped)


__all__ = [
    "ensure_angioeye_postprocess_pipeline_file",
    "ensure_angioeye_postprocess_file",
]
