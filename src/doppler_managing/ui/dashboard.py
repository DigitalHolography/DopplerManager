from __future__ import annotations

import html
import io
from pathlib import Path
import re
from typing import List
import zipfile

import pandas as pd
import streamlit as st

from doppler_managing.models import AcquisitionResult, FileRef, STAGE_ORDER
from doppler_managing.ui.formatting import status_text


FILTER_REGEX_KEY = "index_filter_acquisition_regex"
FILTER_REGEX_PATTERNS_KEY = "index_filter_regex_patterns"
FILTER_STATUSES_KEY = "index_filter_statuses"
FILTER_MISSING_HD_KEY = "index_filter_missing_hd"
FILTER_MISSING_DV_KEY = "index_filter_missing_dv"
FILTER_MISSING_AE_KEY = "index_filter_missing_ae"
FILTER_DIALOG_REGEX_KEY = "index_filter_dialog_acquisition_regex"
FILTER_REGEX_FILE_NAME_KEY = "index_filter_regex_file_name"
FILTER_REGEX_FILE_DISPLAY_KEY = "index_filter_regex_file_display"
FILTER_REGEX_FILE_TEXT_KEY = "index_filter_regex_file_text"
FILTER_REGEX_FILE_ERROR_KEY = "index_filter_regex_file_error"
FILTER_DIALOG_STATUSES_KEY = "index_filter_dialog_statuses"
FILTER_DIALOG_MISSING_HD_KEY = "index_filter_dialog_missing_hd"
FILTER_DIALOG_MISSING_DV_KEY = "index_filter_dialog_missing_dv"
FILTER_DIALOG_MISSING_AE_KEY = "index_filter_dialog_missing_ae"


def render_filters(acquisitions: List[AcquisitionResult], scan_result) -> pd.DataFrame:
    frame = pd.DataFrame([acquisition.to_row() for acquisition in acquisitions])
    status_options = sorted(frame["status"].unique().tolist())

    st.subheader("Acquisition Index")
    filter_cols = st.columns([1.125, 1.125, 6.4])
    if filter_cols[0].button(
        "Filter",
        icon=":material/filter_list:",
        width="stretch",
    ):
        _render_filter_dialog(status_options)

    filtered = frame.copy()
    acquisition_regex = str(st.session_state.get(FILTER_REGEX_KEY, "")).strip()
    if acquisition_regex:
        filtered = _filter_acquisition_regex(filtered, acquisition_regex)
    regex_patterns = st.session_state.get(FILTER_REGEX_PATTERNS_KEY, [])
    if regex_patterns:
        filtered = _filter_acquisition_regex_list(filtered, regex_patterns)
    statuses = st.session_state.get(FILTER_STATUSES_KEY, [])
    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]
    if st.session_state.get(FILTER_MISSING_HD_KEY, False):
        filtered = filtered[filtered["hd_status"] != "complete"]
    if st.session_state.get(FILTER_MISSING_DV_KEY, False):
        filtered = filtered[filtered["dv_status"] != "complete"]
    if st.session_state.get(FILTER_MISSING_AE_KEY, False):
        filtered = filtered[filtered["ae_status"] != "complete"]

    _render_export_button(filter_cols[1], scan_result, filtered)
    return filtered


@st.dialog("Filter", width="medium", icon=":material/filter_list:", on_dismiss="rerun")
def _render_filter_dialog(status_options: list[str]) -> None:
    _prepare_filter_dialog_defaults(status_options)
    st.markdown("#### Name filters")
    st.text_input(
        "Acquisition regex",
        key=FILTER_DIALOG_REGEX_KEY,
        on_change=_sync_filter_regex,
    )
    st.button(
        "Browse regex list",
        icon=":material/folder_open:",
        help="Browse for a regex list file",
        width="stretch",
        on_click=_browse_regex_filter_file,
    )
    file_error = st.session_state.pop(FILTER_REGEX_FILE_ERROR_KEY, "")
    if file_error:
        st.warning(file_error)
    file_display = st.session_state.get(FILTER_REGEX_FILE_DISPLAY_KEY)
    if file_display:
        count = len(st.session_state.get(FILTER_REGEX_PATTERNS_KEY, []))
        suffix = "" if count == 1 else "s"
        file_cols = st.columns([0.9, 0.1], vertical_alignment="center")
        file_cols[0].info(f"Active regex list: {file_display} ({count} pattern{suffix}).")
        if file_cols[1].button(
            "",
            icon=":material/close:",
            help="Clear regex list",
            width="stretch",
            key="clear_regex_list_button",
            on_click=_clear_regex_file_state,
        ):
            st.rerun()

    st.divider()
    st.markdown("#### Status filters")
    st.multiselect(
        "Global status",
        options=status_options,
        format_func=status_text,
        key=FILTER_DIALOG_STATUSES_KEY,
        on_change=_sync_filter_statuses,
    )
    missing_cols = st.columns(3)
    missing_cols[0].checkbox("Missing HD", key=FILTER_DIALOG_MISSING_HD_KEY, on_change=_sync_filter_flags)
    missing_cols[1].checkbox("Missing DV", key=FILTER_DIALOG_MISSING_DV_KEY, on_change=_sync_filter_flags)
    missing_cols[2].checkbox("Missing AE", key=FILTER_DIALOG_MISSING_AE_KEY, on_change=_sync_filter_flags)

    actions = st.columns(2)
    if actions[0].button(
        "Clear",
        icon=":material/filter_alt_off:",
        width="stretch",
        on_click=_clear_filter_state,
    ):
        st.rerun()
    if actions[1].button("Apply", type="primary", icon=":material/check:", width="stretch"):
        st.rerun()


def _prepare_filter_dialog_defaults(status_options: list[str]) -> None:
    st.session_state.setdefault(FILTER_REGEX_KEY, "")
    st.session_state.setdefault(FILTER_REGEX_PATTERNS_KEY, [])
    st.session_state.setdefault(FILTER_STATUSES_KEY, [])
    st.session_state.setdefault(FILTER_MISSING_HD_KEY, False)
    st.session_state.setdefault(FILTER_MISSING_DV_KEY, False)
    st.session_state.setdefault(FILTER_MISSING_AE_KEY, False)

    valid_statuses = [
        status
        for status in st.session_state.get(FILTER_STATUSES_KEY, [])
        if status in status_options
    ]
    st.session_state[FILTER_STATUSES_KEY] = valid_statuses

    st.session_state.setdefault(FILTER_DIALOG_REGEX_KEY, st.session_state[FILTER_REGEX_KEY])
    dialog_statuses = [
        status
        for status in st.session_state.get(FILTER_DIALOG_STATUSES_KEY, valid_statuses)
        if status in status_options
    ]
    st.session_state[FILTER_DIALOG_STATUSES_KEY] = dialog_statuses
    st.session_state.setdefault(FILTER_DIALOG_MISSING_HD_KEY, st.session_state[FILTER_MISSING_HD_KEY])
    st.session_state.setdefault(FILTER_DIALOG_MISSING_DV_KEY, st.session_state[FILTER_MISSING_DV_KEY])
    st.session_state.setdefault(FILTER_DIALOG_MISSING_AE_KEY, st.session_state[FILTER_MISSING_AE_KEY])


def _sync_filter_regex() -> None:
    st.session_state[FILTER_REGEX_KEY] = str(st.session_state.get(FILTER_DIALOG_REGEX_KEY, ""))


def _remember_regex_file_text(file_name: str, display_path: str, text: str) -> None:
    st.session_state[FILTER_REGEX_FILE_NAME_KEY] = file_name
    st.session_state[FILTER_REGEX_FILE_DISPLAY_KEY] = display_path or file_name
    st.session_state[FILTER_REGEX_FILE_TEXT_KEY] = text
    st.session_state[FILTER_REGEX_PATTERNS_KEY] = _regex_patterns_from_text(text)


def _browse_regex_filter_file() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        dialog_root = tk.Tk()
        dialog_root.withdraw()
        dialog_root.attributes("-topmost", True)
        dialog_root.update()
        selected = filedialog.askopenfilename(
            title="Select regex list",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
    except Exception as exc:
        st.session_state[FILTER_REGEX_FILE_ERROR_KEY] = f"Unable to open file picker: {exc}"
        return
    finally:
        if "dialog_root" in locals():
            dialog_root.destroy()

    if not selected:
        return

    path = Path(selected)
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        st.session_state[FILTER_REGEX_FILE_ERROR_KEY] = f"Unable to read regex list: {exc}"
        return

    _remember_regex_file_text(path.name, str(path), text)


def _sync_filter_statuses() -> None:
    st.session_state[FILTER_STATUSES_KEY] = list(st.session_state.get(FILTER_DIALOG_STATUSES_KEY, []))


def _sync_filter_flags() -> None:
    st.session_state[FILTER_MISSING_HD_KEY] = bool(st.session_state.get(FILTER_DIALOG_MISSING_HD_KEY, False))
    st.session_state[FILTER_MISSING_DV_KEY] = bool(st.session_state.get(FILTER_DIALOG_MISSING_DV_KEY, False))
    st.session_state[FILTER_MISSING_AE_KEY] = bool(st.session_state.get(FILTER_DIALOG_MISSING_AE_KEY, False))


def _clear_filter_state() -> None:
    st.session_state[FILTER_REGEX_KEY] = ""
    _clear_regex_file_state()
    st.session_state[FILTER_STATUSES_KEY] = []
    st.session_state[FILTER_MISSING_HD_KEY] = False
    st.session_state[FILTER_MISSING_DV_KEY] = False
    st.session_state[FILTER_MISSING_AE_KEY] = False
    st.session_state[FILTER_DIALOG_REGEX_KEY] = ""
    st.session_state[FILTER_DIALOG_STATUSES_KEY] = []
    st.session_state[FILTER_DIALOG_MISSING_HD_KEY] = False
    st.session_state[FILTER_DIALOG_MISSING_DV_KEY] = False
    st.session_state[FILTER_DIALOG_MISSING_AE_KEY] = False


def _clear_regex_file_state() -> None:
    st.session_state[FILTER_REGEX_PATTERNS_KEY] = []
    st.session_state.pop(FILTER_REGEX_FILE_NAME_KEY, None)
    st.session_state.pop(FILTER_REGEX_FILE_DISPLAY_KEY, None)
    st.session_state.pop(FILTER_REGEX_FILE_TEXT_KEY, None)


def _filter_acquisition_regex(frame: pd.DataFrame, pattern: str) -> pd.DataFrame:
    try:
        matcher = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        st.warning(f"Invalid acquisition regex: {exc}")
        return frame.iloc[0:0]

    mask = frame["acquisition"].astype(str).map(lambda value: bool(matcher.search(value)))
    return frame[mask]


def _filter_acquisition_regex_list(frame: pd.DataFrame, patterns: list[str]) -> pd.DataFrame:
    compiled = []
    invalid = 0
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern, flags=re.IGNORECASE))
        except re.error:
            invalid += 1

    if invalid:
        suffix = "" if invalid == 1 else "s"
        st.caption(f"{invalid} invalid regex pattern{suffix} ignored.")
    if not compiled:
        return frame.iloc[0:0]

    mask = frame["acquisition"].astype(str).map(
        lambda value: any(pattern.search(value) for pattern in compiled)
    )
    return frame[mask]


def _regex_patterns_from_text(text: str) -> list[str]:
    return [
        line
        for raw_line in text.splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    ]


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
    _render_export_button(cols[0], scan_result, filtered)


def _render_export_button(container, scan_result, filtered: pd.DataFrame) -> None:
    zip_bytes = build_missing_holo_lists_zip(
        scan_result.acquisitions,
        filtered,
        scan_result.all_holo_files,
    )

    container.download_button(
        "Explort lists",
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
