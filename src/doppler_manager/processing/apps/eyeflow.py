from __future__ import annotations

import time
from pathlib import Path

from doppler_manager.processing.core.commands import command_prefix_for_stage
from doppler_manager.processing.core.models import ProcessingJob
from doppler_manager.processing.core.paths import safe_resolve


def build_eyeflow_call(
    holo_path: Path,
    pipeline_file: Path,
    output_root: Path,
) -> tuple[str, ...]:
    return (
        *command_prefix_for_stage("ef"),
        "--data",
        str(holo_path),
        "--pipelines",
        str(pipeline_file),
        "--output",
        str(output_root),
    )


def build_eyeflow_job(
    acquisition_id: str,
    holo_path: Path,
    pipeline_file: Path,
    temp_root: Path,
    destination: Path,
) -> ProcessingJob:
    return ProcessingJob(
        acquisition_id=acquisition_id,
        stage="ef",
        command=build_eyeflow_call(holo_path, pipeline_file, temp_root),
        cwd=holo_path.parent,
        description=f"{acquisition_id}: EyeFlow",
        ef_temp_root=temp_root,
        ef_destination=destination,
        stage_destination=destination,
    )


def eyeflow_temp_root(cache_dir: Path, acquisition_id: str) -> Path:
    token = time.strftime("%Y%m%d_%H%M%S")
    safe_id = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in acquisition_id
    )
    return safe_resolve(cache_dir) / "processing" / "eyeflow_runs" / f"{safe_id}_{token}"
