from __future__ import annotations

import html
import json
from typing import List

import pandas as pd
import streamlit as st

from doppler_managing.models import AcquisitionResult, STAGE_ORDER
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
        table.extend(
            [
                "<tr>",
                _plain_cell(row["acquisition"], class_name="dm-acquisition-cell"),
                _status_cell(row["status"]),
                *[_status_cell(row[f"{stage}_status"]) for stage in STAGE_ORDER],
                _count_cell(row["warnings"]),
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
    cols = st.columns([1, 1, 4])
    csv_bytes = filtered.to_csv(index=False).encode("utf-8")
    json_bytes = json.dumps(scan_result.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")

    cols[0].download_button(
        "Export CSV",
        data=csv_bytes,
        file_name="doppler_pipeline_scan.csv",
        mime="text/csv",
        width="stretch",
    )
    cols[1].download_button(
        "Export JSON",
        data=json_bytes,
        file_name="doppler_pipeline_scan.json",
        mime="application/json",
        width="stretch",
    )


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


def _count_cell(value: object) -> str:
    count = int(value or 0)
    class_name = "dm-count-warning" if count > 0 else "dm-count-muted"
    return f'<td><span class="{class_name}">{count}</span></td>'


def _presence_cell(value: object) -> str:
    text = str(value or "")
    if not text:
        return '<td><span class="dm-presence-missing">Missing</span></td>'
    escaped = html.escape(text)
    return f'<td><span class="dm-presence-ok" title="{escaped}">Found</span></td>'
