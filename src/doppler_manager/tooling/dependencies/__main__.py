"""Inspect or refresh the shared dependency lock bundle."""
import argparse
import json
from pathlib import Path

from .resolver import create_plan
from ..paths import default_lock_dir, project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    workspace = project_root()
    plan = create_plan(workspace, (args.output or default_lock_dir(workspace)).resolve(), refresh=args.refresh)
    print(json.dumps({"plan": plan["id"], "python_versions": plan["python_versions"],
                      "assignments": {k: v["python"] for k, v in plan["apps"].items()},
                      "shared_packages": sum(len(n["consumers"]) > 1 for n in plan["nodes"].values())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
