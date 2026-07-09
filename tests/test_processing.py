import sys
from pathlib import Path

import pytest

import doppler_manager._external_cli_runner as external_cli_runner
import doppler_manager.processing as processing
from doppler_manager.models import AcquisitionResult, FileRef, StageResult
from doppler_manager.processing import (
    build_processing_jobs,
    discover_holodoppler_settings,
    install_angioeye_output,
    install_eyeflow_output,
    missing_default_processing_tools,
    needed_processing_stages,
    preferred_holodoppler_settings,
    processing_defaults_dir,
)


def _write(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _acquisition(tmp_path: Path, acquisition_id: str) -> AcquisitionResult:
    holo_path = tmp_path / f"{acquisition_id}.holo"
    acquisition_dir = tmp_path / acquisition_id
    hd_h5 = acquisition_dir / f"{acquisition_id}_HD" / "h5" / f"{acquisition_id}_HD_output.h5"
    dv_h5 = acquisition_dir / f"{acquisition_id}_DV" / "h5" / f"{acquisition_id}_DV.h5"
    ef_h5 = acquisition_dir / f"{acquisition_id}_EF" / "h5" / f"{acquisition_id}_EF.h5"
    _write(holo_path)
    _write(hd_h5)
    _write(dv_h5)
    _write(ef_h5)

    acquisition = AcquisitionResult(
        acquisition_id=acquisition_id,
        source_holo=FileRef.from_path(holo_path, "holo"),
        acquisition_dir=FileRef.from_path(acquisition_dir, "directory"),
    )
    acquisition.stages = {
        "hd": StageResult(
            code="hd",
            label="Holodoppler",
            h5_files=[FileRef.from_path(hd_h5, "h5")],
            status="complete",
        ),
        "dv": StageResult(
            code="dv",
            label="DopplerView",
            h5_files=[FileRef.from_path(dv_h5, "h5")],
            status="complete",
        ),
        "ef": StageResult(
            code="ef",
            label="EyeFlow",
            h5_files=[FileRef.from_path(ef_h5, "h5")],
            status="complete",
        ),
        "ae": StageResult(code="ae", label="AngioEye"),
    }
    return acquisition


def test_build_processing_jobs_keeps_stage_order(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DM_HOLODOPPLER_COMMAND", "hd-command")
    monkeypatch.setenv("DM_DOPPLERVIEW_COMMAND", "dv-command")
    monkeypatch.setenv("DM_EYEFLOW_COMMAND", "ef-command")
    monkeypatch.setenv("DM_ANGIOEYE_COMMAND", "ae-command")

    acquisition_id = "251031_ALA_L_1"
    settings_path = tmp_path / "parameters" / "default_parameters.json"
    _write(
        settings_path,
        b'{"temporal_transformation": "FourierTransform", "frequency_bands": []}',
    )
    acquisition = _acquisition(tmp_path, acquisition_id)

    jobs = build_processing_jobs(
        [acquisition],
        [acquisition_id],
        ["ae", "ef", "hd", "dv"],
        hd_settings_path=settings_path,
        cache_dir=tmp_path / ".doppler_cache",
    )

    assert [job.stage for job in jobs] == ["hd", "dv", "ef", "ae"]
    assert jobs[0].command == (
        "hd-command",
        "process",
        str(tmp_path / f"{acquisition_id}.holo"),
        str(settings_path),
    )
    assert jobs[1].command[:2] == ("dv-command", str(tmp_path / f"{acquisition_id}.holo"))
    assert jobs[2].command[:2] == ("ef-command", "--data")
    assert jobs[3].command[:2] == ("ae-command", "--data")
    assert jobs[3].command[jobs[3].command.index("--data") + 1] == str(
        tmp_path / acquisition_id / f"{acquisition_id}_EF" / "h5" / f"{acquisition_id}_EF.h5"
    )


def test_install_eyeflow_output_replaces_expected_stage_folder(tmp_path: Path) -> None:
    acquisition_id = "251031_ALA_L_1"
    acquisition_dir = tmp_path / acquisition_id
    destination = acquisition_dir / f"{acquisition_id}_EF"
    temp_root = tmp_path / ".doppler_cache" / "processing" / "eyeflow_runs" / "run"
    generated = temp_root / acquisition_id / f"{acquisition_id}_EF"
    _write(destination / "h5" / "old.h5")
    _write(generated / "h5" / f"{acquisition_id}_EF.h5")

    acquisition = _acquisition(tmp_path, acquisition_id)
    job = build_processing_jobs(
        [acquisition],
        [acquisition_id],
        ["ef"],
        hd_settings_path=None,
        cache_dir=tmp_path / ".doppler_cache",
    )[0]
    job = job.__class__(
        acquisition_id=job.acquisition_id,
        stage=job.stage,
        command=job.command,
        cwd=job.cwd,
        description=job.description,
        ef_temp_root=temp_root,
        ef_destination=destination,
    )

    logs: list[str] = []
    install_eyeflow_output(job, logs.append)

    assert not (destination / "h5" / "old.h5").exists()
    assert (destination / "h5" / f"{acquisition_id}_EF.h5").exists()
    assert any("EyeFlow" in line for line in logs)


def test_eyeflow_job_uses_absolute_generated_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DM_EYEFLOW_COMMAND", "ef-command")
    acquisition_id = "251031_ALA_L_1"
    acquisition = _acquisition(tmp_path, acquisition_id)

    jobs = build_processing_jobs(
        [acquisition],
        [acquisition_id],
        ["ef"],
        hd_settings_path=None,
        cache_dir=Path(".doppler_cache"),
    )

    job = jobs[0]
    pipelines_path = Path(job.command[job.command.index("--pipelines") + 1])
    output_path = Path(job.command[job.command.index("--output") + 1])

    assert pipelines_path.is_absolute()
    assert output_path.is_absolute()
    assert pipelines_path.is_file()


def test_eyeflow_job_requires_existing_dopplerview_h5(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DM_EYEFLOW_COMMAND", "ef-command")
    acquisition_id = "251031_ALA_L_1"
    acquisition = _acquisition(tmp_path, acquisition_id)
    acquisition.stages["dv"] = StageResult(code="dv", label="DopplerView", status="not_started")

    with pytest.raises(FileNotFoundError, match="DV .h5 file is required"):
        build_processing_jobs(
            [acquisition],
            [acquisition_id],
            ["ef"],
            hd_settings_path=None,
            cache_dir=tmp_path / ".doppler_cache",
        )


def test_eyeflow_can_use_dopplerview_from_same_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DM_DOPPLERVIEW_COMMAND", "dv-command")
    monkeypatch.setenv("DM_EYEFLOW_COMMAND", "ef-command")
    acquisition_id = "251031_ALA_L_1"
    acquisition = _acquisition(tmp_path, acquisition_id)
    acquisition.stages["dv"] = StageResult(code="dv", label="DopplerView", status="not_started")

    jobs = build_processing_jobs(
        [acquisition],
        [acquisition_id],
        ["ef", "dv"],
        hd_settings_path=None,
        cache_dir=tmp_path / ".doppler_cache",
    )

    assert [job.stage for job in jobs] == ["dv", "ef"]


def test_angioeye_job_uses_existing_eyeflow_h5_and_absolute_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DM_ANGIOEYE_COMMAND", "ae-command")
    acquisition_id = "251031_ALA_L_1"
    acquisition = _acquisition(tmp_path, acquisition_id)

    jobs = build_processing_jobs(
        [acquisition],
        [acquisition_id],
        ["ae"],
        hd_settings_path=None,
        cache_dir=Path(".doppler_cache"),
    )

    job = jobs[0]
    data_path = Path(job.command[job.command.index("--data") + 1])
    pipelines_path = Path(job.command[job.command.index("--pipelines") + 1])
    output_path = Path(job.command[job.command.index("--output") + 1])

    assert data_path == tmp_path / acquisition_id / f"{acquisition_id}_EF" / "h5" / f"{acquisition_id}_EF.h5"
    assert pipelines_path.is_absolute()
    assert output_path.is_absolute()
    assert pipelines_path.is_file()
    assert "--trim-source" in job.command


def test_build_processing_jobs_uses_selected_ef_and_ae_pipelines(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DM_EYEFLOW_COMMAND", "ef-command")
    monkeypatch.setenv("DM_ANGIOEYE_COMMAND", "ae-command")
    acquisition_id = "251031_ALA_L_1"
    acquisition = _acquisition(tmp_path, acquisition_id)

    jobs = build_processing_jobs(
        [acquisition],
        [acquisition_id],
        ["ef", "ae"],
        hd_settings_path=None,
        cache_dir=tmp_path / ".doppler_cache",
        eyeflow_pipelines=["dual_input_tutorial", "waveform_shape_metrics"],
        angioeye_pipelines=["modal_analysis", "waveform_shape_metrics"],
    )

    ef_job = next(job for job in jobs if job.stage == "ef")
    ae_job = next(job for job in jobs if job.stage == "ae")
    ef_pipelines_path = Path(ef_job.command[ef_job.command.index("--pipelines") + 1])
    ae_pipelines_path = Path(ae_job.command[ae_job.command.index("--pipelines") + 1])

    assert ef_pipelines_path.read_text(encoding="utf-8") == (
        "dual_input_tutorial\nwaveform_shape_metrics\n"
    )
    assert ae_pipelines_path.read_text(encoding="utf-8") == (
        "modal_analysis\nwaveform_shape_metrics\n"
    )


def test_build_processing_jobs_can_skip_completed_stages(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DM_ANGIOEYE_COMMAND", "ae-command")
    acquisition_id = "251031_ALA_L_1"
    acquisition = _acquisition(tmp_path, acquisition_id)

    jobs = build_processing_jobs(
        [acquisition],
        [acquisition_id],
        ["hd", "dv", "ef", "ae"],
        hd_settings_path=None,
        cache_dir=tmp_path / ".doppler_cache",
        only_incomplete=True,
    )

    assert [job.stage for job in jobs] == ["ae"]


def test_needed_processing_stages_includes_needs_review(tmp_path: Path) -> None:
    acquisition_id = "251031_ALA_L_1"
    acquisition = _acquisition(tmp_path, acquisition_id)
    acquisition.stages["ef"].status = "warning"

    assert needed_processing_stages(
        [acquisition],
        ["hd", "dv", "ef", "ae"],
        only_incomplete=True,
    ) == ["ef", "ae"]


def test_install_angioeye_output_replaces_expected_stage_folder(tmp_path: Path) -> None:
    acquisition_id = "251031_ALA_L_1"
    acquisition_dir = tmp_path / acquisition_id
    destination = acquisition_dir / f"{acquisition_id}_AE"
    temp_root = tmp_path / ".doppler_cache" / "processing" / "angioeye_runs" / "run"
    generated = temp_root / f"{acquisition_id}_EF_pipelines_result.h5"
    _write(destination / "h5" / "old.h5")
    _write(generated)

    job = processing.ProcessingJob(
        acquisition_id=acquisition_id,
        stage="ae",
        command=("ae-command",),
        cwd=tmp_path,
        description=f"{acquisition_id}: AngioEye",
        ae_temp_root=temp_root,
        ae_destination=destination,
    )

    logs: list[str] = []
    install_angioeye_output(job, logs.append)

    assert not (destination / "h5" / "old.h5").exists()
    assert (destination / "h5" / f"{acquisition_id}_AE.h5").exists()
    assert not generated.exists()
    assert any("AngioEye" in line for line in logs)


def test_run_processing_jobs_deletes_existing_stage_folder_before_launch(tmp_path: Path) -> None:
    acquisition_id = "251031_ALA_L_1"
    destination = tmp_path / acquisition_id / f"{acquisition_id}_HD"
    _write(destination / "h5" / "old.h5")
    script = (
        "import pathlib, sys\n"
        "destination = pathlib.Path(sys.argv[1])\n"
        "raise SystemExit(1 if destination.exists() else 0)\n"
    )
    job = processing.ProcessingJob(
        acquisition_id=acquisition_id,
        stage="hd",
        command=(sys.executable, "-c", script, str(destination)),
        cwd=tmp_path,
        description=f"{acquisition_id}: Holodoppler",
        stage_destination=destination,
    )
    logs: list[str] = []

    results = processing.run_processing_jobs([job], logs.append)

    assert results[0].succeeded
    assert not destination.exists()
    assert any(line.startswith("[DELETE]") for line in logs)


def test_missing_default_processing_tools_respects_command_override(monkeypatch) -> None:
    monkeypatch.setattr(processing.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(processing, "_find_uv_git_cli", lambda _tool_config: None)

    assert missing_default_processing_tools(["hd"]) == ["hd"]

    monkeypatch.setenv("DM_HOLODOPPLER_COMMAND", "holodoppler.exe")

    assert missing_default_processing_tools(["hd"]) == []


def test_missing_default_processing_tools_accepts_uv_git_cli(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(processing.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(processing, "_find_uv_git_cli", lambda _tool_config: tmp_path / "cli.py")

    assert missing_default_processing_tools(["ef", "ae"]) == []


def test_missing_default_processing_tools_accepts_frozen_processing_bundle(monkeypatch) -> None:
    monkeypatch.setattr(processing.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(processing, "_find_uv_git_cli", lambda _tool_config: None)
    monkeypatch.setattr(processing.sys, "frozen", True, raising=False)

    assert missing_default_processing_tools(["ef", "ae"]) == []
    assert missing_default_processing_tools(["hd"]) == ["hd"]


def test_frozen_processing_command_prefix_uses_launcher_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(processing.sys, "frozen", True, raising=False)
    monkeypatch.setattr(processing.sys, "executable", r"C:\App\DopplerManager.exe")

    assert processing.command_prefix_for_stage("dv") == (
        r"C:\App\DopplerManager.exe",
        processing.PROCESSING_CLI_SENTINEL,
        "dv",
    )


def test_run_single_job_keeps_progress_as_replaceable_log_lines(tmp_path: Path) -> None:
    script = (
        "import sys\n"
        "sys.stdout.write('before\\n')\n"
        "sys.stdout.flush()\n"
        "for index in range(3):\n"
        "    sys.stdout.write(f'\\r {index}/3')\n"
        "    sys.stdout.flush()\n"
        "sys.stdout.write('\\r done\\n')\n"
        "sys.stdout.write('after\\r\\n')\n"
        "sys.stdout.flush()\n"
    )
    job = processing.ProcessingJob(
        acquisition_id="acq",
        stage="hd",
        command=(sys.executable, "-c", script),
        cwd=tmp_path,
        description="test job",
    )
    logs: list[str] = []

    result = processing._run_single_job(job, logs.append)

    assert result.succeeded
    progress = processing.PROGRESS_LOG_PREFIX
    assert logs == [
        "before",
        f"{progress}0/3",
        f"{progress}1/3",
        f"{progress}2/3",
        f"{progress}done",
        "after",
    ]


def test_bundled_holodoppler_defaults_are_discovered_and_preferred(tmp_path: Path, monkeypatch) -> None:
    defaults_dir = tmp_path / "processing_defaults" / "holodoppler"
    default_settings = defaults_dir / "default_parameters.json"
    debug_settings = defaults_dir / "default_parameters_debug.json"
    simple_settings = defaults_dir / "default_parameters_simple.yaml"
    _write(default_settings, b"{}")
    _write(debug_settings, b'{"temporal_transformation": "FourierTransform"}')
    _write(simple_settings, b"temporal_transformation: FourierTransform")
    monkeypatch.setattr(processing, "_upstream_holodoppler_settings_dir", lambda: None)
    monkeypatch.setattr(processing, "REPO_PROCESSING_DEFAULTS", tmp_path / "processing_defaults")
    monkeypatch.chdir(tmp_path)

    discovered = discover_holodoppler_settings(tmp_path)

    assert default_settings in discovered
    assert debug_settings in discovered
    assert simple_settings in discovered
    assert preferred_holodoppler_settings(discovered) == debug_settings


def test_holodoppler_defaults_prefer_installed_tool_parameters(tmp_path: Path, monkeypatch) -> None:
    upstream_dir = tmp_path / "uv-cache" / "git-v0" / "checkouts" / "holodoppler" / "abcdef0" / "parameters"
    upstream_settings = upstream_dir / "default_parameters.json"
    repo_settings = tmp_path / "processing_defaults" / "holodoppler" / "default_parameters.json"
    _write(
        upstream_settings,
        b'{"source": "upstream", "temporal_transformation": "FourierTransform"}',
    )
    _write(
        repo_settings,
        b'{"source": "repo", "temporal_transformation": "FourierTransform"}',
    )
    monkeypatch.setattr(processing, "_upstream_holodoppler_settings_dir", lambda: upstream_dir)
    monkeypatch.setattr(processing, "REPO_PROCESSING_DEFAULTS", tmp_path / "processing_defaults")
    monkeypatch.chdir(tmp_path)

    discovered = discover_holodoppler_settings(tmp_path)

    assert upstream_settings in discovered
    assert repo_settings in discovered
    assert preferred_holodoppler_settings(discovered) == upstream_settings


def test_processing_defaults_dir_prefers_pyinstaller_bundle(tmp_path: Path, monkeypatch) -> None:
    bundled = tmp_path / "_internal" / "processing_defaults"
    bundled.mkdir(parents=True)
    exe_defaults = tmp_path / "installed" / "processing_defaults"
    exe_defaults.mkdir(parents=True)
    monkeypatch.setattr(processing.sys, "_MEIPASS", str(tmp_path / "_internal"), raising=False)
    monkeypatch.setattr(processing.sys, "frozen", True, raising=False)
    monkeypatch.setattr(processing.sys, "executable", str(tmp_path / "installed" / "DopplerManager.exe"))
    monkeypatch.setattr(processing, "REPO_PROCESSING_DEFAULTS", tmp_path / "repo" / "processing_defaults")

    assert processing_defaults_dir() == bundled


def test_processing_defaults_dir_uses_installed_exe_neighbor(tmp_path: Path, monkeypatch) -> None:
    exe_defaults = tmp_path / "installed" / "processing_defaults"
    exe_defaults.mkdir(parents=True)
    monkeypatch.delattr(processing.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(processing.sys, "frozen", True, raising=False)
    monkeypatch.setattr(processing.sys, "executable", str(tmp_path / "installed" / "DopplerManager.exe"))
    monkeypatch.setattr(processing, "REPO_PROCESSING_DEFAULTS", tmp_path / "repo" / "processing_defaults")

    assert processing_defaults_dir() == exe_defaults


def test_pipeline_defaults_prefer_installed_tool_settings(tmp_path: Path, monkeypatch) -> None:
    checkout = tmp_path / "uv-cache" / "git-v0" / "checkouts" / "repo" / "abcdef0"
    upstream_settings = checkout / "default_settings.json"
    _write(
        checkout / "pyproject.toml",
        b'[project]\nname = "EyeFlow"\n',
    )
    _write(checkout / "src" / "cli.py", b'"""Run EyeFlow pipelines."""\n')
    _write(
        upstream_settings,
        (
            b'{"pipeline_visibility": {'
            b'"upstream_selected": true, '
            b'"upstream_available": false'
            b"}}"
        ),
    )

    class FakeDistribution:
        def read_text(self, name: str) -> str | None:
            if name != "direct_url.json":
                return None
            return (
                '{"url": "https://github.com/DigitalHolography/EyeFlowPython.git", '
                '"vcs_info": {"vcs": "git", "commit_id": "abcdef0123456789"}}'
    )

    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    monkeypatch.setattr(
        external_cli_runner.metadata,
        "distribution",
        lambda _name: FakeDistribution(),
    )

    repo_defaults = tmp_path / "processing_defaults" / "eyeflow"
    _write(
        repo_defaults / "default_settings.json",
        b'{"pipeline_visibility": {"repo_selected": true}}',
    )
    monkeypatch.setattr(processing, "REPO_PROCESSING_DEFAULTS", tmp_path / "processing_defaults")

    assert processing.available_pipelines_for_stage("ef") == (
        "upstream_selected",
        "upstream_available",
        "waveform_shape_metrics",
    )
    assert processing.default_pipelines_for_stage("ef") == ("upstream_selected",)


def test_pipeline_defaults_fall_back_to_repo_settings(tmp_path: Path, monkeypatch) -> None:
    repo_defaults = tmp_path / "processing_defaults" / "angioeye"
    _write(
        repo_defaults / "default_settings.json",
        (
            b'{"pipeline_visibility": {'
            b'"repo_selected": true, '
            b'"repo_available": false'
            b"}}"
        ),
    )
    monkeypatch.setattr(processing, "REPO_PROCESSING_DEFAULTS", tmp_path / "processing_defaults")
    monkeypatch.setattr(processing, "_upstream_pipeline_settings_path", lambda _stage: None)

    assert processing.available_pipelines_for_stage("ae") == (
        "repo_selected",
        "repo_available",
        "waveform_shape_metrics",
    )
    assert processing.default_pipelines_for_stage("ae") == ("repo_selected",)
