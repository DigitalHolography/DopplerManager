from __future__ import annotations

import sys


PROCESSING_STAGES = ("hd", "dv", "ef", "ae")
STAGE_OUTPUT_SUFFIXES = {
    "hd": "_HD",
    "dv": "_DV",
    "ef": "_EF",
    "ae": "_AE",
}
DEFAULT_EYEFLOW_PIPELINES = ("waveform_shape_metrics",)
DEFAULT_ANGIOEYE_PIPELINES = ("waveform_shape_metrics",)
DEFAULT_PIPELINES_BY_STAGE = {
    "ef": DEFAULT_EYEFLOW_PIPELINES,
    "ae": DEFAULT_ANGIOEYE_PIPELINES,
}
PIPELINE_SETTINGS_FOLDERS = {
    "ef": "eyeflow",
    "ae": "angioeye",
}
PIPELINE_SETTINGS_TOOLS = {
    "ef": "eyeflow",
    "ae": "angioeye",
}
PROGRESS_LOG_PREFIX = "\r"
PROCESSING_CLI_SENTINEL = "--dm-processing-cli"

COMMAND_ENV_VARS = {
    "hd": "DM_HOLODOPPLER_COMMAND",
    "dv": "DM_DOPPLERVIEW_COMMAND",
    "ef": "DM_EYEFLOW_COMMAND",
    "ae": "DM_ANGIOEYE_COMMAND",
}

DEFAULT_COMMAND_PREFIXES = {
    "hd": (
        sys.executable,
        "-c",
        "from holodoppler.cli import main; raise SystemExit(main())",
    ),
    "dv": (sys.executable, "-m", "dopplerview.cli"),
    "ef": (
        sys.executable,
        "-m",
        "doppler_manager._external_cli_runner",
        "eyeflow",
    ),
    "ae": (
        sys.executable,
        "-m",
        "doppler_manager._external_cli_runner",
        "angioeye",
    ),
}

DEFAULT_STAGE_MODULES = {
    "hd": "holodoppler",
    "dv": "dopplerview.cli",
    "ef": "eye_flow",
    "ae": "angio_eye",
}

