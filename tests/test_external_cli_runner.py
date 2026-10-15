import json
from pathlib import Path

import pytest

import doppler_manager._external_cli_runner as external_cli_runner


@pytest.mark.parametrize("git_cache", ["git-v0", "git-v1"])
def test_load_tool_cli_prefers_uv_checkout_over_colliding_installed_cli(
    tmp_path: Path,
    monkeypatch,
    git_cache: str,
) -> None:
    checkout = tmp_path / "uv-cache" / git_cache / "checkouts" / "repo" / "abcdef0"
    checkout_src = checkout / "src"
    checkout_src.mkdir(parents=True)
    (checkout / "pyproject.toml").write_text(
        '[project]\nname = "EyeFlow"\n',
        encoding="utf-8",
    )
    (checkout_src / "cli.py").write_text(
        '"""Run EyeFlow pipelines."""\n'
        "def main(argv=None):\n"
        "    return 37\n",
        encoding="utf-8",
    )

    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "eye_flow.py").write_text("", encoding="utf-8")
    (installed / "cli.py").write_text(
        '"""Run AngioEye pipelines."""\n'
        "def main(argv=None):\n"
        "    return 1\n",
        encoding="utf-8",
    )

    class FakeDistribution:
        def read_text(self, name: str) -> str | None:
            if name != "direct_url.json":
                return None
            return json.dumps(
                {
                    "url": "https://github.com/DigitalHolography/EyeFlowPython.git",
                    "vcs_info": {"vcs": "git", "commit_id": "abcdef0123456789"},
                }
            )

    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    monkeypatch.syspath_prepend(str(installed))
    monkeypatch.setattr(
        external_cli_runner.metadata,
        "distribution",
        lambda _name: FakeDistribution(),
    )

    module = external_cli_runner._load_tool_cli(external_cli_runner.CLI_TOOLS["eyeflow"])

    assert module.main([]) == 37
