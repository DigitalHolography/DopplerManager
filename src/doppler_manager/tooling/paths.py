"""Locations owned by development and build tooling."""
from pathlib import Path
import platform
import sys


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def cache_root(workspace: Path) -> Path:
    return workspace / ".cache" / "doppler-manager"


def default_lock_dir(workspace: Path) -> Path:
    machine = platform.machine().lower()
    architecture = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform)
    return workspace / "dependencies" / f"{system}-{architecture}"
