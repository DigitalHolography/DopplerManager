from __future__ import annotations

from pathlib import Path

from doppler_manager.models import AcquisitionResult, STAGE_LABELS, STAGE_ORDER, StageResult
from doppler_manager.ui.media import _video_cache_path, media_by_stage


def test_media_by_stage_excludes_raw_acquisition_group() -> None:
    acquisition = AcquisitionResult(
        acquisition_id="test",
        stages={
            stage: StageResult(code=stage, label=STAGE_LABELS[stage])
            for stage in STAGE_ORDER
        },
    )

    assert list(media_by_stage(acquisition)) == [STAGE_LABELS[stage] for stage in STAGE_ORDER]


def test_video_cache_path_uses_user_writable_local_appdata(monkeypatch, tmp_path: Path) -> None:
    install_dir = tmp_path / "Program Files" / "DopplerManager" / "0.4.0"
    local_appdata = tmp_path / "Users" / "User" / "AppData" / "Local"
    source = tmp_path / "preview.avi"
    install_dir.mkdir(parents=True)
    source.write_bytes(b"avi")

    monkeypatch.chdir(install_dir)
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))

    cache_path = _video_cache_path(source)

    assert cache_path.parent == local_appdata / "DopplerManager" / ".doppler_cache" / "video_previews"
    assert "Program Files" not in str(cache_path)
