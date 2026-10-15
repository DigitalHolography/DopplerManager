from __future__ import annotations

from pathlib import Path

from doppler_manager.processing.core.commands import command_prefix_for_stage
from doppler_manager.processing.core.models import ProcessingJob


def build_holodoppler_call(holo_path: Path, settings_path: Path) -> tuple[str, ...]:
    return (
        *command_prefix_for_stage("hd"),
        "process",
        str(holo_path),
        str(settings_path),
    )


def build_holodoppler_job(
    acquisition_id: str,
    holo_path: Path,
    settings_path: Path,
    destination: Path,
) -> ProcessingJob:
    return ProcessingJob(
        acquisition_id=acquisition_id,
        stage="hd",
        command=build_holodoppler_call(holo_path, settings_path),
        cwd=holo_path.parent,
        description=f"{acquisition_id}: Holodoppler",
        stage_destination=destination,
    )
