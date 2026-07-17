from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from doppler_manager._external_cli_runner import _find_uv_git_cli

from .apps.angioeye import angioeye_temp_root, build_angioeye_call, build_angioeye_job
from .apps.angioeye_postprocess import (
    AngioEyePostprocessDescriptor,
    POSTPROCESS_INPUT_METHODS,
    build_angioeye_postprocess_call,
    build_angioeye_postprocess_job,
    discover_angioeye_postprocesses,
    input_method_for_count,
    proposed_angioeye_postprocesses,
)
from .apps.dopplerview import build_dopplerview_call, build_dopplerview_job
from .apps.eyeflow import build_eyeflow_call, build_eyeflow_job, eyeflow_temp_root
from .apps.holodoppler import build_holodoppler_call, build_holodoppler_job
from .config import defaults as _defaults
from .config import holodoppler_settings as _holodoppler_settings
from .config import pipelines as _pipelines
from .config.postprocesses import (
    ensure_angioeye_postprocess_pipeline_file,
    ensure_angioeye_postprocess_file,
)
from .core import commands as _commands
from .core import jobs as _jobs
from .core.commands import command_prefix_for_stage
from .core.constants import (
    COMMAND_ENV_VARS,
    DEFAULT_ANGIOEYE_PIPELINES,
    DEFAULT_COMMAND_PREFIXES,
    DEFAULT_EYEFLOW_PIPELINES,
    DEFAULT_PIPELINES_BY_STAGE,
    DEFAULT_STAGE_MODULES,
    PIPELINE_SETTINGS_FOLDERS,
    PIPELINE_SETTINGS_TOOLS,
    PROCESSING_CLI_SENTINEL,
    PROCESSING_STAGES,
    PROGRESS_LOG_PREFIX,
    STAGE_OUTPUT_SUFFIXES,
)
from .core.models import JobResult, ProcessingJob
from .core.paths import (
    acquisition_dir as _acquisition_dir,
    expected_eyeflow_h5_path as _expected_eyeflow_h5_path,
    preferred_stage_h5 as _preferred_stage_h5,
    require_file as _require_file,
    require_stage_h5 as _require_stage_h5,
    safe_resolve as _safe_resolve,
    select_angioeye_h5 as _select_angioeye_h5,
    source_holo_path as _source_holo_path,
    stage_needs_processing as _stage_needs_processing,
    stage_output_dir as _stage_output_dir,
    validate_stage_destination as _validate_stage_destination,
)
from .execution.outputs import install_angioeye_output, install_eyeflow_output, prepare_processing_output
from .execution.runner import (
    format_command,
    quote as _quote,
    run_processing_jobs,
    run_single_job as _run_single_job,
)
from .config.holodoppler_settings import (
    REQUIRED_HOLODOPPLER_SETTINGS_KEYS,
    has_settings_keys as _has_settings_keys,
    holodoppler_settings_from_path,
    preferred_holodoppler_settings,
)


REPO_PROCESSING_DEFAULTS = _defaults.REPO_PROCESSING_DEFAULTS
_upstream_pipeline_settings_path = _pipelines.upstream_pipeline_settings_path
_upstream_holodoppler_settings_dir = _holodoppler_settings.upstream_holodoppler_settings_dir
_eyeflow_temp_root = eyeflow_temp_root
_angioeye_temp_root = angioeye_temp_root


def _sync_patchable_globals() -> None:
    _commands._find_uv_git_cli = _find_uv_git_cli
    _pipelines._find_uv_git_cli = _find_uv_git_cli
    _defaults.REPO_PROCESSING_DEFAULTS = REPO_PROCESSING_DEFAULTS
    _pipelines.upstream_pipeline_settings_path = _upstream_pipeline_settings_path
    _holodoppler_settings.upstream_holodoppler_settings_dir = _upstream_holodoppler_settings_dir


def processing_defaults_dir() -> Path:
    _sync_patchable_globals()
    return _defaults.processing_defaults_dir()


def bundled_holodoppler_settings_dir() -> Path:
    _sync_patchable_globals()
    return _defaults.bundled_holodoppler_settings_dir()


def discover_holodoppler_settings(root: Path | str) -> list[Path]:
    from .config.holodoppler_settings import (
        discover_holodoppler_settings as _discover_holodoppler_settings,
    )

    _sync_patchable_globals()
    return _discover_holodoppler_settings(root)


def needed_processing_stages(
    acquisitions,
    stages: Sequence[str],
    *,
    only_incomplete: bool = False,
) -> list[str]:
    return _jobs.needed_processing_stages(
        acquisitions,
        stages,
        only_incomplete=only_incomplete,
    )


def processing_stages_for_acquisition(
    acquisition,
    stages: Sequence[str],
    *,
    only_incomplete: bool = False,
) -> list[str]:
    return _jobs.processing_stages_for_acquisition(
        acquisition,
        stages,
        only_incomplete=only_incomplete,
    )


def build_processing_jobs(
    acquisitions,
    selected_ids: Sequence[str],
    stages: Sequence[str],
    *,
    hd_settings_path: Optional[Path],
    cache_dir: Path,
    only_incomplete: bool = False,
    eyeflow_pipelines: Optional[Sequence[str]] = None,
    angioeye_pipelines: Optional[Sequence[str]] = None,
    angioeye_postprocesses: Optional[Sequence[str]] = None,
) -> list[ProcessingJob]:
    _sync_patchable_globals()
    return _jobs.build_processing_jobs(
        acquisitions,
        selected_ids,
        stages,
        hd_settings_path=hd_settings_path,
        cache_dir=cache_dir,
        only_incomplete=only_incomplete,
        eyeflow_pipelines=eyeflow_pipelines,
        angioeye_pipelines=angioeye_pipelines,
        angioeye_postprocesses=angioeye_postprocesses,
    )


def missing_default_processing_tools(stages: Sequence[str]) -> list[str]:
    _sync_patchable_globals()
    return _commands.missing_default_processing_tools(stages)


def available_pipelines_for_stage(stage: str) -> tuple[str, ...]:
    _sync_patchable_globals()
    return _pipelines.available_pipelines_for_stage(stage)


def default_pipelines_for_stage(stage: str) -> tuple[str, ...]:
    _sync_patchable_globals()
    return _pipelines.default_pipelines_for_stage(stage)


def ensure_eyeflow_pipeline_file(
    cache_dir: Path,
    pipelines: Optional[Sequence[str]] = None,
) -> Path:
    _sync_patchable_globals()
    return _pipelines.ensure_eyeflow_pipeline_file(cache_dir, pipelines)


def ensure_angioeye_pipeline_file(
    cache_dir: Path,
    pipelines: Optional[Sequence[str]] = None,
) -> Path:
    _sync_patchable_globals()
    return _pipelines.ensure_angioeye_pipeline_file(cache_dir, pipelines)


def _default_processing_tool_available(stage: str) -> bool:
    _sync_patchable_globals()
    return _commands.default_processing_tool_available(stage)


def _pipeline_visibility(stage: str) -> dict[str, bool]:
    _sync_patchable_globals()
    return _pipelines.pipeline_visibility(stage)


def _default_pipeline_settings_path(stage: str) -> Path | None:
    _sync_patchable_globals()
    return _pipelines.default_pipeline_settings_path(stage)


def _normalize_pipeline_selection(
    stage: str,
    pipelines: Optional[Sequence[str]],
    *,
    label: str,
) -> tuple[str, ...]:
    _sync_patchable_globals()
    return _pipelines.normalize_pipeline_selection(stage, pipelines, label=label)


def _dedupe_strings(values) -> tuple[str, ...]:
    return _pipelines.dedupe_strings(values)


__all__ = [
    "PROCESSING_STAGES",
    "PROGRESS_LOG_PREFIX",
    "PROCESSING_CLI_SENTINEL",
    "ProcessingJob",
    "AngioEyePostprocessDescriptor",
    "POSTPROCESS_INPUT_METHODS",
    "JobResult",
    "available_pipelines_for_stage",
    "build_angioeye_call",
    "build_angioeye_job",
    "build_angioeye_postprocess_call",
    "build_angioeye_postprocess_job",
    "build_dopplerview_call",
    "build_dopplerview_job",
    "build_eyeflow_call",
    "build_eyeflow_job",
    "build_holodoppler_call",
    "build_holodoppler_job",
    "build_processing_jobs",
    "bundled_holodoppler_settings_dir",
    "command_prefix_for_stage",
    "default_pipelines_for_stage",
    "discover_holodoppler_settings",
    "ensure_angioeye_pipeline_file",
    "ensure_angioeye_postprocess_pipeline_file",
    "ensure_angioeye_postprocess_file",
    "ensure_eyeflow_pipeline_file",
    "format_command",
    "holodoppler_settings_from_path",
    "install_angioeye_output",
    "install_eyeflow_output",
    "discover_angioeye_postprocesses",
    "input_method_for_count",
    "missing_default_processing_tools",
    "needed_processing_stages",
    "preferred_holodoppler_settings",
    "prepare_processing_output",
    "processing_defaults_dir",
    "processing_stages_for_acquisition",
    "proposed_angioeye_postprocesses",
    "run_processing_jobs",
]
