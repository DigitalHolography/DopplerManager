from pathlib import Path

import doppler_manager.launcher as launcher


def test_development_launch_syncs_processing_defaults(monkeypatch, tmp_path: Path) -> None:
    events: list[str] = []
    log_path = tmp_path / "DopplerManager.log"

    monkeypatch.setattr(launcher, "_log_path", lambda: log_path)
    monkeypatch.setattr(launcher, "_log", lambda *_args: None)
    monkeypatch.setattr(launcher, "_stop_recorded_server", lambda _path: events.append("stop"))
    monkeypatch.setattr(
        launcher,
        "sync_processing_defaults",
        lambda: events.append("sync") or [tmp_path / "default.json"],
    )
    monkeypatch.setattr(launcher, "_run", lambda *_args, **_kwargs: events.append("run"))

    launcher.launch()

    assert events == ["stop", "sync", "run"]
