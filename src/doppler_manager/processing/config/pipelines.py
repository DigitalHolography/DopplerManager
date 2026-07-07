from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Optional

from doppler_manager._external_cli_runner import CLI_TOOLS, _find_uv_git_cli
from doppler_manager.processing.core.constants import (
    DEFAULT_PIPELINES_BY_STAGE,
    PIPELINE_SETTINGS_FOLDERS,
    PIPELINE_SETTINGS_TOOLS,
)
from doppler_manager.processing.core.paths import safe_resolve

from . import defaults


def available_pipelines_for_stage(stage: str) -> tuple[str, ...]:
    visibility = pipeline_visibility(stage)
    configured = tuple(visibility)
    defaults_for_stage = DEFAULT_PIPELINES_BY_STAGE[stage]
    return dedupe_strings((*configured, *defaults_for_stage))


def default_pipelines_for_stage(stage: str) -> tuple[str, ...]:
    visibility = pipeline_visibility(stage)
    selected = tuple(name for name, enabled in visibility.items() if enabled)
    if selected:
        return selected
    return DEFAULT_PIPELINES_BY_STAGE[stage]


def ensure_eyeflow_pipeline_file(
    cache_dir: Path,
    pipelines: Optional[Sequence[str]] = None,
) -> Path:
    pipeline_path = safe_resolve(cache_dir) / "processing" / "eyeflow_pipelines.txt"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    selected_pipelines = normalize_pipeline_selection(
        "ef",
        pipelines,
        label="EyeFlow",
    )
    desired = "\n".join(selected_pipelines) + "\n"
    if (
        not pipeline_path.exists()
        or pipeline_path.read_text(encoding="utf-8", errors="replace") != desired
    ):
        pipeline_path.write_text(desired, encoding="utf-8")
    return pipeline_path


def ensure_angioeye_pipeline_file(
    cache_dir: Path,
    pipelines: Optional[Sequence[str]] = None,
) -> Path:
    pipeline_path = safe_resolve(cache_dir) / "processing" / "angioeye_pipelines.txt"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    selected_pipelines = normalize_pipeline_selection(
        "ae",
        pipelines,
        label="AngioEye",
    )
    desired = "\n".join(selected_pipelines) + "\n"
    if (
        not pipeline_path.exists()
        or pipeline_path.read_text(encoding="utf-8", errors="replace") != desired
    ):
        pipeline_path.write_text(desired, encoding="utf-8")
    return pipeline_path


def pipeline_visibility(stage: str) -> dict[str, bool]:
    settings_path = default_pipeline_settings_path(stage)
    if settings_path is None:
        return {}

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    visibility = payload.get("pipeline_visibility")
    if not isinstance(visibility, dict):
        return {}
    return {
        str(name): bool(enabled)
        for name, enabled in visibility.items()
        if str(name).strip()
    }


def default_pipeline_settings_path(stage: str) -> Path | None:
    upstream = upstream_pipeline_settings_path(stage)
    if upstream is not None:
        return upstream

    fallback = (
        defaults.processing_defaults_dir()
        / PIPELINE_SETTINGS_FOLDERS[stage]
        / "default_settings.json"
    )
    return fallback if fallback.is_file() else None


def upstream_pipeline_settings_path(stage: str) -> Path | None:
    tool_name = PIPELINE_SETTINGS_TOOLS[stage]
    cli_path = _find_uv_git_cli(CLI_TOOLS[tool_name])
    if cli_path is None:
        return None
    settings_path = cli_path.parents[1] / "default_settings.json"
    return settings_path if settings_path.is_file() else None


def normalize_pipeline_selection(
    stage: str,
    pipelines: Optional[Sequence[str]],
    *,
    label: str,
) -> tuple[str, ...]:
    selected = (
        default_pipelines_for_stage(stage)
        if pipelines is None
        else dedupe_strings(
            str(pipeline).strip()
            for pipeline in pipelines
            if str(pipeline).strip()
        )
    )
    if not selected:
        raise ValueError(f"Select at least one {label} pipeline.")
    return selected


def dedupe_strings(values: Iterable[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)
