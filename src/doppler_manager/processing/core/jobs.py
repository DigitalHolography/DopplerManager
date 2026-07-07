from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from doppler_manager.models import AcquisitionResult

from doppler_manager.processing.apps.angioeye import angioeye_temp_root, build_angioeye_job
from doppler_manager.processing.apps.dopplerview import build_dopplerview_job
from doppler_manager.processing.apps.eyeflow import build_eyeflow_job, eyeflow_temp_root
from doppler_manager.processing.apps.holodoppler import build_holodoppler_job
from doppler_manager.processing.config.pipelines import (
    ensure_angioeye_pipeline_file,
    ensure_eyeflow_pipeline_file,
)

from .constants import PROCESSING_STAGES
from .models import ProcessingJob
from .paths import (
    acquisition_dir,
    expected_eyeflow_h5_path,
    preferred_stage_h5,
    require_file,
    require_stage_h5,
    safe_resolve,
    source_holo_path,
    stage_needs_processing,
    stage_output_dir,
)


def needed_processing_stages(
    acquisitions: Sequence[AcquisitionResult],
    stages: Sequence[str],
    *,
    only_incomplete: bool = False,
) -> list[str]:
    needed = {
        stage
        for acquisition in acquisitions
        for stage in processing_stages_for_acquisition(
            acquisition,
            stages,
            only_incomplete=only_incomplete,
        )
    }
    return [stage for stage in PROCESSING_STAGES if stage in needed]


def processing_stages_for_acquisition(
    acquisition: AcquisitionResult,
    stages: Sequence[str],
    *,
    only_incomplete: bool = False,
) -> list[str]:
    selected_stage_set = set(stages)
    invalid_stages = selected_stage_set - set(PROCESSING_STAGES)
    if invalid_stages:
        raise ValueError(
            f"Unknown processing stage(s): {', '.join(sorted(invalid_stages))}"
        )

    return [
        stage
        for stage in PROCESSING_STAGES
        if stage in selected_stage_set
        and (
            not only_incomplete
            or stage_needs_processing(acquisition, stage)
        )
    ]


def build_processing_jobs(
    acquisitions: Sequence[AcquisitionResult],
    selected_ids: Sequence[str],
    stages: Sequence[str],
    *,
    hd_settings_path: Optional[Path],
    cache_dir: Path,
    only_incomplete: bool = False,
    eyeflow_pipelines: Optional[Sequence[str]] = None,
    angioeye_pipelines: Optional[Sequence[str]] = None,
) -> list[ProcessingJob]:
    cache_dir = safe_resolve(cache_dir)
    selected_stage_set = set(stages)
    invalid_stages = selected_stage_set - set(PROCESSING_STAGES)
    if invalid_stages:
        raise ValueError(
            f"Unknown processing stage(s): {', '.join(sorted(invalid_stages))}"
        )

    by_id = {acquisition.acquisition_id: acquisition for acquisition in acquisitions}
    missing_ids = [
        acquisition_id for acquisition_id in selected_ids if acquisition_id not in by_id
    ]
    if missing_ids:
        raise ValueError(f"Unknown acquisition(s): {', '.join(missing_ids)}")

    stages_by_acquisition = {
        acquisition_id: processing_stages_for_acquisition(
            by_id[acquisition_id],
            stages,
            only_incomplete=only_incomplete,
        )
        for acquisition_id in selected_ids
    }
    needed_stage_set = {
        stage
        for acquisition_stages in stages_by_acquisition.values()
        for stage in acquisition_stages
    }

    if "hd" in needed_stage_set:
        if hd_settings_path is None:
            raise ValueError("Select a HoloDoppler settings JSON file.")
        if not hd_settings_path.is_file():
            raise FileNotFoundError(
                f"HoloDoppler settings file not found: {hd_settings_path}"
            )

    eyeflow_pipeline_file = (
        ensure_eyeflow_pipeline_file(cache_dir, eyeflow_pipelines)
        if "ef" in needed_stage_set
        else None
    )
    angioeye_pipeline_file = (
        ensure_angioeye_pipeline_file(cache_dir, angioeye_pipelines)
        if "ae" in needed_stage_set
        else None
    )

    jobs: list[ProcessingJob] = []
    for acquisition_id in selected_ids:
        acquisition = by_id[acquisition_id]
        acquisition_stage_set = set(stages_by_acquisition[acquisition_id])
        if not acquisition_stage_set:
            continue

        holo_path = source_holo_path(acquisition)
        acquisition_root = acquisition_dir(acquisition, holo_path)

        if "hd" in acquisition_stage_set:
            require_file(holo_path, acquisition_id, "source .holo")
            assert hd_settings_path is not None
            destination = stage_output_dir(acquisition_root, acquisition_id, "hd")
            jobs.append(
                build_holodoppler_job(
                    acquisition_id,
                    holo_path,
                    hd_settings_path,
                    destination,
                )
            )

        if "dv" in acquisition_stage_set:
            require_file(holo_path, acquisition_id, "source .holo")
            if "hd" not in acquisition_stage_set:
                require_stage_h5(acquisition, "hd")
            destination = stage_output_dir(acquisition_root, acquisition_id, "dv")
            jobs.append(build_dopplerview_job(acquisition_id, holo_path, destination))

        if "ef" in acquisition_stage_set:
            require_file(holo_path, acquisition_id, "source .holo")
            if "hd" not in acquisition_stage_set:
                require_stage_h5(acquisition, "hd")
            if "dv" not in acquisition_stage_set:
                require_stage_h5(acquisition, "dv")
            assert eyeflow_pipeline_file is not None
            temp_root = eyeflow_temp_root(cache_dir, acquisition_id)
            destination = stage_output_dir(acquisition_root, acquisition_id, "ef")
            jobs.append(
                build_eyeflow_job(
                    acquisition_id,
                    holo_path,
                    eyeflow_pipeline_file,
                    temp_root,
                    destination,
                )
            )

        if "ae" in acquisition_stage_set:
            require_file(holo_path, acquisition_id, "source .holo")
            if "ef" not in acquisition_stage_set:
                require_stage_h5(acquisition, "ef")
            assert angioeye_pipeline_file is not None
            ef_h5_path = (
                expected_eyeflow_h5_path(acquisition_id, acquisition_root)
                if "ef" in acquisition_stage_set
                else preferred_stage_h5(acquisition, "ef")
            )
            temp_root = angioeye_temp_root(cache_dir, acquisition_id)
            destination = stage_output_dir(acquisition_root, acquisition_id, "ae")
            jobs.append(
                build_angioeye_job(
                    acquisition_id,
                    holo_path,
                    ef_h5_path,
                    angioeye_pipeline_file,
                    temp_root,
                    destination,
                )
            )

    return jobs
