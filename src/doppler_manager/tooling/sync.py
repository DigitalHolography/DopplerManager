from __future__ import annotations

import argparse
import json
from pathlib import Path

from doppler_manager.runtime.defaults import sync_processing_defaults
from .dependencies.lock import LOCK_NAME
from .paths import default_lock_dir, project_root


def main() -> int:
    args = _parse_args()
    workspace = project_root()
    from .dependencies.resolver import create_plan
    from .environments import materialize
    from doppler_manager.runtime.manifest import selected_generation

    plan_dir = (args.plan_dir or default_lock_dir(workspace)).resolve()
    if args.locked and not (plan_dir / LOCK_NAME).is_file():
        raise RuntimeError("No dependency plan; run `uv run sync --plan-only` first.")
    if args.locked and args.refresh:
        raise ValueError("--locked and --refresh cannot be combined")
    plan = create_plan(workspace, plan_dir, refresh=args.refresh)
    print(f"Dependency plan {plan['id']}: Python {', '.join(plan['python_versions'])}")
    if args.plan_only:
        return 0
    runtime_root = (
        Path(args.environment_root).expanduser().resolve()
        if args.environment_root
        else workspace / "processing_runtimes"
    )

    generation = selected_generation(runtime_root)
    if generation is None or json.loads((generation / "ready.json").read_text())["plan_id"] != plan["id"]:
        materialize(plan_dir / LOCK_NAME, runtime_root, workspace, output=args.validation_output)

    for path in sync_processing_defaults(
        args.defaults_output or workspace / "processing_defaults",
        environment_root=runtime_root,
    ):
        print(f"Synced {path}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize isolated processing runtimes and their default settings."
    )
    parser.add_argument(
        "--environment-root",
        help="Root directory containing the isolated runtime projects.",
    )
    parser.add_argument("--plan-dir", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--locked", action="store_true")
    parser.add_argument("--defaults-output", type=Path)
    parser.add_argument("--validation-output", type=Path)
    return parser.parse_args()

if __name__ == "__main__":
    raise SystemExit(main())
