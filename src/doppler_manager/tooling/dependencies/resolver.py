"""Use uv to resolve candidate interpreters, then publish only selected locks."""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from packaging.specifiers import SpecifierSet

from .graph import graph_from_locks
from .lock import LOCK_NAME, digest, load_plan, publish_bundle
from .manifest import manifest, pin_requirement, write_project
from ..paths import cache_root


def run_uv(*args: str, env: dict | None = None) -> str:
    result = subprocess.run(
        ["uv", *map(str, args)], env=env, capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def choose_versions(compatible: dict[str, list[str]], candidates: list[str]) -> dict[str, str]:
    for count in range(1, len(candidates) + 1):
        for versions in itertools.combinations(candidates, count):
            if all(any(v in allowed for v in versions) for allowed in compatible.values()):
                return {app: next(v for v in versions if v in allowed)
                        for app, allowed in compatible.items()}
    raise RuntimeError(f"No supported Python assignment: {compatible}")


def create_plan(workspace: Path, output: Path, *, refresh: bool = False) -> dict:
    target = output / LOCK_NAME
    if target.is_file() and not refresh:
        return load_plan(target, workspace)
    config = manifest(workspace)
    working = cache_root(workspace) / "resolve" / uuid.uuid4().hex
    working.mkdir(parents=True)
    env = {**os.environ, "UV_PYTHON_INSTALL_DIR": str(cache_root(workspace) / "python")}
    pinned = {app: [pin_requirement(req) for req in spec["requirements"]]
              for app, spec in config["apps"].items()}
    versions = []
    compatibility = {app: [] for app in config["apps"]}
    projects, failures = {}, {}
    for candidate in config["candidates"]:
        run_uv("python", "install", candidate, env=env)
        python = run_uv("python", "find", "--managed-python", candidate, env=env)
        version = subprocess.check_output([python, "-I", "-c", "import platform; print(platform.python_version())"], text=True).strip()
        versions.append(version)
        for app, spec in config["apps"].items():
            if version not in SpecifierSet(spec["requires_python"]):
                continue
            project = working / "candidates" / app / version
            write_project(project, app, pinned[app], version)
            try:
                run_uv("lock", "--project", project, "--python", python, env=env)
            except RuntimeError as exc:
                if "No solution found" not in str(exc):
                    raise
                failures[f"{app}/{version}"] = str(exc).replace(str(working), "<resolver-workspace>")
                continue
            compatibility[app].append(version)
            projects[app, version] = project
        if all(version in allowed for allowed in compatibility.values()):
            break
    assignments = choose_versions(compatibility, versions)
    staged = working / "selected"
    staged.mkdir()
    chosen = {}
    for app, version in assignments.items():
        path = staged / "apps" / app
        path.mkdir(parents=True)
        for filename in ("pyproject.toml", "uv.lock"):
            shutil.copy2(projects[app, version] / filename, path / filename)
        chosen[app] = path
    plan = graph_from_locks(assignments, chosen, config)
    plan.update(compatibility=compatibility, resolution_failures=failures, pinned_requirements=pinned)
    plan["projects"] = {app: path.relative_to(staged).as_posix() for app, path in chosen.items()}
    plan["lock_hashes"] = {
        (path / filename).relative_to(staged).as_posix(): hashlib.sha256((path / filename).read_bytes()).hexdigest()
        for path in chosen.values() for filename in ("pyproject.toml", "uv.lock")
    }
    plan["id"] = digest(plan)[:24]
    (staged / LOCK_NAME).write_text(json.dumps(plan, indent=2), encoding="utf-8", newline="\n")
    return publish_bundle(staged, output)
