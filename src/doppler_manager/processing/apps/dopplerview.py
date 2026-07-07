from __future__ import annotations

from pathlib import Path

from doppler_manager.processing.core.commands import command_prefix_for_stage
from doppler_manager.processing.core.models import ProcessingJob


def build_dopplerview_call(holo_path: Path) -> tuple[str, ...]:
    return (
        *command_prefix_for_stage("dv"),
        str(holo_path),
        "--config_mode",
        "local",
    )


def build_dopplerview_job(
    acquisition_id: str,
    holo_path: Path,
    destination: Path,
) -> ProcessingJob:
    return ProcessingJob(
        acquisition_id=acquisition_id,
        stage="dv",
        command=build_dopplerview_call(holo_path),
        cwd=holo_path.parent,
        description=f"{acquisition_id}: DopplerView",
        stage_destination=destination,
    )
