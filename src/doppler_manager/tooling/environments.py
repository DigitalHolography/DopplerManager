"""Install and publish validated runtime generations from a locked snapshot."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from doppler_manager.runtime.manifest import python_executable, selected_generation
from .dependencies.graph import requirement
from .dependencies.lock import load_plan, snapshot_plan
from .dependencies.resolver import run_uv
from .paths import cache_root
from .validation.metadata import validate_metadata
from .validation.startup import validate
from .validation.relocation import validate_relocated

def materialize(plan_path: Path, destination: Path, workspace: Path, *, output: Path | None = None) -> Path:
    # Own a verified snapshot for the entire installation.
    with snapshot_plan(plan_path, workspace) as snapshot:
        return _materialize(snapshot, destination, workspace, output=output)


def _materialize(plan_path: Path, destination: Path, workspace: Path, *, output: Path | None) -> Path:
    plan = load_plan(plan_path, workspace)
    destination.mkdir(parents=True, exist_ok=True)
    generations = destination / "generations"
    generations.mkdir(exist_ok=True)
    # Never mutate a published generation, even if the same plan is requested twice.
    generation = generations / f"{plan['id']}-{uuid.uuid4().hex[:8]}"
    generation.mkdir()
    reports = output or workspace / "build" / "validation" / generation.name
    env = os.environ.copy()
    env["UV_PYTHON_INSTALL_DIR"] = str(cache_root(workspace) / "python")
    pythons = {}
    for version in plan["python_versions"]:
        run_uv("python", "install", version, env=env)
        source_python = Path(run_uv("python", "find", "--managed-python", version, env=env)).resolve()
        base = Path(subprocess.check_output([str(source_python), "-I", "-c", "import sys; print(sys.base_prefix)"], text=True).strip())
        target = generation / "python" / version
        shutil.copytree(base, target, symlinks=False)
        python = python_executable(target)
        actual = subprocess.check_output([str(python), "-I", "-c", "import platform; print(platform.python_version())"], text=True).strip()
        if actual != version:
            raise RuntimeError(f"Portable Python version mismatch: {version} != {actual}")
        pythons[version] = python
    for key, node in plan["nodes"].items():
        target = generation / "packages" / key
        python = pythons[next(plan["apps"][app]["python"] for app in node["consumers"])]
        print(f"Installing {node['name']} {node['version']} for {', '.join(node['consumers'])}", flush=True)
        run_uv("pip", "install", "--python", python, "--target", target,
               "--no-deps", requirement(node), env=env)
    apps = {}
    for app, profile in plan["apps"].items():
        apps[app] = {"python": pythons[profile["python"]].relative_to(generation).as_posix(),
                     "paths": [f"packages/{key}" for key in profile["nodes"]]}
    apps["manager"]["source"] = str(workspace / "src")
    bootstrap = Path(__file__).resolve().parents[1] / "runtime" / "bootstrap.py"
    shutil.copy2(bootstrap, generation / "bootstrap.py")
    (generation / "runtime.json").write_text(json.dumps({"schema": 1, "plan_id": plan["id"], "apps": apps}, indent=2), encoding="utf-8")
    shutil.copy2(plan_path, generation / "dependency-plan.json")
    validate_metadata(plan, generation, output=reports)
    validate(generation, output=reports / "startup")
    validate_relocated(generation, output=reports / "relocated")
    (generation / "ready.json").write_text(json.dumps({"plan_id": plan["id"]}), encoding="utf-8")
    temporary = destination / f"current-{uuid.uuid4().hex}.tmp"
    temporary.write_text(json.dumps({"generation": generation.relative_to(destination).as_posix()}), encoding="utf-8")
    temporary.replace(destination / "current.json")
    return generation
