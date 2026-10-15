from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from doppler_manager.processing.runtimes import (
    runtime_available,
    runtime_command_prefix,
)

from .constants import (
    COMMAND_ENV_VARS,
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
    if stage in PROCESSING_STAGES:
        return runtime_command_prefix(stage)
    raise ValueError(f"Unknown processing stage: {stage}")


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
    if stage in PROCESSING_STAGES:
        return runtime_available(stage)
    return False
