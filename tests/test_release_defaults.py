from pathlib import Path

import doppler_manager.release_defaults as release_defaults


def _write(path: Path, text: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_sync_processing_defaults_copies_commit_checkout_files(tmp_path: Path, monkeypatch) -> None:
    commits = {
        "holodoppler": "05d0b7c822648283e7dd5809a7a71cee5730aebd",
        "EyeFlow": "2d42e4a03483d73bdb13a2b4cf71f7dac4042ab4",
        "AngioEye": "9442eb81ea3cf860de9b5b6f94d8248e36c82ba7",
    }
    projects = {"holodoppler": "holodoppler", "EyeFlow": "EyeFlow", "AngioEye": "AngioEye"}
    cache = tmp_path / "uv-cache"
    for distribution, commit in commits.items():
        root = cache / "git-v0" / "checkouts" / distribution / commit[:7]
        _write(root / "pyproject.toml", f'[project]\nname = "{projects[distribution]}"\n')
        if distribution == "holodoppler":
            for name in (
                "default_parameters_debug.json",
                "default_parameters_debug_angularsp.json",
                "default_parameters_debug_of_choroid.json",
                "default_parameters_simple.yaml",
            ):
                _write(root / "parameters" / name, f'{{"source": "{name}"}}')
        else:
            _write(root / "default_settings.json", f'{{"source": "{distribution}"}}')

    class FakeDistribution:
        def __init__(self, commit: str) -> None:
            self.commit = commit

        def read_text(self, name: str) -> str | None:
            if name != "direct_url.json":
                return None
            return '{"vcs_info": {"commit_id": "' + self.commit + '"}}'

    monkeypatch.setenv("UV_CACHE_DIR", str(cache))
    monkeypatch.setattr(
        release_defaults.metadata,
        "distribution",
        lambda name: FakeDistribution(commits[name]),
    )
    target = tmp_path / "processing_defaults"
    _write(target / "holodoppler" / "stale.json", '{"stale": true}')
    _write(target / "holodoppler" / "stale.yml", "stale: true")

    copied = release_defaults.sync_processing_defaults(target)

    assert len(copied) == 6
    assert not (target / "holodoppler" / "stale.json").exists()
    assert not (target / "holodoppler" / "stale.yml").exists()
    assert (target / "holodoppler" / "default_parameters_debug.json").read_text(encoding="utf-8") == '{"source": "default_parameters_debug.json"}'
    assert (target / "holodoppler" / "default_parameters_simple.yaml").is_file()
    assert (target / "eyeflow" / "default_settings.json").read_text(encoding="utf-8") == '{"source": "EyeFlow"}'
    assert (target / "angioeye" / "default_settings.json").read_text(encoding="utf-8") == '{"source": "AngioEye"}'
