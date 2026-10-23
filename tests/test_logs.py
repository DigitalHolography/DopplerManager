import sys
from dataclasses import replace

import pytest

from doppler_manager import launcher, logs
from doppler_manager.processing.core.models import ProcessingJob
from doppler_manager.processing.execution import runner


def test_launcher_uses_roaming_logs_but_keeps_runtime_local(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert launcher._log_path() == tmp_path / "roaming/DopplerManager/logs/DopplerManager.log"
    assert launcher._runtime_dir() == tmp_path / "local/DopplerManager"
    assert {p.name for p in logs.logs_dir().iterdir()} == {
        "Holodoppler", "DopplerView", "EyeFlow", "AngioEye"
    }
    launcher._log(launcher._log_path(), "application event")
    assert "application event" in launcher._log_path().read_text(encoding="utf-8")


def test_processing_logs_capture_each_file_and_preserve_reruns(tmp_path):
    script = (
        "import sys; print('normal output'); print('échec', file=sys.stderr); "
        "raise RuntimeError('processing failed')"
    )
    first = ProcessingJob(
        acquisition_id="test", stage="dv",
        command=(sys.executable, "-c", script, str(tmp_path / "test.holo")),
        cwd=tmp_path, description="test: DopplerView",
    )
    second = replace(first, acquisition_id="second_test", command=(
        *first.command[:-1], str(tmp_path / "second_test.holo")
    ))
    ui_logs = []
    results = runner.run_processing_jobs([first, second], ui_logs.append)
    assert [result.returncode for result in results] == [1, 1]
    first_path = logs.logs_dir() / "DopplerView/test.log"
    second_path = logs.logs_dir() / "DopplerView/second_test.log"
    content = first_path.read_text(encoding="utf-8")
    for text in ("normal output", "échec", "Traceback", "processing failed", "exited with code 1", str(tmp_path), "[CMD]"):
        assert text in content
    assert "[ACQUISITION] second_test" in second_path.read_text(encoding="utf-8")
    assert "second_test" not in content
    runner.run_processing_jobs([first], ui_logs.append)
    rerun = first_path.read_text(encoding="utf-8")
    assert rerun.startswith(content)
    assert rerun.count("[RUN]") == 2
    main = logs.main_log_path().read_text(encoding="utf-8")
    assert str(first_path) in main and str(second_path) in main
    assert "exited with code 1" in main


@pytest.mark.parametrize("failure_point", ["prepare_processing_output", "run_single_job", "install_eyeflow_output"])
def test_manager_exceptions_are_logged_and_fail_the_job(monkeypatch, tmp_path, failure_point):
    job = ProcessingJob("test", "ef", (sys.executable, "-c", "pass"), tmp_path, "test: EyeFlow")

    def fail(*args):
        raise PermissionError("access denied")

    monkeypatch.setattr(runner, failure_point, fail)
    result = runner.run_processing_jobs([job], lambda line: None)
    assert not result[0].succeeded
    for path in (logs.main_log_path(), logs.logs_dir() / "EyeFlow/test.log"):
        content = path.read_text(encoding="utf-8")
        assert "PermissionError: access denied" in content
        assert "Traceback" in content


def test_windowed_dispatcher_errors_go_to_the_processing_log(monkeypatch, tmp_path):
    path = tmp_path / "processing.log"
    with monkeypatch.context() as patch:
        patch.setenv("DM_PROCESSING_LOG", str(path))
        patch.setattr(sys, "argv", ["DopplerManager.exe", launcher.PROCESSING_CLI_SENTINEL, "dv"])
        patch.setattr(sys, "stdout", None)
        patch.setattr(sys, "stderr", None)
        launcher._configure_stdio(tmp_path / "main.log")
        stream = sys.stderr
        print("dispatcher failure", file=stream)
    stream.close()
    assert "dispatcher failure" in path.read_text(encoding="utf-8")
    assert not (tmp_path / "main.log").exists()


def test_missing_executable_and_upstream_skip_are_persisted(tmp_path):
    job = ProcessingJob("test", "dv", (str(tmp_path / "missing.exe"),), tmp_path, "test: DopplerView")
    downstream = replace(job, stage="ef", description="test: EyeFlow")
    results = runner.run_processing_jobs([job, downstream], lambda line: None)
    assert results[0].returncode == 127
    content = (logs.logs_dir() / "DopplerView/test.log").read_text(encoding="utf-8")
    assert "Could not launch" in content and "exited with code 127" in content
    assert "[SKIP]" in (logs.logs_dir() / "EyeFlow/test.log").read_text(encoding="utf-8")
