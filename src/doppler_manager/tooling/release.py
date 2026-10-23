"""Generate a PyInstaller specification and release payload from a locked graph."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from doppler_manager.runtime.manifest import invocation, selected_generation
from .paths import project_root
from .validation.startup import validate
from .validation.relocation import validate_relocated


def stage_runtimes(generation: Path, output: Path) -> Path:
    """Keep frozen paths short enough for Windows installer file operations."""
    data = json.loads((generation / "runtime.json").read_text(encoding="utf-8"))
    plan = json.loads((generation / "dependency-plan.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    payload = output / "runtime-payload"
    # Build outputs must be new directories; never delete a live runtime.
    payload.mkdir()
    apps = {app: profile for app, profile in data["apps"].items() if app != "manager"}
    paths = sorted({path for profile in apps.values() for path in profile["paths"]})
    compact_paths = {path: f"p/{index:x}" for index, path in enumerate(paths)}
    apps = {
        app: {**profile, "paths": [compact_paths[path] for path in profile["paths"]]}
        for app, profile in apps.items()
    }
    bases = {Path(profile["python"]).parts[1] for profile in apps.values()}
    for version in bases:
        shutil.copytree(generation / "python" / version, payload / "python" / version)
    for relative in paths:
        shutil.copytree(generation / relative, payload / compact_paths[relative])
    shutil.copy2(generation / "bootstrap.py", payload / "bootstrap.py")
    shutil.copy2(generation / "dependency-plan.json", payload / "dependency-plan.json")
    if (generation / "installed-dependencies.json").is_file():
        shutil.copy2(generation / "installed-dependencies.json", payload / "installed-dependencies.json")
    (payload / "runtime.json").write_text(json.dumps({**data, "apps": apps}, indent=2), encoding="utf-8")
    validate(payload, output=output / "validation" / "payload")
    (payload / "ready.json").write_text(json.dumps({"plan_id": plan["id"]}), encoding="utf-8")
    # Frozen runtime lookup uses the same generation manifest as development.
    container = output / "processing_runtimes"
    container.mkdir()
    # The installed application has one immutable generation. Its identity stays
    # in the manifests; repeating its hash in every pathname wastes path budget.
    destination = container / "generations" / "0"
    destination.parent.mkdir()
    payload.rename(destination)
    (container / "current.json").write_text(json.dumps({"generation": "generations/0"}), encoding="utf-8")
    return container


def prepare(workspace: Path, runtime_root: Path, output: Path, defaults: Path) -> tuple[Path, Path]:
    generation = selected_generation(runtime_root)
    if generation is None:
        raise RuntimeError("Build runtimes have not been synchronized")
    data = json.loads((generation / "runtime.json").read_text(encoding="utf-8"))
    plan = json.loads((generation / "dependency-plan.json").read_text(encoding="utf-8"))
    container = stage_runtimes(generation, output)
    manager_paths = [str(generation / path) for path in data["apps"]["manager"]["paths"]]
    source = workspace / "src"
    spec = output / "DopplerManager.spec"
    spec.write_text(
        "# Generated from dependency plan " + plan["id"] + "\n"
        "from PyInstaller.utils.hooks import collect_all, collect_data_files\n"
        "datas, binaries, hiddenimports = collect_all('streamlit')\n"
        "datas += collect_data_files('imageio_ffmpeg')\n"
        f"datas += [({str(defaults)!r}, 'processing_defaults'), "
        f"({str(source / 'doppler_manager/processing/runtime_bridge.py')!r}, 'doppler_manager/processing')]\n"
        f"a = Analysis([{str(source / 'doppler_manager/launcher.py')!r}], "
        f"pathex={[str(source), *manager_paths]!r}, binaries=binaries, datas=datas, "
        # Uvicorn's optional httptools import can become a namespace containing
        # only extension modules in a frozen build. Use its required h11 backend.
        "excludes=['doppler_manager.tooling', 'httptools'], hiddenimports=hiddenimports + ['streamlit.web.cli', 'watchdog.observers.winapi', "
        "'doppler_manager.app', 'doppler_manager.processing.runtime_bridge'])\n"
        "pyz = PYZ(a.pure)\n"
        "exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DopplerManager', "
        f"console=False, icon={str(workspace / 'packaging/DopplerManager.ico')!r})\n"
        # External runtimes bypass both Analysis and COLLECT. They are copied
        # verbatim after freezing so DLLs never enter the manager's binary graph.
        f"# External runtime payload: {str(container)!r}\n"
        "coll = COLLECT(exe, a.binaries, a.datas, name='DopplerManager')\n",
        encoding="utf-8",
    )
    return spec, generation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--defaults", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    workspace = project_root()
    spec, generation = prepare(workspace, args.runtime_root.resolve(), args.output.resolve(), args.defaults.resolve())
    command = invocation(generation, "manager", ("-m", "PyInstaller", "--noconfirm", "--clean",
                         "--distpath", str(args.dist.resolve()), "--workpath", str(args.work.resolve()), str(spec)))
    subprocess.run(command, check=True)
    # Move the entire frozen bundle before checking its dispatchers.
    built = args.dist.resolve() / "DopplerManager"
    shutil.copytree(args.output.resolve() / "processing_runtimes", built / "_internal/processing_runtimes")
    validate_relocated(built, output=args.output.resolve() / "validation" / "frozen", frozen=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
