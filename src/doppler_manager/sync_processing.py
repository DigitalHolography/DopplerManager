from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from doppler_manager.processing.runtimes import RUNTIMES


@dataclass(frozen=True)
class RuntimeInstallSpec:
    requirements: tuple[str, ...]
    python_version: str | None = None


def main() -> int:
    args = _parse_args()
    workspace = Path(__file__).resolve().parents[2]
    manifest = _runtime_manifest(workspace / "pyproject.toml")
    runtime_root = (
        Path(args.environment_root).expanduser().resolve()
        if args.environment_root
        else workspace / "processing_runtimes"
    )

    for stage, spec in manifest.items():
        project_root = runtime_root / RUNTIMES[stage].project_name
        environment = project_root / ".venv"
        project_root.mkdir(parents=True, exist_ok=True)
        _copy_runtime_support_files(workspace, stage, project_root)
        python = _ensure_environment(environment, spec.python_version)
        ready_marker = environment / ".doppler_manager_ready"
        ready_marker.unlink(missing_ok=True)
        _run_uv("pip", "install", "--python", str(python), *spec.requirements)
        ready_marker.write_text("ready\n", encoding="utf-8")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize isolated processing runtimes."
    )
    parser.add_argument(
        "--environment-root",
        help="Root directory containing the isolated runtime projects.",
    )
    return parser.parse_args()


def _runtime_manifest(path: Path) -> dict[str, RuntimeInstallSpec]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    raw_manifest = (
        payload.get("tool", {})
        .get("doppler_manager", {})
        .get("processing_runtimes", {})
    )
    if not isinstance(raw_manifest, dict):
        raise ValueError("Missing [tool.doppler_manager.processing_runtimes] manifest.")

    raw_python_versions = raw_manifest.get("python", {})
    if not isinstance(raw_python_versions, dict):
        raise ValueError(
            "Runtime Python versions must be a table under "
            "[tool.doppler_manager.processing_runtimes.python]."
        )

    manifest: dict[str, RuntimeInstallSpec] = {}
    for stage, runtime in RUNTIMES.items():
        runtime_name = runtime.project_name
        requirements = raw_manifest.get(stage)
        if not isinstance(requirements, list) or not all(
            isinstance(requirement, str) and requirement.strip()
            for requirement in requirements
        ):
            raise ValueError(
                f"Runtime manifest entry '{stage}' ({runtime_name}) is invalid."
            )
        python_version = raw_python_versions.get(stage)
        if python_version is not None and (
            not isinstance(python_version, str) or not python_version.strip()
        ):
            raise ValueError(
                f"Runtime Python version '{stage}' ({runtime_name}) is invalid."
            )
        manifest[stage] = RuntimeInstallSpec(
            requirements=tuple(requirements),
            python_version=python_version.strip() if python_version else None,
        )
    return manifest


def _python_path(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _ensure_environment(environment: Path, python_version: str | None) -> Path:
    python = _python_path(environment)
    if (
        python_version
        and python.is_file()
        and _python_version(python) != python_version
    ):
        _run_uv("venv", "--clear", "--python", python_version, str(environment))
    elif not python.is_file():
        arguments = ["venv"]
        if environment.exists():
            arguments.append("--clear")
        if python_version:
            arguments.extend(("--python", python_version))
        arguments.append(str(environment))
        _run_uv(*arguments)
    return python


def _python_version(python: Path) -> str | None:
    try:
        completed = subprocess.run(
            (
                str(python),
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    version = completed.stdout.strip()
    return version or None


def _copy_runtime_support_files(workspace: Path, stage: str, target: Path) -> None:
    if stage != "ef":
        return
    source = workspace / "processing_runtimes" / "eyeflow" / "runtime_limits.py"
    destination = target / source.name
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def _run_uv(*args: str) -> None:
    subprocess.run(("uv", *args), check=True)
