"""Standalone entry point for an app's isolated view of shared packages.

Executed by a complete portable Python with -I -S; no manager imports required.
"""
from __future__ import annotations

import json
import os
import runpy
import site
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    app = sys.argv[1]
    manifest = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
    profile = manifest["apps"][app]
    os.environ["DM_RUNTIME_APP"] = app
    # Standard library remains available; user, cwd and global site-packages do not.
    for relative in profile["paths"]:
        site.addsitedir(str(root / relative))
    if app == "manager" and "source" in profile:
        sys.path.insert(0, profile["source"])
    args = sys.argv[2:]
    if args[0] == "-m":
        sys.argv = args[1:]
        runpy.run_module(args[1], run_name="__main__", alter_sys=True)
    elif args[0] == "-c":
        sys.argv = ["-c", *args[2:]]
        exec(compile(args[1], "<runtime-cli>", "exec"), {"__name__": "__main__"})
    else:
        sys.argv = args
        runpy.run_path(args[0], run_name="__main__")


if __name__ == "__main__":
    main()
