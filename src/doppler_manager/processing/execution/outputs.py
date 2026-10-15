from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from doppler_manager.processing.core.models import ProcessingJob
from doppler_manager.processing.core.paths import (
    safe_resolve,
    select_angioeye_h5,
    validate_stage_destination,
)


def prepare_processing_output(
    job: ProcessingJob,
    on_log: Callable[[str], None],
) -> None:
    destination = job.stage_destination
    if destination is None or not destination.exists():
        return

    validate_stage_destination(job, destination)
    if not destination.is_dir():
        raise RuntimeError(f"Refusing to delete non-folder stage output path: {destination}")

    shutil.rmtree(destination)
    on_log(f"[DELETE] Existing result folder -> {destination}")


def install_eyeflow_output(job: ProcessingJob, on_log: Callable[[str], None]) -> None:
    if job.ef_temp_root is None or job.ef_destination is None:
        return

    generated = job.ef_temp_root / job.acquisition_id / f"{job.acquisition_id}_EF"
    if not generated.is_dir():
        raise FileNotFoundError(
            f"Expected EyeFlow output folder was not created: {generated}"
        )

    destination = job.ef_destination
    acquisition_root = destination.parent
    expected_name = f"{job.acquisition_id}_EF"

    resolved_acquisition = safe_resolve(acquisition_root)
    resolved_destination = safe_resolve(destination)
    if destination.name != expected_name or resolved_destination.parent != resolved_acquisition:
        raise RuntimeError(f"Refusing to replace unexpected EyeFlow output path: {destination}")

    acquisition_root.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.move(str(generated), str(destination))
    shutil.rmtree(job.ef_temp_root, ignore_errors=True)
    on_log(f"[OUTPUT] EyeFlow -> {destination}")


def install_angioeye_output(job: ProcessingJob, on_log: Callable[[str], None]) -> None:
    if job.ae_temp_root is None or job.ae_destination is None:
        return

    generated_h5 = select_angioeye_h5(job.ae_temp_root, job.acquisition_id)

    destination = job.ae_destination
    acquisition_root = destination.parent
    expected_name = f"{job.acquisition_id}_AE"

    resolved_acquisition = safe_resolve(acquisition_root)
    resolved_destination = safe_resolve(destination)
    if destination.name != expected_name or resolved_destination.parent != resolved_acquisition:
        raise RuntimeError(f"Refusing to replace unexpected AngioEye output path: {destination}")

    acquisition_root.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)

    target_h5_dir = destination / "h5"
    target_h5_dir.mkdir(parents=True, exist_ok=True)
    target_h5 = target_h5_dir / f"{expected_name}.h5"
    shutil.move(str(generated_h5), str(target_h5))

    for child in job.ae_temp_root.iterdir():
        if child.exists():
            target = destination / child.name
            if target.exists():
                spillover_dir = destination / "raw_output"
                spillover_dir.mkdir(parents=True, exist_ok=True)
                target = spillover_dir / child.name
            shutil.move(str(child), str(target))

    shutil.rmtree(job.ae_temp_root, ignore_errors=True)
    on_log(f"[OUTPUT] AngioEye -> {target_h5}")


def job_temp_root(job: ProcessingJob) -> Optional[Path]:
    if job.stage == "ef":
        return job.ef_temp_root
    if job.stage == "ae":
        return job.ae_temp_root
    return None
