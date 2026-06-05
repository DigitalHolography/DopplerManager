from pathlib import Path

from doppler_managing.scanner import ScanOptions, scan_root


def _write(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_scan_detects_complete_pipeline(tmp_path: Path) -> None:
    acquisition_id = "251031_ALA_L_1"
    _write(tmp_path / f"{acquisition_id}.holo")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_input_HD_params.json", b"{}")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_HD" / "h5" / f"{acquisition_id}_HD_output.h5")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_HD" / "version_holodoppler.txt", b"1.2.3")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_HD" / "png" / f"{acquisition_id}_HD_M0.png")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_DV" / "h5" / f"{acquisition_id}_DV.h5")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_DV" / "config" / "DV_params.json", b"{}")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_EF" / "h5" / f"{acquisition_id}_EF.h5")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_AE" / "h5" / f"{acquisition_id}_AE.h5")

    result = scan_root(tmp_path, ScanOptions(max_depth=4))

    assert len(result.acquisitions) == 1
    acquisition = result.acquisitions[0]
    assert acquisition.acquisition_id == acquisition_id
    assert acquisition.status == "complete"
    assert acquisition.stages["hd"].status == "complete"
    assert acquisition.stages["dv"].status == "complete"
    assert acquisition.stages["ef"].status == "complete"
    assert acquisition.stages["ae"].status == "complete"
    assert acquisition.stages["hd"].versions["version_holodoppler.txt"] == "1.2.3"
    assert acquisition.stages["hd"].preview_files[0].name.endswith(".png")


def test_scan_warns_when_downstream_exists_without_upstream(tmp_path: Path) -> None:
    acquisition_id = "260307_VAB_L_3"
    _write(tmp_path / acquisition_id / f"{acquisition_id}_DV" / "h5" / f"{acquisition_id}_DV.h5")

    result = scan_root(tmp_path, ScanOptions(max_depth=4))

    assert len(result.acquisitions) == 1
    acquisition = result.acquisitions[0]
    assert acquisition.stages["hd"].status == "not_started"
    assert acquisition.stages["dv"].status == "warning"
    assert acquisition.status == "warning"
    assert any("upstream stage" in warning for warning in acquisition.warnings)


def test_scan_marks_zero_byte_h5_as_error(tmp_path: Path) -> None:
    acquisition_id = "260310_AUZ0752_1"
    _write(tmp_path / f"{acquisition_id}.holo")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_HD" / "h5" / f"{acquisition_id}_HD_output.h5", b"")

    result = scan_root(tmp_path, ScanOptions(max_depth=4))

    acquisition = result.acquisitions[0]
    assert acquisition.stages["hd"].status == "error"
    assert acquisition.status == "error"
