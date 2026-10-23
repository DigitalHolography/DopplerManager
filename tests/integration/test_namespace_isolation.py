import json
import subprocess
import sys
from pathlib import Path

import pytest

from doppler_manager.runtime.manifest import invocation


def test_bootstrap_isolates_namespaces_and_survives_relocation(tmp_path):
    import shutil
    import doppler_manager.runtime.bootstrap as bootstrap
    root = tmp_path / "generation"
    root.mkdir()
    shutil.copy2(bootstrap.__file__, root / "bootstrap.py")
    apps = {}
    for name in ("eyeflow", "angioeye"):
        package = root / name
        package.mkdir()
        (package / "launcher.py").write_text(f"NAME = {name!r}")
        apps[name] = {"python": sys.executable, "paths": [name]}
    (root / "runtime.json").write_text(json.dumps({"apps": apps}))
    moved = root.with_name("moved")
    root.rename(moved)
    for app in apps:
        command = invocation(moved, app, ("-c", "import launcher; print(launcher.NAME)"))
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        assert result.stdout.strip() == app


def test_bootstrap_prefers_eyeflows_packaged_runtime_limits(tmp_path):
    import shutil
    from doppler_manager.runtime import bootstrap

    shutil.copy2(bootstrap.__file__, tmp_path / "bootstrap.py")
    package = tmp_path / "packages/eyeflow"
    package.mkdir(parents=True)
    (package / "runtime_limits.py").write_text("ORIGIN = 'eyeflow-wheel'")
    legacy_support = tmp_path / "support/eyeflow"
    legacy_support.mkdir(parents=True)
    (legacy_support / "runtime_limits.py").write_text("raise RuntimeError('obsolete shim loaded')")
    (tmp_path / "runtime.json").write_text(json.dumps({
        "apps": {"eyeflow": {"python": sys.executable, "paths": ["packages/eyeflow"]}}
    }))
    result = subprocess.run(invocation(tmp_path, "eyeflow", (
        "-c", "import runtime_limits; print(runtime_limits.ORIGIN)",
    )), capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "eyeflow-wheel"


