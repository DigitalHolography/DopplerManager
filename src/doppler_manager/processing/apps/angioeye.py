from __future__ import annotations

import time
from pathlib import Path

from doppler_manager.processing.core.commands import command_prefix_for_stage
from doppler_manager.processing.core.models import ProcessingJob
from doppler_manager.processing.core.paths import safe_resolve


def build_angioeye_call(
    holo_path: Path,
    pipeline_file: Path,
    output_root: Path,
    postprocess_file: Path | None = None,
) -> tuple[str, ...]:
    command = (
        *command_prefix_for_stage("ae"),
        "--data",
        str(holo_path),
        "--pipelines",
        str(pipeline_file),
        "--output",
        str(output_root),
    )
    if postprocess_file is not None:
        command += ("--postprocesses", str(postprocess_file))
    return command


def build_angioeye_job(
    acquisition_id: str,
    holo_path: Path,
    pipeline_file: Path,
    temp_root: Path,
    destination: Path,
    postprocess_file: Path | None = None,
) -> ProcessingJob:
    return ProcessingJob(
        acquisition_id=acquisition_id,
        stage="ae",
        command=build_angioeye_call(
            holo_path,
            pipeline_file,
            temp_root,
            postprocess_file,
        ),
        cwd=holo_path.parent,
        description=f"{acquisition_id}: AngioEye",
        ae_temp_root=temp_root,
        ae_destination=destination,
        stage_destination=destination,
    )


def angioeye_temp_root(cache_dir: Path, acquisition_id: str) -> Path:
    token = time.strftime("%Y%m%d_%H%M%S")
    safe_id = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in acquisition_id
    )
    return safe_resolve(cache_dir) / "processing" / "angioeye_runs" / f"{safe_id}_{token}"


# Kept available from the AngioEye app module alongside the pipeline builder.
from .angioeye_postprocess import (  # noqa: E402
    build_angioeye_postprocess_call,
    build_angioeye_postprocess_job,
)
