"""Read installed runtime generations without importing build tooling."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def python_executable(root: Path) -> Path:
    return root / ("python.exe" if os.name == "nt" else "bin/python3")


def invocation(root: Path, app: str, args: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    data = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
    python = root / data["apps"][app]["python"]
    # -I ignores PYTHONUNBUFFERED/PYTHONIOENCODING, so configure live UTF-8
    # processing output with interpreter flags rather than environment variables.
    return (str(python), "-I", "-S", "-u", "-X", "utf8", str(root / "bootstrap.py"), app, *args)


def selected_generation(root: Path) -> Path | None:
    pointer = root / "current.json"
    if not pointer.is_file():
        return None
    relative = json.loads(pointer.read_text(encoding="utf-8"))["generation"]
    generation = (root / relative).resolve()
    if not generation.is_relative_to(root.resolve() / "generations"):
        raise RuntimeError(f"Invalid runtime generation: {relative}")
    if not (generation / "ready.json").is_file():
        raise RuntimeError(f"Incomplete runtime generation: {generation}")
    return generation

def active_generation() -> Path | None:
    configured = os.getenv("DM_PROCESSING_RUNTIME_ROOT", "").strip()
    if configured:
        return selected_generation(Path(configured).expanduser())
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            generation = selected_generation(Path(bundle) / "processing_runtimes")
            if generation is not None:
                return generation
        return selected_generation(Path(sys.executable).resolve().parent / "processing_runtimes")
    return selected_generation(Path(__file__).resolve().parents[3] / "processing_runtimes")
