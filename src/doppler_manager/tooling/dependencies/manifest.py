"""Declared app requirements, generated uv projects and source pinning."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import Requirement
from doppler_manager.runtime.apps import RUNTIMES

def manifest(workspace: Path) -> dict:
    data = tomllib.loads((workspace / "pyproject.toml").read_text(encoding="utf-8"))
    tool = data["tool"]["doppler_manager"]
    apps = {
        "manager": {
            "requirements": data["project"]["dependencies"] + data["dependency-groups"]["release"],
            "requires_python": data["project"]["requires-python"],
        }
    }
    specs = runtime_manifest(workspace / "pyproject.toml")
    for stage, runtime in RUNTIMES.items():
        spec = specs[stage]
        pin = spec.python_version
        apps[runtime.project_name] = {
            "stage": stage, "requirements": list(spec.requirements),
            "requires_python": f"=={pin}.*" if pin else ">=3.10",
        }
    return {"apps": apps, "candidates": tool["dependency_plan"]["python_candidates"],
            "platform": platform.system(), "machine": platform.machine()}


def write_project(path: Path, app: str, requirements: list[str], version: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(
        '[project]\nname = ' + json.dumps(f"dm-plan-{app}") + '\nversion = "0.0.0"\n'
        + 'requires-python = ' + json.dumps(f"=={version}") + '\ndependencies = '
        + json.dumps(requirements, indent=2) + '\n[tool.uv]\npackage = false\n'
        + 'environments = [' + json.dumps(f"sys_platform == '{sys.platform}'") + ']\n',
        encoding="utf-8",
        newline="\n",
    )

def pin_requirement(text: str) -> str:
    req = Requirement(text)
    if not req.url or not req.url.startswith("git+"):
        return text
    url, _, fragment = req.url[4:].partition("#")
    repo, separator, ref = url.rpartition("@")
    if not separator:
        repo, ref = url, "HEAD"
    if len(ref) != 40 or any(c not in "0123456789abcdefABCDEF" for c in ref):
        result = subprocess.run(["git", "ls-remote", "--exit-code", repo, ref,
                                 f"refs/heads/{ref}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"],
                                capture_output=True, text=True, check=True,
                                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        references = {line.split()[1]: line.split()[0] for line in result.stdout.splitlines()}
        resolved = next((references[name] for name in (
            f"refs/heads/{ref}", f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", ref
        ) if name in references), None)
        if resolved is None:
            raise RuntimeError(f"Cannot pin Git requirement: {text}")
        ref = resolved
    extras = "[" + ",".join(sorted(req.extras)) + "]" if req.extras else ""
    marker = f" ; {req.marker}" if req.marker else ""
    return f"{req.name}{extras} @ git+{repo}@{ref}" + (f"#{fragment}" if fragment else "") + marker

@dataclass(frozen=True)
class RuntimeInstallSpec:
    requirements: tuple[str, ...]
    python_version: str | None = None

def runtime_manifest(path: Path) -> dict[str, RuntimeInstallSpec]:
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
