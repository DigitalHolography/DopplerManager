import json
import subprocess
import sys
from pathlib import Path

import pytest

from doppler_manager.runtime.manifest import selected_generation


@pytest.mark.parametrize("validation_fails", [False, True])
def test_sync_publishes_only_validated_generations_and_preserves_previous_runtime(monkeypatch, tmp_path, validation_fails):
    import doppler_manager.tooling.environments as store
    root = tmp_path / "runtimes"
    previous = root / "generations/old"
    previous.mkdir(parents=True)
    (previous / "ready.json").write_text('{"plan_id": "old"}')
    (root / "current.json").write_text('{"generation": "generations/old"}')
    legacy = root / "dopplerview/.venv"
    legacy.mkdir(parents=True)
    (legacy / "untouched").write_text("running")
    plan = {"id": "new", "python_versions": ["3.13.14"], "nodes": {},
            "apps": {"manager": {"python": "3.13.14", "nodes": [], "requirements": []}}}
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    monkeypatch.setattr(store, "load_plan", lambda *_args: plan)
    monkeypatch.setattr(store, "run_uv", lambda *_args, **_kw: sys.executable)
    monkeypatch.setattr(store.shutil, "copytree", lambda _source, target, **_kw: target.mkdir(parents=True))
    monkeypatch.setattr(store.subprocess, "check_output", lambda args, **_kw: (
        sys.base_prefix if "base_prefix" in args[-1] else "3.13.14"
    ))
    validations = []

    def validate(generation, **kwargs):
        validations.append(generation)
        assert selected_generation(root) == previous.resolve()
        if validation_fails:
            raise RuntimeError("bad runtime")

    from contextlib import contextmanager

    @contextmanager
    def snapshot(*args):
        yield plan_path

    monkeypatch.setattr(store, "snapshot_plan", snapshot)
    monkeypatch.setattr(store, "validate", validate)
    monkeypatch.setattr(store, "validate_relocated", validate)
    if validation_fails:
        with pytest.raises(RuntimeError, match="bad runtime"):
            store.materialize(plan_path, root, tmp_path)
        assert selected_generation(root) == previous.resolve()
    else:
        new = store.materialize(plan_path, root, tmp_path)
        assert selected_generation(root) == new.resolve()
        assert len(validations) == 2
        assert not (new / "support").exists()
    assert (previous / "ready.json").is_file()
    assert (legacy / "untouched").read_text() == "running"


