"""Validate runtime imports/CLI startup, optionally using a relocated copy."""
import argparse
import shutil
from pathlib import Path

from doppler_manager.runtime.manifest import selected_generation
from .relocation import validate_relocated
from .startup import validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--relocate", action="store_true", help="Test a disposable copy")
    parser.add_argument("--frozen", action="store_true", help="Runtime root is a frozen app directory")
    args = parser.parse_args()
    root, output = args.runtime_root.resolve(), args.output.resolve()
    if output.is_relative_to(root):
        parser.error("--output must be outside the runtime directory")
    if args.relocate:
        # Diagnostics must never rename a live runtime.
        copy = output / "runtime-copy"
        shutil.copytree(root, copy)
        results = validate_relocated(copy, output=output / "results", frozen=args.frozen)
    else:
        container = root / "_internal/processing_runtimes" if args.frozen else root
        generation = root if (root / "runtime.json").is_file() else selected_generation(container)
        if generation is None:
            parser.error("No validated runtime generation found")
        results = validate(generation, output=output, frozen_exe=root / "DopplerManager.exe" if args.frozen else None)
    print(f"{len(results)} startup checks passed; evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
