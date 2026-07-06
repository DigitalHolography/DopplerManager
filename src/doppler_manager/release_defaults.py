from __future__ import annotations

import json
import shutil
from importlib import metadata
from pathlib import Path

from ._external_cli_runner import _project_name, _uv_cache_roots


def sync_processing_defaults(target_root: Path | None = None) -> list[Path]:
    target_root = Path.cwd() / "processing_defaults" if target_root is None else Path(target_root)
    copied = _copy_jsons(
        _app_root("holodoppler", "holodoppler") / "parameters",
        target_root / "holodoppler",
    )
    for distribution, project, target in (
        ("EyeFlow", "EyeFlow", target_root / "eyeflow" / "default_settings.json"),
        ("AngioEye", "AngioEye", target_root / "angioeye" / "default_settings.json"),
    ):
        copied.append(_copy_file(_app_root(distribution, project) / "default_settings.json", target))
    return copied


def _app_root(distribution: str, project: str) -> Path:
    direct_url = json.loads(metadata.distribution(distribution).read_text("direct_url.json") or "{}")
    commit = direct_url.get("vcs_info", {}).get("commit_id", "")[:7].lower()
    if not commit:
        raise RuntimeError(f"{distribution} was not installed from a pinned git commit.")
    for cache_root in _uv_cache_roots():
        checkout_root = cache_root / "git-v0" / "checkouts"
        if not checkout_root.is_dir():
            continue
        for pyproject in checkout_root.rglob("pyproject.toml"):
            has_commit = any(part.lower().startswith(commit) for part in pyproject.parts)
            if has_commit and _project_name(pyproject) == project.lower():
                return pyproject.parent
    raise FileNotFoundError(f"Could not find {distribution} checkout for commit {commit}.")


def _copy_jsons(source_dir: Path, target_dir: Path) -> list[Path]:
    files = sorted(source_dir.glob("*.json"))
    if len(files) < 4:
        raise FileNotFoundError(f"Expected HoloDoppler JSON defaults in {source_dir}.")
    target_dir.mkdir(parents=True, exist_ok=True)
    for stale in target_dir.glob("*.json"):
        stale.unlink()
    return [_copy_file(source, target_dir / source.name) for source in files]


def _copy_file(source: Path, target: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def main() -> None:
    for path in sync_processing_defaults():
        print(f"Synced {path}")


if __name__ == "__main__":
    main()
