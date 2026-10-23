import hashlib
import json
from pathlib import Path

import pytest

from doppler_manager.tooling.dependencies import lock


def bundle(directory: Path, content: str) -> dict:
    project = directory / "apps/manager"
    project.mkdir(parents=True)
    artifact = project / "uv.lock"
    artifact.write_text(content)
    plan = {
        "schema": 1, "input_hash": lock.digest({"inputs": "unchanged"}),
        "lock_hashes": {"apps/manager/uv.lock": hashlib.sha256(artifact.read_bytes()).hexdigest()},
    }
    plan["id"] = lock.digest(plan)[:24]
    (directory / lock.LOCK_NAME).write_text(json.dumps(plan))
    return plan


def test_snapshot_remains_consistent_across_refresh(monkeypatch, tmp_path):
    monkeypatch.setattr(lock, "manifest", lambda _workspace: {"inputs": "unchanged"})
    destination, replacement = tmp_path / "selected", tmp_path / "replacement"
    original = bundle(destination, "old artifact")
    updated = bundle(replacement, "new artifact")
    with lock.snapshot_plan(destination / lock.LOCK_NAME, tmp_path) as snapshot:
        lock.publish_bundle(replacement, destination)
        assert lock.load_plan(snapshot, tmp_path)["id"] == original["id"]
        assert (snapshot.parent / "apps/manager/uv.lock").read_text() == "old artifact"
        assert lock.load_plan(destination / lock.LOCK_NAME)["id"] == updated["id"]


def test_failed_publication_restores_previous_bundle(monkeypatch, tmp_path):
    destination, replacement = tmp_path / "selected", tmp_path / "replacement"
    original = bundle(destination, "old artifact")
    bundle(replacement, "new artifact")
    rename = Path.rename

    def fail_on_publication(self, target):
        if ".stage-" in self.name:
            raise OSError("simulated publication failure")
        return rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_on_publication)
    with pytest.raises(OSError, match="publication failure"):
        lock.publish_bundle(replacement, destination)
    assert lock.load_plan(destination / lock.LOCK_NAME)["id"] == original["id"]


def test_concurrent_bundle_access_is_rejected(tmp_path):
    directory = tmp_path / "selected"
    bundle(directory, "artifact")
    with lock.bundle_access(directory):
        with pytest.raises((RuntimeError, BlockingIOError)):
            lock.load_plan(directory / lock.LOCK_NAME)


def test_committed_bundle_is_self_consistent():
    directory = Path(__file__).resolve().parents[2] / "dependencies/windows-x86_64"
    plan = lock.load_plan(directory / lock.LOCK_NAME)
    assert set(plan["projects"]) == {"manager", "holodoppler", "dopplerview", "eyeflow", "angioeye"}
    assert all(path == f"apps/{app}" for app, path in plan["projects"].items())
