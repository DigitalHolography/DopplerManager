from pathlib import Path

from doppler_manager.scan import ScanOptions, holo_filter_ids_from_text, scan_root


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


def test_scan_does_not_warn_when_downstream_exists_without_upstream(tmp_path: Path) -> None:
    acquisition_id = "260307_VAB_L_3"
    _write(tmp_path / f"{acquisition_id}.holo")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_DV" / "h5" / f"{acquisition_id}_DV.h5")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_AE" / "h5" / f"{acquisition_id}_AE.h5")

    result = scan_root(tmp_path, ScanOptions(max_depth=4))

    assert len(result.acquisitions) == 1
    acquisition = result.acquisitions[0]
    assert acquisition.stages["hd"].status == "not_started"
    assert acquisition.stages["dv"].status == "complete"
    assert acquisition.stages["ef"].status == "not_started"
    assert acquisition.stages["ae"].status == "complete"
    assert acquisition.status == "partial"
    assert not acquisition.warnings
    assert not any("upstream" in warning.lower() for warning in acquisition.warning_messages())


def test_scan_does_not_warn_when_eyeflow_exists_without_dopplerview(tmp_path: Path) -> None:
    acquisition_id = "260307_VAB_L_3"
    _write(tmp_path / f"{acquisition_id}.holo")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_HD" / "h5" / f"{acquisition_id}_HD_output.h5")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_EF" / "h5" / f"{acquisition_id}_EF.h5")

    result = scan_root(tmp_path, ScanOptions(max_depth=4))

    acquisition = result.acquisitions[0]
    assert acquisition.stages["dv"].status == "not_started"
    assert acquisition.stages["ef"].status == "complete"
    assert not any("DopplerView" in warning for warning in acquisition.warning_messages())


def test_scan_marks_zero_byte_h5_as_error(tmp_path: Path) -> None:
    acquisition_id = "260310_AUZ0752_1"
    _write(tmp_path / f"{acquisition_id}.holo")
    _write(tmp_path / acquisition_id / f"{acquisition_id}_HD" / "h5" / f"{acquisition_id}_HD_output.h5", b"")

    result = scan_root(tmp_path, ScanOptions(max_depth=4))

    acquisition = result.acquisitions[0]
    assert acquisition.stages["hd"].status == "error"
    assert acquisition.status == "error"


def test_holo_filter_text_accepts_holo_filenames_paths_and_comments() -> None:
    ids = holo_filter_ids_from_text(
        """
        # one .holo per line
        251031_ALA_L_1.holo
        C:\\data\\260307_VAB_L_3.holo
        260310_AUZ0752_1
        """
    )

    assert ids == {"251031_ALA_L_1", "260307_VAB_L_3", "260310_AUZ0752_1"}


def test_scan_can_be_limited_to_holo_filter_list(tmp_path: Path) -> None:
    included_id = "251031_ALA_L_1"
    excluded_id = "260307_VAB_L_3"
    _write(tmp_path / f"{included_id}.holo")
    _write(tmp_path / included_id / f"{included_id}_HD" / "h5" / f"{included_id}_HD_output.h5")
    _write(tmp_path / f"{excluded_id}.holo")
    _write(tmp_path / excluded_id / f"{excluded_id}_HD" / "h5" / f"{excluded_id}_HD_output.h5")

    result = scan_root(
        tmp_path,
        ScanOptions(
            max_depth=4,
            holo_filter_ids=holo_filter_ids_from_text(f"{included_id}.holo\n"),
        ),
    )

    assert [acquisition.acquisition_id for acquisition in result.acquisitions] == [included_id]
    assert [Path(file.path).name for file in result.all_holo_files] == [
        f"{included_id}.holo",
        f"{excluded_id}.holo",
    ]
