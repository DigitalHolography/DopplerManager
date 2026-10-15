import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import doppler_manager.processing.runtimes as runtimes
from doppler_manager.sync_processing import _runtime_manifest


def test_runtime_definitions_cover_each_processing_stage() -> None:
    assert {
        stage: runtime.project_name for stage, runtime in runtimes.RUNTIMES.items()
    } == {
        "hd": "holodoppler",
        "dv": "dopplerview",
        "ef": "eyeflow",
        "ae": "angioeye",
    }
    assert len({runtime.project_name for runtime in runtimes.RUNTIMES.values()}) == 4


def test_runtime_manifest_pins_holodoppler_compatibility() -> None:
    manifest = _runtime_manifest(Path("pyproject.toml"))

    assert manifest["hd"].python_version == "3.13"
    assert "cinereader>=1.4.3" in manifest["hd"].requirements
    assert "numba>=0.65.1,<0.67" in manifest["hd"].requirements
    assert manifest["dv"].python_version is None
    assert manifest["ef"].python_version is None
    assert manifest["ae"].python_version is None


def test_runtime_catalog_decodes_isolated_bridge_response(
    tmp_path: Path,
    monkeypatch,
) -> None:
    python = tmp_path / "python.exe"
    python.touch()
    project = tmp_path / "project"
    project.mkdir()
    response = {
        "ok": True,
        "available": [
            {
                "name": "waveform_shape_metrics",
                "description": "Waveform metrics",
                "dag_requires": [],
            }
        ],
        "missing": [
            {
                "name": "broken_pipeline",
                "description": "Import Error: dependency",
                "error_msg": "dependency",
            }
        ],
    }

    monkeypatch.setattr(runtimes, "runtime_python", lambda _stage: python)
    monkeypatch.setattr(runtimes, "runtime_project_dir", lambda _stage: project)

    def fake_run(command, **kwargs):
        assert command == (str(python), str(runtimes._bridge_path()), "pipelines")
        assert kwargs["cwd"] == project
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(response),
            stderr="",
        )

    monkeypatch.setattr(runtimes.subprocess, "run", fake_run)

    available, missing = runtimes.runtime_catalog("ae", "pipelines")

    assert available[0].name == "waveform_shape_metrics"
    assert missing[0].error_msg == "dependency"


def test_runtime_command_prefix_uses_configured_python(
    tmp_path: Path,
    monkeypatch,
) -> None:
    python = tmp_path / "eyeflow-python.exe"
    monkeypatch.setenv("DM_EYEFLOW_PYTHON", str(python))

    prefix = runtimes.runtime_command_prefix("ef")

    assert prefix[0] == str(python)
    assert prefix[1] == "-c"
    assert "from launcher import cli_main" in prefix[2]


def test_runtime_availability_requires_a_success_marker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    python = tmp_path / "python.exe"
    python.touch()
    marker = tmp_path / ".doppler_manager_ready"
    monkeypatch.setattr(runtimes, "runtime_python", lambda _stage: python)
    monkeypatch.setattr(runtimes, "runtime_ready_marker", lambda _stage: marker)

    assert not runtimes.runtime_available("hd")
    marker.touch()
    assert runtimes.runtime_available("hd")


def test_runtime_catalog_does_not_require_a_project_cwd(
    tmp_path: Path,
    monkeypatch,
) -> None:
    python = tmp_path / "python.exe"
    python.touch()
    missing_project = tmp_path / "missing-project"
    monkeypatch.setattr(runtimes, "runtime_python", lambda _stage: python)
    monkeypatch.setattr(
        runtimes,
        "runtime_project_dir",
        lambda _stage: missing_project,
    )

    def fake_run(command, **kwargs):
        assert kwargs["cwd"] is None
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True, "available": [], "missing": []}),
            stderr="",
        )

    monkeypatch.setattr(runtimes.subprocess, "run", fake_run)

    assert runtimes.runtime_catalog("ae", "pipelines") == ((), ())


def test_runtime_bridge_serializes_pipeline_and_postprocess_fields() -> None:
    from doppler_manager.processing.runtime_bridge import _serialize_catalog

    pipeline = SimpleNamespace(
        name="pipeline",
        description="Pipeline description",
        dag_requires=("input",),
        dag_produces=("output",),
    )
    postprocess = SimpleNamespace(
        name="postprocess",
        description="Postprocess description",
        input_methods=["single_file"],
        required_pipelines=["pipeline"],
    )

    pipeline_payload = _serialize_catalog([pipeline], kind="pipelines", available=True)
    postprocess_payload = _serialize_catalog(
        [postprocess],
        kind="postprocesses",
        available=True,
    )

    assert pipeline_payload[0]["dag_requires"] == ["input"]
    assert postprocess_payload[0]["input_methods"] == ["single_file"]
