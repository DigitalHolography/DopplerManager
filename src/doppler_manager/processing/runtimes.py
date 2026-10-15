from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal


RuntimeStage = Literal["hd", "dv", "ef", "ae"]


@dataclass(frozen=True)
class ProcessingRuntime:
    stage: RuntimeStage
    project_name: str
    environment_variable: str
    launcher_args: tuple[str, ...]


RUNTIMES: dict[RuntimeStage, ProcessingRuntime] = {
    "hd": ProcessingRuntime(
        stage="hd",
        project_name="holodoppler",
        environment_variable="DM_HOLODOPPLER_PYTHON",
        launcher_args=(
            "-c",
            "from holodoppler.cli import main; raise SystemExit(main())",
        ),
    ),
    "dv": ProcessingRuntime(
        stage="dv",
        project_name="dopplerview",
        environment_variable="DM_DOPPLERVIEW_PYTHON",
        launcher_args=("-m", "dopplerview.cli"),
    ),
    "ef": ProcessingRuntime(
        stage="ef",
        project_name="eyeflow",
        environment_variable="DM_EYEFLOW_PYTHON",
        launcher_args=(
            "-c",
            "from launcher import cli_main; raise SystemExit(cli_main())",
        ),
    ),
    "ae": ProcessingRuntime(
        stage="ae",
        project_name="angioeye",
        environment_variable="DM_ANGIOEYE_PYTHON",
        launcher_args=(
            "-c",
            "from launcher import cli_main; raise SystemExit(cli_main())",
        ),
    ),
}


class ProcessingRuntimeError(RuntimeError):
    """Raised when an isolated processing runtime cannot answer a request."""


def runtime_project_dir(stage: RuntimeStage) -> Path:
    runtime = RUNTIMES[stage]
    configured_root = os.getenv("DM_PROCESSING_RUNTIME_ROOT", "").strip()
    if configured_root:
        return Path(configured_root).expanduser() / runtime.project_name

    source_root = Path(__file__).resolve().parents[3]
    source_project = source_root / "processing_runtimes" / runtime.project_name
    if source_project.is_dir():
        return source_project

    working_project = Path.cwd() / "processing_runtimes" / runtime.project_name
    if working_project.is_dir():
        return working_project

    executable_project = (
        Path(sys.executable).resolve().parent
        / "processing_runtimes"
        / runtime.project_name
    )
    return executable_project


def runtime_ready_marker(stage: RuntimeStage) -> Path:
    return runtime_project_dir(stage) / ".venv" / ".doppler_manager_ready"


def runtime_python(stage: RuntimeStage) -> Path:
    runtime = RUNTIMES[stage]
    configured_python = os.getenv(runtime.environment_variable, "").strip()
    if configured_python:
        return Path(configured_python).expanduser()

    environment_dir = runtime_project_dir(stage) / ".venv"
    if os.name == "nt":
        return environment_dir / "Scripts" / "python.exe"
    return environment_dir / "bin" / "python"


def runtime_available(stage: RuntimeStage) -> bool:
    python = runtime_python(stage)
    configured_python = os.getenv(RUNTIMES[stage].environment_variable, "").strip()
    return python.is_file() and (
        bool(configured_python) or runtime_ready_marker(stage).is_file()
    )


def runtime_command_prefix(stage: RuntimeStage) -> tuple[str, ...]:
    """Return the command prefix for the selected isolated runtime CLI."""

    return (
        str(runtime_python(stage)),
        *RUNTIMES[stage].launcher_args,
    )


def runtime_catalog(
    stage: RuntimeStage,
    catalog: Literal["pipelines", "postprocesses"],
) -> tuple[tuple[SimpleNamespace, ...], tuple[SimpleNamespace, ...]]:
    """Load catalog metadata from an upstream runtime subprocess."""

    python = runtime_python(stage)
    if not python.is_file():
        raise ProcessingRuntimeError(
            f"{stage.upper()} processing runtime is not installed: {python}. "
            "Run scripts/sync_processing.ps1 or set the runtime Python override."
        )

    project_dir = runtime_project_dir(stage)
    try:
        completed = subprocess.run(
            (str(python), str(_bridge_path()), catalog),
            cwd=project_dir if project_dir.is_dir() else None,
            env=runtime_environment(stage),
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProcessingRuntimeError(
            f"Unable to start {stage.upper()} {catalog} discovery: {exc}"
        ) from exc
    payload = _decode_catalog_response(completed)
    if not payload.get("ok", False):
        error = str(payload.get("error", "Unknown catalog error")).strip()
        raise ProcessingRuntimeError(
            f"Unable to discover {stage.upper()} {catalog}: {error}"
        )

    return (
        _namespace_records(payload.get("available", ())),
        _namespace_records(payload.get("missing", ())),
    )


def run_runtime_cli(stage: RuntimeStage, args: list[str]) -> int:
    """Run an upstream CLI using only its isolated runtime environment."""

    try:
        completed = subprocess.run(
            (*runtime_command_prefix(stage), *args),
            env=runtime_environment(stage),
            check=False,
        )
    except OSError as exc:
        print(
            f"Could not start {stage.upper()} processing runtime: {exc}",
            file=sys.stderr,
        )
        return 1
    return int(completed.returncode)


def _bridge_path() -> Path:
    bridge = Path(__file__).with_name("runtime_bridge.py")
    if bridge.is_file():
        return bridge

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        bundled_bridge = (
            Path(bundle_root) / "doppler_manager" / "processing" / "runtime_bridge.py"
        )
        if bundled_bridge.is_file():
            return bundled_bridge
    return bridge


def runtime_environment(stage: RuntimeStage) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    if stage == "ef":
        project_dir = runtime_project_dir(stage)
        if project_dir.is_dir():
            environment["PYTHONPATH"] = str(project_dir)
    return environment


def _decode_catalog_response(
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    raw = completed.stdout.strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        details = completed.stderr.strip() or raw or "no response"
        raise ProcessingRuntimeError(
            f"Catalog bridge returned invalid JSON: {details}"
        ) from exc

    if not isinstance(payload, dict):
        raise ProcessingRuntimeError("Catalog bridge returned a non-object response.")
    if completed.returncode and "error" not in payload:
        details = completed.stderr.strip() or f"exit code {completed.returncode}"
        payload = {"ok": False, "error": details}
    return payload


def _namespace_records(records: Any) -> tuple[SimpleNamespace, ...]:
    if not isinstance(records, list):
        return ()
    return tuple(
        SimpleNamespace(**record) for record in records if isinstance(record, dict)
    )


__all__ = [
    "ProcessingRuntime",
    "ProcessingRuntimeError",
    "RUNTIMES",
    "RuntimeStage",
    "run_runtime_cli",
    "runtime_available",
    "runtime_catalog",
    "runtime_command_prefix",
    "runtime_environment",
    "runtime_project_dir",
    "runtime_ready_marker",
    "runtime_python",
]
