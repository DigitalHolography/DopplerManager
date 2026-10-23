"""Verify, snapshot and transactionally publish a stable dependency lock bundle."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from .manifest import manifest

SCHEMA = 1
LOCK_NAME = "runtime-lock.json"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@contextmanager
def bundle_access(directory: Path):
    """Fail rather than read across a simultaneous controlled replacement."""
    directory.parent.mkdir(parents=True, exist_ok=True)
    lock = directory.parent / f".{directory.name}.lock"
    with lock.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(f"Dependency bundle is in use: {directory}") from exc
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _bundle_file(directory: Path, relative: str) -> Path:
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise RuntimeError(f"Lock path escapes dependency bundle: {relative}")
    return path


def _read_plan(path: Path, workspace: Path | None = None) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan["schema"] != SCHEMA:
        raise RuntimeError("Unsupported dependency plan schema")
    if plan["id"] != digest({k: v for k, v in plan.items() if k != "id"})[:24]:
        raise RuntimeError("Dependency plan content hash does not match")
    if workspace and plan["input_hash"] != digest(manifest(workspace)):
        raise RuntimeError("Dependency inputs changed; run `uv run sync --refresh --plan-only`.")
    for relative, expected in plan.get("lock_hashes", {}).items():
        if hashlib.sha256(_bundle_file(path.parent, relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Generated lock was changed: {relative}")
    return plan


def load_plan(path: Path, workspace: Path | None = None) -> dict:
    with bundle_access(path.parent):
        return _read_plan(path, workspace)


@contextmanager
def snapshot_plan(path: Path, workspace: Path):
    """Keep a verified, private copy while downloads/installations are running."""
    with tempfile.TemporaryDirectory(prefix="doppler-lock-") as temporary:
        directory = Path(temporary)
        with bundle_access(path.parent):
            plan = _read_plan(path, workspace)
            for relative in plan["lock_hashes"]:
                target = _bundle_file(directory, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_bundle_file(path.parent, relative), target)
            snapshot = directory / LOCK_NAME
            shutil.copy2(path, snapshot)
            _read_plan(snapshot, workspace)
        yield snapshot


def publish_bundle(staged: Path, destination: Path) -> dict:
    """Replace one whole bundle under the same lock used by readers."""
    plan = _read_plan(staged / LOCK_NAME)
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    prepared = destination.with_name(f".{destination.name}.stage-{uuid.uuid4().hex}")
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    shutil.copytree(staged, prepared)
    try:
        _read_plan(prepared / LOCK_NAME)
        with bundle_access(destination):
            if destination.exists():
                destination.rename(backup)
            try:
                prepared.rename(destination)
            except BaseException:
                if backup.exists():
                    backup.rename(destination)
                raise
        if backup.exists():
            assert backup.parent == destination.parent and backup != destination
            shutil.rmtree(backup)
    finally:
        if prepared.exists():
            assert prepared.parent == destination.parent and prepared != destination
            shutil.rmtree(prepared)
    return plan
