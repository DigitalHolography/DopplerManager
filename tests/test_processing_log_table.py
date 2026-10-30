from pathlib import Path
from threading import Event

from streamlit.testing.v1 import AppTest

from doppler_manager.processing.core.models import JobResult, ProcessingJob
from doppler_manager.processing.execution.session import ProcessingRun
from doppler_manager.ui.processing import (
    _aggregate_processing_status,
    _processing_cell_statuses,
)


def test_log_table_selection_and_order():
    app = AppTest.from_string('''
from doppler_manager.ui.processing import _render_processing_log_view
entries = [
    {"line": "a-ef", "files": ("a",), "app": "EyeFlow"},
    {"line": "b-hd", "files": ("b",), "app": "Holodoppler"},
    {"line": "a-hd", "files": ("a",), "app": "Holodoppler"},
    {"line": "b-ef", "files": ("b",), "app": "EyeFlow"},
]
_render_processing_log_view(["b", "a"], ["hd", "ef"], entries=entries)
''').run()
    assert not app.exception
    assert not app.selectbox
    assert [b.label for b in app.button[:5]] == ["All", "HD", "DV", "EF", "AE"]
    text = app.code[0].value
    assert text.index("b-hd") < text.index("b-ef") < text.index("a-hd") < text.index("a-ef")

    # Individual cell, entire file, and entire app column.
    for key, expected in [
        ("processing_log_cell_2_1", ["a-hd"]),
        ("processing_log_cell_2_0", ["a-hd", "a-ef"]),
        ("processing_log_cell_0_3", ["b-ef", "a-ef"]),
        ("processing_log_cell_0_0", ["b-hd", "b-ef", "a-hd", "a-ef"]),
    ]:
        app.button(key=key).click().run()
        assert not app.exception
        lines = [line for line in app.code[0].value.splitlines() if line and not line.startswith("===")]
        assert lines == expected
    app.button(key="processing_log_cell_1_2").click().run()
    assert not app.code
    assert "No log entries" in app.caption[0].value


def test_run_status_survives_log_eviction_and_includes_skips(tmp_path, monkeypatch):
    import doppler_manager.processing.execution.runner as runner

    entered = Event()
    release = Event()
    jobs = [
        ProcessingJob("file", stage, ("unused",), tmp_path, stage)
        for stage in ("hd", "dv", "ef")
    ]

    def execute(job, emit):
        if job.stage == "dv":
            entered.set()
            assert release.wait(5)
            return JobResult(job, 1)
        return JobResult(job, 0)

    monkeypatch.setattr(runner, "prepare_processing_output", lambda *args: None)
    monkeypatch.setattr(runner, "run_single_job", execute)
    run = ProcessingRun(jobs, selected_file_ids=["file"], allowed_apps=[], log_limit=1)
    assert run.snapshot().job_statuses == ("pending", "pending", "pending")
    run.start()
    try:
        assert entered.wait(5)
        snapshot = run.snapshot()
        assert snapshot.job_statuses == ("complete", "running", "pending")
        cells = _processing_cell_statuses(run, snapshot.job_statuses)
        assert cells[("file", "Holodoppler")] == ["complete"]
        assert _aggregate_processing_status(snapshot.job_statuses) == "running"
    finally:
        release.set()
        run._thread.join(5)
    assert run.snapshot().job_statuses == ("complete", "failed", "skipped")
    assert _aggregate_processing_status(run.snapshot().job_statuses) == "failed"
    assert len(run.snapshot().log_entries) == 1


def test_postprocess_and_pipeline_share_angioeye_status():
    jobs = [
        ProcessingJob(file, stage, (), Path("."), stage)
        for file, stage in [("a", "ae"), ("__angioeye_postprocess__", "ae_postprocess")]
    ]
    run = ProcessingRun(jobs, selected_file_ids=["a", "b"], allowed_apps=["AngioEye"])
    cells = _processing_cell_statuses(run, ["complete", "pending"])
    assert _aggregate_processing_status(cells[("a", "AngioEye")]) == "pending"
    assert cells[("b", "AngioEye")] == ["pending"]
    assert _aggregate_processing_status(["complete", "complete"]) == "complete"
    assert _aggregate_processing_status([]) == "pending"
