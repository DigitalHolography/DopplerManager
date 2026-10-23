import sys
from pathlib import Path

from doppler_manager.tooling.dependencies import resolver
from doppler_manager.tooling.dependencies.lock import LOCK_NAME, load_plan


def test_refresh_has_stable_selected_paths_and_leaves_candidates_in_cache(monkeypatch, tmp_path):
    config = {"apps": {"manager": {"requirements": ["common>=1"], "requires_python": ">=3.13"}},
              "candidates": ["3.13"]}
    monkeypatch.setattr(resolver, "manifest", lambda _workspace: config)
    monkeypatch.setattr(resolver.subprocess, "check_output", lambda *_args, **_kwargs: "3.13.14")
    calls = []

    def fake_uv(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("python", "find"):
            return sys.executable
        if args[0] == "lock":
            project = Path(args[args.index("--project") + 1])
            (project / "uv.lock").write_text('''
[[package]]
name = "root"
version = "0.0.0"
source = {virtual = "."}
dependencies = [{name = "common"}]
[[package]]
name = "common"
version = "1.0"
source = {registry = "https://example.org"}
wheels = [{url = "https://example.org/common-1.0-py3-none-any.whl", hash = "sha256:abc"}]
''')
        return ""

    monkeypatch.setattr(resolver, "run_uv", fake_uv)
    output = tmp_path / "dependencies/test-platform"
    first = resolver.create_plan(tmp_path, output)
    second = resolver.create_plan(tmp_path, output, refresh=True)
    assert first["id"] == second["id"]
    assert first["projects"] == {"manager": "apps/manager"}
    assert set(path.name for path in output.iterdir()) == {"apps", LOCK_NAME}
    assert len(list((tmp_path / ".cache/doppler-manager/resolve").iterdir())) == 2
    assert load_plan(output / LOCK_NAME)["id"] == first["id"]
    assert all(call[0] in {"python", "lock"} for call in calls)
