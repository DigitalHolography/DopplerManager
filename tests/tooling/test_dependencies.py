import json
import subprocess
import sys
from pathlib import Path

import pytest

from doppler_manager.tooling.dependencies.graph import artifact, graph_from_locks
from doppler_manager.tooling.dependencies.resolver import choose_versions
from doppler_manager.tooling.dependencies.manifest import pin_requirement
from doppler_manager.tooling.dependencies.lock import digest, load_plan


def test_selection_minimizes_versions_instead_of_greedy_assignment():
    compatible = {"manager": ["3.13", "3.14"], "dv": ["3.12", "3.14"], "hd": ["3.12", "3.14"]}
    assert set(choose_versions(compatible, ["3.13", "3.12", "3.14"]).values()) == {"3.14"}
    compatible["hd"] = ["3.12"]
    assert len(set(choose_versions(compatible, ["3.13", "3.12", "3.14"]).values())) == 2
    with pytest.raises(RuntimeError, match="No supported Python"):
        choose_versions({"dv": []}, ["3.13"])


def test_graph_shares_exact_artifacts_and_keeps_conflicting_versions(tmp_path):
    projects = {}
    for app, version in (("manager", "1.0"), ("dopplerview", "2.0")):
        project = tmp_path / app
        project.mkdir()
        project.joinpath("uv.lock").write_text('''
[[package]]
name = "root"
version = "0.0.0"
source = { virtual = "." }
dependencies = [{ name = "numeric" }, { name = "common" }]
[[package]]
name = "numeric"
version = "''' + version + '''"
source = { registry = "https://example.org" }
dependencies = [{ name = "common" }]
wheels = [{ url = "https://example.org/numeric-''' + version + '''-py3-none-any.whl", hash = "sha256:abc" }]
[[package]]
name = "common"
version = "1.0"
source = { registry = "https://example.org" }
wheels = [{ url = "https://example.org/common-1.0-py3-none-any.whl", hash = "sha256:def" }]
''', encoding="utf-8")
        projects[app] = project
    plan = graph_from_locks({k: "3.13.14" for k in projects}, projects,
                            {"apps": {k: {"requirements": []} for k in projects}})
    assert len(plan["nodes"]) == 3
    shared = [n for n in plan["nodes"].values() if len(n["consumers"]) == 2]
    assert [n["name"] for n in shared] == ["common"]
    assert len(plan["apps"]["manager"]["edges"]) == 1
    assert plan["apps"]["manager"]["nodes"] != plan["apps"]["dopplerview"]["nodes"]


def test_git_artifact_requires_exact_commit():
    package = {"name": "app", "source": {"git": "https://example.org/app?rev=main#" + "a" * 40}}
    assert artifact(package, "3.13.14")["git"] == "git+https://example.org/app@" + "a" * 40
    package["source"]["git"] = "https://example.org/app#main"
    with pytest.raises(RuntimeError, match="Unpinned"):
        artifact(package, "3.13.14")


def test_git_pinning_does_not_confuse_branch_with_remote_tracking_reference(monkeypatch):
    from doppler_manager.tooling.dependencies import manifest as planner
    monkeypatch.setattr(planner.subprocess, "run", lambda *_args, **_kw: subprocess.CompletedProcess(
        [], 0, stdout="a" * 40 + "\trefs/heads/main\n" + "b" * 40 + "\trefs/remotes/origin/main\n"
    ))
    assert pin_requirement("app @ git+https://example.org/app.git@main").endswith("@" + "a" * 40)


def test_plan_rejects_changed_locks(tmp_path):
    lock = tmp_path / "uv.lock"
    lock.write_text("original")
    import hashlib
    plan = {"schema": 1, "lock_hashes": {"uv.lock": hashlib.sha256(lock.read_bytes()).hexdigest()}}
    plan["id"] = digest(plan)[:24]
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    load_plan(path)
    lock.write_text("changed")
    with pytest.raises(RuntimeError, match="lock was changed"):
        load_plan(path)


