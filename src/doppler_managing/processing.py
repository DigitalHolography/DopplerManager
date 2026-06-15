from __future__ import annotations

import codecs
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import AcquisitionResult


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
PROGRESS_LOG_PREFIX = "\r"

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
        "doppler_managing._external_cli_runner",
        "eyeflow",
    ),
    "ae": (
        sys.executable,
        "-m",
        "doppler_managing._external_cli_runner",
        "angioeye",
    ),
}

DEFAULT_STAGE_MODULES = {
    "hd": "holodoppler",
    "dv": "dopplerview.cli",
    "ef": "eye_flow",
    "ae": "angio_eye",
}

REPO_PROCESSING_DEFAULTS = Path(__file__).resolve().parents[2] / "processing_defaults"
REQUIRED_HOLODOPPLER_SETTINGS_KEYS = ("temporal_transformation",)


def bundled_holodoppler_settings_dir() -> Path:
    return REPO_PROCESSING_DEFAULTS / "holodoppler"

@dataclass(frozen=True)
class ProcessingJob:
    acquisition_id: str
    stage: str
    command: tuple[str, ...]
    cwd: Path
    description: str
    ef_temp_root: Optional[Path] = None
    ef_destination: Optional[Path] = None
    ae_temp_root: Optional[Path] = None
    ae_destination: Optional[Path] = None
    stage_destination: Optional[Path] = None


@dataclass(frozen=True)
class JobResult:
    job: ProcessingJob
    returncode: int

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


def command_prefix_for_stage(stage: str) -> tuple[str, ...]:
    env_var = COMMAND_ENV_VARS[stage]
    override = os.getenv(env_var, "").strip()
    if override:
        return (override,)
    return DEFAULT_COMMAND_PREFIXES[stage]


def missing_default_processing_tools(stages: Sequence[str]) -> list[str]:
    missing: list[str] = []
    for stage in PROCESSING_STAGES:
        if stage not in stages:
            continue
        if os.getenv(COMMAND_ENV_VARS[stage], "").strip():
            continue
        module_name = DEFAULT_STAGE_MODULES[stage]
        try:
            module_spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError):
            module_spec = None
        if module_spec is None:
            missing.append(stage)
    return missing


def discover_holodoppler_settings(root: Path | str) -> list[Path]:
    root_path = Path(root).expanduser()
    candidates: list[Path] = []

    env_file = os.getenv("DM_HOLODOPPLER_SETTINGS")
    if env_file:
        candidates.append(Path(env_file).expanduser())

    env_dir = os.getenv("DM_HOLODOPPLER_SETTINGS_DIR")
    if env_dir:
        candidates.append(Path(env_dir).expanduser())

    candidates.extend(
        [
            bundled_holodoppler_settings_dir(),
            Path.cwd() / "processing_defaults" / "holodoppler",
            Path.cwd() / "parameters",
            Path.cwd() / "HoloDopplerPython" / "parameters",
            root_path / "parameters",
            root_path / "HoloDopplerPython" / "parameters",
        ]
    )

    settings: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        for path in holodoppler_settings_from_path(candidate):
            resolved = _safe_resolve(path)
            if resolved not in seen:
                seen.add(resolved)
                settings.append(path)
    return sorted(settings, key=lambda item: item.name.lower())


def holodoppler_settings_from_path(path: Path | str) -> list[Path]:
    value = str(path).strip()
    if not value:
        return []

    candidate = Path(value).expanduser()
    if candidate.is_file() and candidate.suffix.lower() == ".json":
        return [candidate]
    if candidate.is_dir():
        return sorted(candidate.glob("*.json"), key=lambda item: item.name.lower())
    return []


def preferred_holodoppler_settings(settings: Sequence[Path]) -> Optional[Path]:
    if not settings:
        return None
    compatible = [path for path in settings if _has_settings_keys(path, REQUIRED_HOLODOPPLER_SETTINGS_KEYS)]
    if compatible:
        settings = compatible
    preferred_names = (
        "default_parameters.json",
        "default_parameters_debug.json",
        "default_parameters_lightest.json",
        "default_parameters_cine.json",
    )
    by_name = {path.name.lower(): path for path in settings}
    for name in preferred_names:
        if name in by_name:
            return by_name[name]
    return settings[0]


def available_pipelines_for_stage(stage: str) -> tuple[str, ...]:
    visibility = _pipeline_visibility(stage)
    configured = tuple(visibility)
    defaults = DEFAULT_PIPELINES_BY_STAGE[stage]
    return _dedupe_strings((*configured, *defaults))


def default_pipelines_for_stage(stage: str) -> tuple[str, ...]:
    visibility = _pipeline_visibility(stage)
    selected = tuple(name for name, enabled in visibility.items() if enabled)
    if selected:
        return selected
    return DEFAULT_PIPELINES_BY_STAGE[stage]


def ensure_eyeflow_pipeline_file(
    cache_dir: Path,
    pipelines: Optional[Sequence[str]] = None,
) -> Path:
    pipeline_path = _safe_resolve(cache_dir) / "processing" / "eyeflow_pipelines.txt"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    selected_pipelines = _normalize_pipeline_selection(
        "ef",
        pipelines,
        label="EyeFlow",
    )
    desired = "\n".join(selected_pipelines) + "\n"
    if (
        not pipeline_path.exists()
        or pipeline_path.read_text(encoding="utf-8", errors="replace") != desired
    ):
        pipeline_path.write_text(desired, encoding="utf-8")
    return pipeline_path


def ensure_angioeye_pipeline_file(
    cache_dir: Path,
    pipelines: Optional[Sequence[str]] = None,
) -> Path:
    pipeline_path = _safe_resolve(cache_dir) / "processing" / "angioeye_pipelines.txt"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    selected_pipelines = _normalize_pipeline_selection(
        "ae",
        pipelines,
        label="AngioEye",
    )
    desired = "\n".join(selected_pipelines) + "\n"
    if (
        not pipeline_path.exists()
        or pipeline_path.read_text(encoding="utf-8", errors="replace") != desired
    ):
        pipeline_path.write_text(desired, encoding="utf-8")
    return pipeline_path


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
            or _stage_needs_processing(acquisition, stage)
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
    cache_dir = _safe_resolve(cache_dir)
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

        holo_path = _source_holo_path(acquisition)
        acquisition_dir = _acquisition_dir(acquisition, holo_path)

        if "hd" in acquisition_stage_set:
            _require_file(holo_path, acquisition_id, "source .holo")
            assert hd_settings_path is not None
            destination = _stage_output_dir(acquisition_dir, acquisition_id, "hd")
            jobs.append(
                ProcessingJob(
                    acquisition_id=acquisition_id,
                    stage="hd",
                    command=(
                        *command_prefix_for_stage("hd"),
                        "process",
                        str(holo_path),
                        str(hd_settings_path),
                    ),
                    cwd=holo_path.parent,
                    description=f"{acquisition_id}: Holodoppler",
                    stage_destination=destination,
                )
            )

        if "dv" in acquisition_stage_set:
            _require_file(holo_path, acquisition_id, "source .holo")
            if "hd" not in acquisition_stage_set:
                _require_stage_h5(acquisition, "hd")
            destination = _stage_output_dir(acquisition_dir, acquisition_id, "dv")
            jobs.append(
                ProcessingJob(
                    acquisition_id=acquisition_id,
                    stage="dv",
                    command=(
                        *command_prefix_for_stage("dv"),
                        str(holo_path),
                        "--config_mode",
                        "local",
                    ),
                    cwd=holo_path.parent,
                    description=f"{acquisition_id}: DopplerView",
                    stage_destination=destination,
                )
            )

        if "ef" in acquisition_stage_set:
            _require_file(holo_path, acquisition_id, "source .holo")
            if "hd" not in acquisition_stage_set:
                _require_stage_h5(acquisition, "hd")
            assert eyeflow_pipeline_file is not None
            temp_root = _eyeflow_temp_root(cache_dir, acquisition_id)
            destination = _stage_output_dir(acquisition_dir, acquisition_id, "ef")
            jobs.append(
                ProcessingJob(
                    acquisition_id=acquisition_id,
                    stage="ef",
                    command=(
                        *command_prefix_for_stage("ef"),
                        "--data",
                        str(holo_path),
                        "--pipelines",
                        str(eyeflow_pipeline_file),
                        "--output",
                        str(temp_root),
                    ),
                    cwd=holo_path.parent,
                    description=f"{acquisition_id}: EyeFlow",
                    ef_temp_root=temp_root,
                    ef_destination=destination,
                    stage_destination=destination,
                )
            )

        if "ae" in acquisition_stage_set:
            _require_file(holo_path, acquisition_id, "source .holo")
            if "ef" not in acquisition_stage_set:
                _require_stage_h5(acquisition, "ef")
            assert angioeye_pipeline_file is not None
            ef_h5_path = (
                _expected_eyeflow_h5_path(acquisition_id, acquisition_dir)
                if "ef" in acquisition_stage_set
                else _preferred_stage_h5(acquisition, "ef")
            )
            temp_root = _angioeye_temp_root(cache_dir, acquisition_id)
            destination = _stage_output_dir(acquisition_dir, acquisition_id, "ae")
            jobs.append(
                ProcessingJob(
                    acquisition_id=acquisition_id,
                    stage="ae",
                    command=(
                        *command_prefix_for_stage("ae"),
                        "--data",
                        str(ef_h5_path),
                        "--pipelines",
                        str(angioeye_pipeline_file),
                        "--output",
                        str(temp_root),
                        "--trim-source",
                    ),
                    cwd=holo_path.parent,
                    description=f"{acquisition_id}: AngioEye",
                    ae_temp_root=temp_root,
                    ae_destination=destination,
                    stage_destination=destination,
                )
            )

    return jobs


def run_processing_jobs(
    jobs: Sequence[ProcessingJob],
    on_log: Callable[[str], None],
) -> list[JobResult]:
    results: list[JobResult] = []
    failed_acquisitions: set[str] = set()

    for job in jobs:
        if job.acquisition_id in failed_acquisitions:
            on_log(f"[SKIP] {job.description}: upstream stage failed.")
            continue

        on_log(f"[START] {job.description}")

        try:
            prepare_processing_output(job, on_log)
        except Exception as exc:  # noqa: BLE001
            result = JobResult(job=job, returncode=1)
            results.append(result)
            failed_acquisitions.add(job.acquisition_id)
            on_log(f"[FAIL] Could not prepare {job.description}: {exc}")
            continue

        on_log(f"[CMD] {format_command(job.command)}")
        result = _run_single_job(job, on_log)
        results.append(result)

        if result.succeeded and job.stage == "ef":
            try:
                install_eyeflow_output(job, on_log)
            except Exception as exc:  # noqa: BLE001
                on_log(f"[FAIL] Could not install EyeFlow output: {exc}")
                result = JobResult(job=job, returncode=1)
                results[-1] = result

        if result.succeeded and job.stage == "ae":
            try:
                install_angioeye_output(job, on_log)
            except Exception as exc:  # noqa: BLE001
                on_log(f"[FAIL] Could not install AngioEye output: {exc}")
                result = JobResult(job=job, returncode=1)
                results[-1] = result

        if result.succeeded:
            on_log(f"[OK] {job.description}")
        else:
            failed_acquisitions.add(job.acquisition_id)
            on_log(f"[FAIL] {job.description} exited with code {result.returncode}.")

    return results


def prepare_processing_output(
    job: ProcessingJob,
    on_log: Callable[[str], None],
) -> None:
    destination = job.stage_destination
    if destination is None or not destination.exists():
        return

    _validate_stage_destination(job, destination)
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
    acquisition_dir = destination.parent
    expected_name = f"{job.acquisition_id}_EF"

    resolved_acquisition = _safe_resolve(acquisition_dir)
    resolved_destination = _safe_resolve(destination)
    if destination.name != expected_name or resolved_destination.parent != resolved_acquisition:
        raise RuntimeError(f"Refusing to replace unexpected EyeFlow output path: {destination}")

    acquisition_dir.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.move(str(generated), str(destination))
    shutil.rmtree(job.ef_temp_root, ignore_errors=True)
    on_log(f"[OUTPUT] EyeFlow -> {destination}")


def install_angioeye_output(job: ProcessingJob, on_log: Callable[[str], None]) -> None:
    if job.ae_temp_root is None or job.ae_destination is None:
        return

    generated_h5 = _select_angioeye_h5(job.ae_temp_root, job.acquisition_id)

    destination = job.ae_destination
    acquisition_dir = destination.parent
    expected_name = f"{job.acquisition_id}_AE"

    resolved_acquisition = _safe_resolve(acquisition_dir)
    resolved_destination = _safe_resolve(destination)
    if destination.name != expected_name or resolved_destination.parent != resolved_acquisition:
        raise RuntimeError(f"Refusing to replace unexpected AngioEye output path: {destination}")

    acquisition_dir.mkdir(parents=True, exist_ok=True)
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


def format_command(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return " ".join(_quote(arg) for arg in command)


def _run_single_job(job: ProcessingJob, on_log: Callable[[str], None]) -> JobResult:
    temp_root = _job_temp_root(job)
    if temp_root is not None:
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        process = subprocess.Popen(
            list(job.command),
            cwd=str(job.cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            bufsize=0,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        on_log(f"[FAIL] Command not found: {job.command[0]}")
        return JobResult(job=job, returncode=127)

    assert process.stdout is not None
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    buffer = ""
    pending_carriage_return = False
    current_line_is_progress = False

    def emit_buffer(*, progress: bool) -> None:
        nonlocal buffer
        text = buffer.strip()
        if text:
            prefix = PROGRESS_LOG_PREFIX if progress else ""
            on_log(f"{prefix}{text}")
        buffer = ""

    def handle_output_char(char: str) -> None:
        nonlocal buffer, pending_carriage_return, current_line_is_progress
        if pending_carriage_return:
            if char == "\n":
                emit_buffer(progress=current_line_is_progress)
                current_line_is_progress = False
                pending_carriage_return = False
                return
            if char == "\r":
                return
            emit_buffer(progress=True)
            current_line_is_progress = True
            pending_carriage_return = False

        if char == "\r":
            pending_carriage_return = True
        elif char == "\n":
            emit_buffer(progress=current_line_is_progress)
            current_line_is_progress = False
        else:
            buffer += char

    while True:
        chunk = process.stdout.read(1)
        if chunk == b"" and process.poll() is not None:
            break
        if chunk == b"":
            time.sleep(0.05)
            continue
        for char in decoder.decode(chunk):
            handle_output_char(char)

    for char in decoder.decode(b"", final=True):
        handle_output_char(char)

    trailing = buffer.strip()
    if trailing:
        prefix = PROGRESS_LOG_PREFIX if current_line_is_progress else ""
        on_log(f"{prefix}{trailing}")

    return JobResult(job=job, returncode=process.wait())


def _source_holo_path(acquisition: AcquisitionResult) -> Path:
    if acquisition.source_holo is None:
        raise FileNotFoundError(
            f"{acquisition.acquisition_id}: source .holo file was not indexed."
        )
    return Path(acquisition.source_holo.path)


def _acquisition_dir(acquisition: AcquisitionResult, holo_path: Path) -> Path:
    if acquisition.acquisition_dir is not None:
        return Path(acquisition.acquisition_dir.path)
    return holo_path.with_suffix("")


def _require_file(path: Path, acquisition_id: str, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{acquisition_id}: {label} not found: {path}")


def _require_stage_h5(acquisition: AcquisitionResult, stage: str) -> None:
    result = acquisition.stages[stage]
    if not any(Path(file_ref.path).is_file() for file_ref in result.h5_files):
        raise FileNotFoundError(
            f"{acquisition.acquisition_id}: {stage.upper()} .h5 file is required "
            "before running downstream stages."
        )


def _stage_needs_processing(acquisition: AcquisitionResult, stage: str) -> bool:
    result = acquisition.stages.get(stage)
    if result is None:
        return True
    return result.status != "complete"


def _preferred_stage_h5(acquisition: AcquisitionResult, stage: str) -> Path:
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


def _expected_eyeflow_h5_path(acquisition_id: str, acquisition_dir: Path) -> Path:
    return acquisition_dir / f"{acquisition_id}_EF" / "h5" / f"{acquisition_id}_EF.h5"


def _stage_output_dir(acquisition_dir: Path, acquisition_id: str, stage: str) -> Path:
    return acquisition_dir / f"{acquisition_id}{STAGE_OUTPUT_SUFFIXES[stage]}"


def _select_angioeye_h5(temp_root: Path, acquisition_id: str) -> Path:
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


def _job_temp_root(job: ProcessingJob) -> Optional[Path]:
    if job.stage == "ef":
        return job.ef_temp_root
    if job.stage == "ae":
        return job.ae_temp_root
    return None


def _eyeflow_temp_root(cache_dir: Path, acquisition_id: str) -> Path:
    token = time.strftime("%Y%m%d_%H%M%S")
    safe_id = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in acquisition_id
    )
    return _safe_resolve(cache_dir) / "processing" / "eyeflow_runs" / f"{safe_id}_{token}"


def _angioeye_temp_root(cache_dir: Path, acquisition_id: str) -> Path:
    token = time.strftime("%Y%m%d_%H%M%S")
    safe_id = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in acquisition_id
    )
    return _safe_resolve(cache_dir) / "processing" / "angioeye_runs" / f"{safe_id}_{token}"


def _validate_stage_destination(job: ProcessingJob, destination: Path) -> None:
    suffix = STAGE_OUTPUT_SUFFIXES.get(job.stage)
    if suffix is None:
        raise RuntimeError(f"Unknown processing stage: {job.stage}")

    expected_name = f"{job.acquisition_id}{suffix}"
    resolved_parent = _safe_resolve(destination.parent)
    resolved_destination = _safe_resolve(destination)
    if destination.name != expected_name or resolved_destination.parent != resolved_parent:
        raise RuntimeError(f"Refusing to delete unexpected stage output path: {destination}")


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _pipeline_visibility(stage: str) -> dict[str, bool]:
    settings_path = (
        REPO_PROCESSING_DEFAULTS
        / PIPELINE_SETTINGS_FOLDERS[stage]
        / "default_settings.json"
    )
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    visibility = payload.get("pipeline_visibility")
    if not isinstance(visibility, dict):
        return {}
    return {
        str(name): bool(enabled)
        for name, enabled in visibility.items()
        if str(name).strip()
    }


def _normalize_pipeline_selection(
    stage: str,
    pipelines: Optional[Sequence[str]],
    *,
    label: str,
) -> tuple[str, ...]:
    selected = (
        default_pipelines_for_stage(stage)
        if pipelines is None
        else _dedupe_strings(
            str(pipeline).strip()
            for pipeline in pipelines
            if str(pipeline).strip()
        )
    )
    if not selected:
        raise ValueError(f"Select at least one {label} pipeline.")
    return selected


def _dedupe_strings(values: Iterable[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def _has_settings_keys(path: Path, keys: Sequence[str]) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return all(key in payload for key in keys)


def _quote(value: str) -> str:
    if not value or any(char.isspace() for char in value):
        return "'" + value.replace("'", "'\"'\"'") + "'"
    return value
