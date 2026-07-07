from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Sequence

from doppler_manager._external_cli_runner import CLI_TOOLS, _find_uv_git_cli

from .constants import (
    COMMAND_ENV_VARS,
    DEFAULT_COMMAND_PREFIXES,
    DEFAULT_STAGE_MODULES,
    PIPELINE_SETTINGS_TOOLS,
    PROCESSING_CLI_SENTINEL,
    PROCESSING_STAGES,
)


def command_prefix_for_stage(stage: str) -> tuple[str, ...]:
    env_var = COMMAND_ENV_VARS[stage]
    override = os.getenv(env_var, "").strip()
    if override:
        return (override,)
    if getattr(sys, "frozen", False):
        return (sys.executable, PROCESSING_CLI_SENTINEL, stage)
    return DEFAULT_COMMAND_PREFIXES[stage]


def missing_default_processing_tools(stages: Sequence[str]) -> list[str]:
    missing: list[str] = []
    for stage in PROCESSING_STAGES:
        if stage not in stages:
            continue
        if os.getenv(COMMAND_ENV_VARS[stage], "").strip():
            continue
        if not default_processing_tool_available(stage):
            missing.append(stage)
    return missing


def default_processing_tool_available(stage: str) -> bool:
    if getattr(sys, "frozen", False) and stage in {"ef", "ae"}:
        return True

    module_name = DEFAULT_STAGE_MODULES[stage]
    try:
        module_spec = importlib.util.find_spec(module_name)
    except (ImportError, ValueError):
        module_spec = None
    if module_spec is not None:
        return True

    tool_name = PIPELINE_SETTINGS_TOOLS.get(stage)
    if tool_name is None:
        return False
    return _find_uv_git_cli(CLI_TOOLS[tool_name]) is not None

