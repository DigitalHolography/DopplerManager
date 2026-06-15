from __future__ import annotations

import io
import zipfile

import pandas as pd

from doppler_managing.models import AcquisitionResult, FileRef, STAGE_LABELS, STAGE_ORDER, StageResult
from doppler_managing.ui.dashboard import (
    build_missing_holo_lists_zip,
    missing_holo_paths_by_stage,
    scanned_holo_paths,
    _count_cell,
)


def _acquisition(acquisition_id: str, holo_path: str, statuses: dict[str, str]) -> AcquisitionResult:
    return AcquisitionResult(
        acquisition_id=acquisition_id,
        source_holo=_holo_ref(holo_path),
        stages={
            stage: StageResult(
                code=stage,
                label=STAGE_LABELS[stage],
                status=statuses.get(stage, "complete"),
            )
            for stage in STAGE_ORDER
        },
    )


def _holo_ref(holo_path: str) -> FileRef:
    return FileRef(
        path=holo_path,
        name=holo_path.rsplit("\\", 1)[-1],
        size=1,
        modified_ts=0,
        kind="holo",
    )


def test_missing_holo_paths_by_stage_uses_filtered_non_complete_stages() -> None:
    acquisitions = [
        _acquisition(
            "a",
            r"C:\data\a.holo",
            {"hd": "complete", "dv": "partial", "ef": "warning", "ae": "not_started"},
        ),
        _acquisition(
            "b",
            r"C:\data\b.holo",
            {"hd": "error", "dv": "complete", "ef": "complete", "ae": "complete"},
        ),
    ]
    filtered = pd.DataFrame([{"acquisition": "a"}])

    lists = missing_holo_paths_by_stage(acquisitions, filtered)

    assert lists == {
        "hd": [],
        "dv": [r"C:\data\a.holo"],
        "ef": [r"C:\data\a.holo"],
        "ae": [r"C:\data\a.holo"],
    }


def test_build_missing_holo_lists_zip_contains_one_text_file_per_stage() -> None:
    acquisitions = [
        _acquisition(
            "a",
            r"C:\data\a.holo",
            {"hd": "complete", "dv": "partial", "ef": "complete", "ae": "complete"},
        ),
        _acquisition(
            "b",
            r"C:\data\b.holo",
            {"hd": "complete", "dv": "complete", "ef": "complete", "ae": "complete"},
        ),
    ]
    filtered = pd.DataFrame([{"acquisition": "a"}])

    payload = build_missing_holo_lists_zip(
        acquisitions,
        filtered,
        [
            _holo_ref(r"C:\data\a.holo"),
            _holo_ref(r"C:\data\b.holo"),
            _holo_ref(r"C:\data\c.holo"),
        ],
    )

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert sorted(archive.namelist()) == [
            "list_ae.txt",
            "list_all.txt",
            "list_dv.txt",
            "list_ef.txt",
            "list_hd.txt",
        ]
        assert archive.read("list_hd.txt").decode("utf-8") == ""
        assert archive.read("list_dv.txt").decode("utf-8") == "C:\\data\\a.holo\n"
        assert (
            archive.read("list_all.txt").decode("utf-8")
            == "C:\\data\\a.holo\nC:\\data\\b.holo\nC:\\data\\c.holo\n"
        )


def test_scanned_holo_paths_can_use_unfiltered_scan_file_list() -> None:
    acquisitions = [
        _acquisition("a", r"C:\data\a.holo", {}),
        _acquisition("b", r"C:\data\b.holo", {}),
    ]

    assert scanned_holo_paths(
        acquisitions,
        [_holo_ref(r"C:\data\a.holo"), _holo_ref(r"C:\data\c.holo")],
    ) == [r"C:\data\a.holo", r"C:\data\c.holo"]


def test_warning_count_hover_escapes_warning_text() -> None:
    html = _count_cell(1, ['Missing "raw" file <check>'])

    assert "dm-count-tooltip" in html
    assert "- Missing &quot;raw&quot; file &lt;check&gt;" in html
    assert "dm-warning-details-row" not in html
