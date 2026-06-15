from __future__ import annotations

import html
import io
from typing import List
import zipfile

import pandas as pd
import streamlit as st

from doppler_managing.models import AcquisitionResult, FileRef, STAGE_ORDER
from doppler_managing.ui.formatting import status_text


def render_filters(acquisitions: List[AcquisitionResult]) -> pd.DataFrame:
    frame = pd.DataFrame([acquisition.to_row() for acquisition in acquisitions])

    st.subheader("Acquisition Index")
    cols = st.columns([2, 1.2])
    query = cols[0].text_input("Filter by acquisition", value="")
    statuses = cols[1].multiselect(
        "Global status",
        options=sorted(frame["status"].unique().tolist()),
        format_func=status_text,
    )
    check_cols = st.columns([1, 1, 1, 3])
    missing_hd = check_cols[0].checkbox("Missing HD")
    missing_dv = check_cols[1].checkbox("Missing DV")
    missing_final = check_cols[2].checkbox("Missing AE")

    filtered = frame.copy()
    if query:
        filtered = filtered[filtered["acquisition"].str.contains(query, case=False, na=False)]
    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]
    if missing_hd:
        filtered = filtered[filtered["hd_status"] != "complete"]
    if missing_dv:
        filtered = filtered[filtered["dv_status"] != "complete"]
    if missing_final:
        filtered = filtered[filtered["ae_status"] != "complete"]
    return filtered


def render_overview_table(frame: pd.DataFrame) -> None:
    headers = [
        "Acquisition",
        "Global",
        "HD",
        "DV",
        "EF",
        "AE",
        "Warn",
        "Err",
        "Raw",
        "Folder",
    ]
    table = [
        '<div class="dm-index-scroll">',
        '<table class="dm-index-table">',
        "<thead><tr>",
        *[f"<th>{html.escape(header)}</th>" for header in headers],
        "</tr></thead><tbody>",
    ]

    for row in frame.to_dict("records"):
        warning_messages = _warning_messages(row.get("warning_messages"))
        table.extend(
            [
                "<tr>",
                _plain_cell(row["acquisition"], class_name="dm-acquisition-cell"),
                _status_cell(row["status"]),
                *[_status_cell(row[f"{stage}_status"]) for stage in STAGE_ORDER],
                _count_cell(row["warnings"], warning_messages),
                _count_cell(row["errors"]),
                _presence_cell(row["source_holo"]),
                _presence_cell(row["acquisition_dir"]),
                "</tr>",
            ]
        )

    table.extend(["</tbody></table></div>"])
    st.markdown("".join(table), unsafe_allow_html=True)


def render_exports(scan_result, filtered: pd.DataFrame) -> None:
    st.markdown('<div class="dm-export-spacer"></div>', unsafe_allow_html=True)
    cols = st.columns([1, 5])
    zip_bytes = build_missing_holo_lists_zip(
        scan_result.acquisitions,
        filtered,
        scan_result.all_holo_files,
    )

    cols[0].download_button(
        "Export list",
        data=zip_bytes,
        file_name="doppler_pipeline_missing_holo_lists.zip",
        mime="application/zip",
        width="stretch",
    )


def build_missing_holo_lists_zip(
    acquisitions: List[AcquisitionResult],
    filtered: pd.DataFrame,
    all_holo_files: List[FileRef] | None = None,
) -> bytes:
    lists = missing_holo_paths_by_stage(acquisitions, filtered)
    all_holo_paths = scanned_holo_paths(acquisitions, all_holo_files)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for stage in STAGE_ORDER:
            payload = "\n".join(lists[stage])
            if payload:
                payload += "\n"
            archive.writestr(f"list_{stage}.txt", payload)
        payload = "\n".join(all_holo_paths)
        if payload:
            payload += "\n"
        archive.writestr("list_all.txt", payload)
    return buffer.getvalue()


def scanned_holo_paths(
    acquisitions: List[AcquisitionResult],
    all_holo_files: List[FileRef] | None = None,
) -> list[str]:
    if all_holo_files is not None:
        paths = [file.path for file in all_holo_files]
    else:
        paths = [
            acquisition.source_holo.path
            for acquisition in acquisitions
            if acquisition.source_holo is not None
        ]
    return sorted(dict.fromkeys(paths))


def missing_holo_paths_by_stage(
    acquisitions: List[AcquisitionResult],
    filtered: pd.DataFrame,
) -> dict[str, list[str]]:
    filtered_ids = set(filtered["acquisition"].astype(str).tolist())
    lists: dict[str, list[str]] = {stage: [] for stage in STAGE_ORDER}

    for acquisition in acquisitions:
        if acquisition.acquisition_id not in filtered_ids or acquisition.source_holo is None:
            continue

        for stage in STAGE_ORDER:
            result = acquisition.stages.get(stage)
            if result is None or result.status != "complete":
                lists[stage].append(acquisition.source_holo.path)

    for stage in STAGE_ORDER:
        lists[stage] = sorted(dict.fromkeys(lists[stage]))
    return lists


def _plain_cell(value: object, class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    return f"<td{class_attr}>{html.escape(str(value))}</td>"


def _status_cell(status: object) -> str:
    status_key = str(status)
    status_class = status_key.replace("_", "-")
    label = status_text(status_key)
    return (
        "<td>"
        f'<span class="dm-status-pill dm-status-{status_class}">{html.escape(label)}</span>'
        "</td>"
    )


def _count_cell(value: object, details: List[str] | None = None) -> str:
    count = int(value or 0)
    class_name = "dm-count-warning" if count > 0 else "dm-count-muted"
    if details:
        class_name += " dm-count-with-details"
        tooltip_items = "".join(
            f'<span class="dm-count-tooltip-line">- {html.escape(detail)}</span>'
            for detail in details
        )
        aria_label = html.escape("Warnings: " + "; ".join(details), quote=True)
        return (
            "<td>"
            f'<span class="{class_name}" aria-label="{aria_label}" tabindex="0">'
            f"{count}"
            f'<span class="dm-count-tooltip" role="tooltip">{tooltip_items}</span>'
            "</span>"
            "</td>"
        )
    return f'<td><span class="{class_name}">{count}</span></td>'


def _warning_messages(value: object) -> List[str]:
    if isinstance(value, (list, tuple)):
        return [message for item in value if (message := str(item).strip())]

    if value is None:
        return []

    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass

    return [message for line in str(value).splitlines() if (message := line.strip())]


def _presence_cell(value: object) -> str:
    text = str(value or "")
    if not text:
        return '<td><span class="dm-presence-missing">Missing</span></td>'
    escaped = html.escape(text)
    return f'<td><span class="dm-presence-ok" title="{escaped}">Found</span></td>'
