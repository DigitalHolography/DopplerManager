"""Relocate a disposable build directory and restore it even on failure."""
from pathlib import Path
import uuid

from doppler_manager.runtime.manifest import selected_generation
from .startup import validate


def validate_relocated(root: Path, *, output: Path, frozen: bool = False) -> list[dict]:
    root = root.resolve()
    if output.resolve().is_relative_to(root):
        raise ValueError("Validation output must be outside the runtime directory")
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Expected a disposable build directory: {root}")
    moved = root.with_name(root.name + "-relocated-" + uuid.uuid4().hex[:8])
    if moved.parent != root.parent or moved.exists():
        raise ValueError(f"Unsafe relocation target: {moved}")
    root.rename(moved)
    try:
        if not frozen:
            return validate(moved, output=output)
        generation = selected_generation(moved / "_internal/processing_runtimes")
        if generation is None:
            raise RuntimeError("Frozen bundle is missing its runtime manifest")
        return validate(generation, output=output, frozen_exe=moved / "DopplerManager.exe")
    finally:
        moved.rename(root)
