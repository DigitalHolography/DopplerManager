import json
import shutil
import sys
from pathlib import Path

import pytest

from doppler_manager.runtime import bootstrap
from doppler_manager.tooling.validation import startup, relocation


def test_validation_outputs_do_not_modify_the_runtime(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    shutil.copy2(bootstrap.__file__, runtime / "bootstrap.py")
    (runtime / "runtime.json").write_text(json.dumps({
        "apps": {"probe": {"python": sys.executable, "paths": []}}
    }))
    monkeypatch.setattr(startup, "IMPORTS", {"probe": "import sys"})
    before = {path.name: path.read_bytes() for path in runtime.iterdir()}
    output = tmp_path / "evidence"
    results = startup.validate(runtime, output=output)
    assert results[0]["returncode"] == 0
    assert (output / "validation.json").is_file()
    assert (output / "appdata").is_dir()
    assert {path.name: path.read_bytes() for path in runtime.iterdir()} == before


def test_relocation_failure_restores_the_disposable_directory(monkeypatch, tmp_path):
    runtime = tmp_path / "disposable"
    runtime.mkdir()
    (runtime / "marker").write_text("unchanged")

    def fail(root, **kwargs):
        assert root != runtime and root.parent == runtime.parent
        raise RuntimeError("startup failed")

    monkeypatch.setattr(relocation, "validate", fail)
    with pytest.raises(RuntimeError, match="startup failed"):
        relocation.validate_relocated(runtime, output=tmp_path / "evidence")
    assert (runtime / "marker").read_text() == "unchanged"


def test_validation_rejects_output_inside_runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    with pytest.raises(ValueError, match="outside"):
        startup.validate(runtime, output=runtime / "evidence")
    with pytest.raises(ValueError, match="outside"):
        relocation.validate_relocated(runtime, output=runtime / "evidence")
    assert list(runtime.iterdir()) == []
