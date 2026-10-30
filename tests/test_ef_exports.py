from __future__ import annotations

import io
from pathlib import Path
import zipfile

import pytest
from streamlit.testing.v1 import AppTest

from doppler_manager.exports import build_cohort_ef_zip, build_ef_h5_zip, parse_cohorts
from doppler_manager.models import AcquisitionResult, FileRef, StageResult


def _acquisition(root: Path, name: str, filename: str | None = None) -> AcquisitionResult:
    folder = root / name
    folder.mkdir(parents=True)
    path = folder / (filename or f"{name}_EF.h5")
    path.write_bytes(name.encode())
    return AcquisitionResult(
        acquisition_id=name,
        source_holo=FileRef.from_path(root / f"{name}.holo", "holo"),
        acquisition_dir=FileRef.from_path(folder, "directory"),
        stages={"ef": StageResult("ef", "EyeFlow", h5_files=[FileRef.from_path(path, "h5")])},
    )


def test_all_ef_export_includes_warning_stage_and_preserves_duplicate_filenames(tmp_path):
    acquisitions = [_acquisition(tmp_path, name, "output.h5") for name in ("a", "b")]
    acquisitions[0].stages["ef"].status = "warning"
    acquisitions.append(AcquisitionResult("no_ef"))
    with zipfile.ZipFile(io.BytesIO(build_ef_h5_zip(acquisitions))) as archive:
        assert archive.namelist() == ["output.h5", "output_2.h5"]
        assert archive.read("output.h5") == b"a"
        assert archive.read("output_2.h5") == b"b"


def test_cohorts_match_paths_and_names_and_report_missing(tmp_path):
    a, b = [_acquisition(tmp_path, name) for name in ("a", "b")]
    absent = AcquisitionResult("no_ef")
    text = f'\ufeff[Controls]\n"{a.source_holo.path}"\na\nno_ef\nunknown.holo\n[Patients]\n{b.acquisition_dir.path}\n[Empty]\n'
    with zipfile.ZipFile(io.BytesIO(build_cohort_ef_zip([a, b, absent], text))) as archive:
        assert set(archive.namelist()) == {
            "Controls/", "Controls/a_EF.h5", "Patients/", "Patients/b_EF.h5", "Empty/", "missing_EF.txt",
        }
        assert archive.read("Controls/a_EF.h5") == b"a"
        assert archive.read("missing_EF.txt").decode() == "[Controls]\nno_ef\nunknown.holo\n"


def test_cohort_reports_stale_files_and_ambiguous_names(tmp_path):
    a = _acquisition(tmp_path / "one", "a")
    duplicate = _acquisition(tmp_path / "two", "a")
    b = _acquisition(tmp_path, "b")
    Path(b.stages["ef"].h5_files[0].path).unlink()
    text = f"[Cohort]\na\nb\n{a.source_holo.path}\n"
    with zipfile.ZipFile(io.BytesIO(build_cohort_ef_zip([a, duplicate, b], text))) as archive:
        assert archive.read("missing_EF.txt").decode() == "[Cohort]\na\nb\n"
        assert archive.read("Cohort/a_EF.h5") == b"a"


@pytest.mark.parametrize("text", ["", "a.holo", "[]\na", "[../outside]\na", "[C:\\folder]\na", "[CON]\na", "[missing_EF.txt]\na"])
def test_invalid_cohort_lists_are_rejected(text):
    with pytest.raises(ValueError):
        parse_cohorts(text)


@pytest.mark.parametrize("has_ef", [False, True])
def test_export_popup_options_and_ef_availability(tmp_path, has_ef):
    path = tmp_path / "app.py"
    path.write_text(
        'import pandas as pd\n'
        'import streamlit as st\n'
        'from doppler_manager.models import AcquisitionResult, ScanResult, StageResult, FileRef\n'
        'from doppler_manager.ui.dashboard import _render_export_button\n'
        f'files = [FileRef("a_EF.h5", "a_EF.h5", 1, 0, "h5")] if {has_ef} else []\n'
        'a = AcquisitionResult("a", stages={"ef": StageResult("ef", "EyeFlow", h5_files=files)})\n'
        '_render_export_button(st, ScanResult(".", [a]), pd.DataFrame([{"acquisition": "a"}]))\n'
    )
    app = AppTest.from_file(str(path)).run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert [item.value for item in app.markdown if item.value.startswith("####")] == [
        "#### 1. Export scan lists", "#### 2. Export all EF h5 files", "#### 3. Export EF h5 files by cohort",
    ]
    for button in app.button:
        if button.label.startswith("Prepare"):
            assert button.disabled is not has_ef
    assert app.text_area[0].disabled is not has_ef
