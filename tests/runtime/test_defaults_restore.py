import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from doppler_manager.runtime import defaults as release_defaults
from doppler_manager.runtime.apps import RUNTIMES


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    "site_packages", ["Lib/site-packages", "lib/python3.13/site-packages"]
)
@pytest.mark.parametrize("custom_root", [False, True])
@pytest.mark.parametrize("git_cache", ["git-v0", "git-v1"])
def test_sync_restores_defaults_when_package_versions_are_unchanged(
    tmp_path: Path, monkeypatch, site_packages: str, custom_root: bool, git_cache: str
) -> None:
    workspace = tmp_path / "workspace"
    runtime_root = (
        tmp_path / "release-runtimes"
        if custom_root
        else workspace / "processing_runtimes"
    )
    _write(
        workspace / "pyproject.toml",
        Path("pyproject.toml").read_text(encoding="utf-8"),
    )
    for runtime in RUNTIMES.values():
        (runtime_root / runtime.project_name / ".venv").mkdir(parents=True)
    cache = tmp_path / "uv-cache"
    expected: dict[Path, str] = {}
    for project, commit in (
        ("holodoppler", "a" * 40),
        ("EyeFlow", "b" * 40),
        ("AngioEye", "c" * 40),
    ):
        dist_info = (
            runtime_root / project.lower() / ".venv" / site_packages
            / f"{project}-1.0.dist-info"
        )
        _write(
            dist_info / "METADATA",
            f"Metadata-Version: 2.1\nName: {project}\nVersion: 1.0\n",
        )
        _write(
            dist_info / "direct_url.json",
            json.dumps({"vcs_info": {"commit_id": commit}}),
        )
        checkout = cache / git_cache / "checkouts" / project / commit[:7]
        _write(checkout / "pyproject.toml", f'[project]\nname = "{project}"\n')
        if project == "holodoppler":
            relative = Path("holodoppler/default_parameters_simple.yaml")
            source = checkout / "parameters" / relative.name
            content = "setting: original\n"
        else:
            relative = Path(project.lower()) / "default_settings.json"
            source = checkout / relative.name
            content = '{"setting": "original"}\n'
        _write(source, content)
        expected[relative] = content

    monkeypatch.setenv("UV_CACHE_DIR", str(cache))
    monkeypatch.setattr(
        release_defaults.metadata, "distribution",
        lambda name: pytest.fail(f"Unexpected manager distribution lookup: {name}"),
    )
    monkeypatch.chdir(tmp_path)

    release_defaults.sync_processing_defaults(workspace / "processing_defaults", environment_root=runtime_root)
    target = workspace / "processing_defaults"
    for relative, content in expected.items():
        assert (target / relative).read_text(encoding="utf-8") == content

    (target / "angioeye/default_settings.json").unlink()
    _write(target / "eyeflow/default_settings.json", "{}")
    (target / "holodoppler/default_parameters_simple.yaml").unlink()

    release_defaults.sync_processing_defaults(workspace / "processing_defaults", environment_root=runtime_root)
    for relative, content in expected.items():
        assert (target / relative).read_text(encoding="utf-8") == content
