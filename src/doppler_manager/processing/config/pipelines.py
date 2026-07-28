from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from doppler_manager._external_cli_runner import CLI_TOOLS, _find_uv_git_cli
from doppler_manager.processing.core.constants import (
    DEFAULT_PIPELINES_BY_STAGE,
    PIPELINE_SETTINGS_FOLDERS,
    PIPELINE_SETTINGS_TOOLS,
)
from doppler_manager.processing.core.paths import safe_resolve
from doppler_manager.processing.runtimes import (
    RuntimeStage,
    runtime_catalog,
    runtime_project_dir,
)

from . import defaults


@dataclass(frozen=True)
class PipelineInfo:
    """Serializable pipeline metadata returned by an isolated runtime."""

    name: str
    description: str = ""
    available: bool = True
    missing_deps: tuple[str, ...] = ()
    required_pipelines: tuple[str, ...] = ()
    required_pipeline_options: tuple[tuple[str, ...], ...] = ()
    dag_requires: tuple[str, ...] = ()
    dag_produces: tuple[str, ...] = ()
    input_slot: str = "both"
    missing_pipelines: tuple[str, ...] = ()
    error_msg: str = ""
    visibility: str = "visible"


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


def pipeline_descriptors_for_stage(stage: str) -> tuple[PipelineInfo, ...]:
    """Return upstream pipeline descriptors configured for a processing stage."""

    configured_names = set(available_pipelines_for_stage(stage))
    try:
        available, missing = pipeline_catalog(stage)
    except Exception:  # noqa: BLE001
        return ()
    return tuple(
        descriptor
        for descriptor in (*available, *missing)
        if str(getattr(descriptor, "name", "")).strip() in configured_names
    )


@lru_cache(maxsize=2)
def pipeline_catalog(
    stage: RuntimeStage = "ae",
) -> tuple[list[PipelineInfo], list[PipelineInfo]]:
    """Load one isolated runtime's pipeline decorator catalog."""

    available, missing = runtime_catalog(stage, "pipelines")
    return (
        [_pipeline_info(item, available=True) for item in available],
        [_pipeline_info(item, available=False) for item in missing],
    )


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
    runtime_stage: RuntimeStage = "ef" if stage == "ef" else "ae"
    settings_path = runtime_project_dir(runtime_stage) / "default_settings.json"
    if settings_path.is_file():
        return settings_path

    # Keep compatibility with installations created before isolated runtime
    # projects were introduced. This reads metadata only; it never imports an
    # upstream package into the manager process.
    tool_name = PIPELINE_SETTINGS_TOOLS[stage]
    cli_path = _find_uv_git_cli(CLI_TOOLS[tool_name])
    if cli_path is None:
        return None
    legacy_settings_path = cli_path.parents[1] / "default_settings.json"
    return legacy_settings_path if legacy_settings_path.is_file() else None


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
            str(pipeline).strip() for pipeline in pipelines if str(pipeline).strip()
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


def _pipeline_info(record, *, available: bool) -> PipelineInfo:
    return PipelineInfo(
        name=_text(record, "name"),
        description=_text(record, "description"),
        available=bool(getattr(record, "available", available)) and available,
        missing_deps=_strings(record, "missing_deps"),
        required_pipelines=_strings(record, "required_pipelines"),
        required_pipeline_options=_string_options(record, "required_pipeline_options"),
        dag_requires=_strings(record, "dag_requires"),
        dag_produces=_strings(record, "dag_produces"),
        input_slot=_text(record, "input_slot") or "both",
        missing_pipelines=_strings(record, "missing_pipelines"),
        error_msg=_text(record, "error_msg"),
        visibility=_text(record, "visibility") or "visible",
    )


def _text(record, field: str) -> str:
    return str(getattr(record, field, "") or "").strip()


def _strings(record, field: str) -> tuple[str, ...]:
    value = getattr(record, field, ()) or ()
    if isinstance(value, str):
        value = (value,)
    return tuple(
        dict.fromkeys(str(item).strip() for item in value if str(item).strip())
    )


def _string_options(record, field: str) -> tuple[tuple[str, ...], ...]:
    value = getattr(record, field, ()) or ()
    if isinstance(value, str):
        value = ((value,),)
    return tuple(
        option for option in (_normalize_option(item) for item in value) if option
    )


def _normalize_option(value) -> tuple[str, ...]:
    if isinstance(value, str):
        value = (value,)
    return tuple(
        dict.fromkeys(str(item).strip() for item in value if str(item).strip())
    )
