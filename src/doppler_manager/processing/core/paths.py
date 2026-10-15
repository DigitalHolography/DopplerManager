from __future__ import annotations

from pathlib import Path

from doppler_manager.models import AcquisitionResult

from .constants import STAGE_OUTPUT_SUFFIXES
from .models import ProcessingJob


def source_holo_path(acquisition: AcquisitionResult) -> Path:
    if acquisition.source_holo is None:
        raise FileNotFoundError(
            f"{acquisition.acquisition_id}: source .holo file was not indexed."
        )
    return Path(acquisition.source_holo.path)


def acquisition_dir(acquisition: AcquisitionResult, holo_path: Path) -> Path:
    if acquisition.acquisition_dir is not None:
        return Path(acquisition.acquisition_dir.path)
    return holo_path.with_suffix("")


def require_file(path: Path, acquisition_id: str, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{acquisition_id}: {label} not found: {path}")


def require_stage_h5(acquisition: AcquisitionResult, stage: str) -> None:
    result = acquisition.stages[stage]
    if not any(Path(file_ref.path).is_file() for file_ref in result.h5_files):
        raise FileNotFoundError(
            f"{acquisition.acquisition_id}: {stage.upper()} .h5 file is required "
            "before running downstream stages."
        )


def stage_needs_processing(acquisition: AcquisitionResult, stage: str) -> bool:
    result = acquisition.stages.get(stage)
    if result is None:
        return True
    return result.status != "complete"


def preferred_stage_h5(acquisition: AcquisitionResult, stage: str) -> Path:
    result = acquisition.stages[stage]
    h5_paths = [Path(file_ref.path) for file_ref in result.h5_files]
    existing_h5_paths = [path for path in h5_paths if path.is_file()]
    if not existing_h5_paths:
        raise FileNotFoundError(
            f"{acquisition.acquisition_id}: {stage.upper()} .h5 file is required "
            "before running downstream stages."
        )

    expected_name = f"{acquisition.acquisition_id}_{stage.upper()}.h5"
    for path in existing_h5_paths:
        if path.name == expected_name:
            return path
    return existing_h5_paths[0]


def expected_eyeflow_h5_path(acquisition_id: str, acquisition_dir: Path) -> Path:
    return acquisition_dir / f"{acquisition_id}_EF" / "h5" / f"{acquisition_id}_EF.h5"


def stage_output_dir(acquisition_dir: Path, acquisition_id: str, stage: str) -> Path:
    return acquisition_dir / f"{acquisition_id}{STAGE_OUTPUT_SUFFIXES[stage]}"


def select_angioeye_h5(temp_root: Path, acquisition_id: str) -> Path:
    if not temp_root.is_dir():
        raise FileNotFoundError(f"Expected AngioEye output folder was not created: {temp_root}")

    h5_paths = sorted(temp_root.rglob("*.h5"), key=lambda path: str(path).lower())
    if not h5_paths:
        raise FileNotFoundError(f"No AngioEye .h5 output was created under: {temp_root}")

    preferred_names = (
        f"{acquisition_id}_EF_pipelines_result.h5",
        f"{acquisition_id}_pipelines_result.h5",
        f"{acquisition_id}_AE.h5",
    )
    by_name = {path.name: path for path in h5_paths}
    for name in preferred_names:
        if name in by_name:
            return by_name[name]
    return h5_paths[0]


def validate_stage_destination(job: ProcessingJob, destination: Path) -> None:
    suffix = STAGE_OUTPUT_SUFFIXES.get(job.stage)
    if suffix is None:
        raise RuntimeError(f"Unknown processing stage: {job.stage}")

    expected_name = f"{job.acquisition_id}{suffix}"
    resolved_parent = safe_resolve(destination.parent)
    resolved_destination = safe_resolve(destination)
    if destination.name != expected_name or resolved_destination.parent != resolved_parent:
        raise RuntimeError(f"Refusing to delete unexpected stage output path: {destination}")


def safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()
