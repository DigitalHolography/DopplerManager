from __future__ import annotations

import html
from pathlib import Path
from typing import List, Optional

import pandas as pd
import streamlit as st

from doppler_manager.models import AcquisitionResult, FileRef, STAGE_LABELS, STAGE_ORDER
from doppler_manager.ui.formatting import format_size, format_timestamp, status_text
from doppler_manager.ui.media import render_media_preview


def render_acquisition_detail(acquisitions: List[AcquisitionResult], filtered: pd.DataFrame) -> None:
    filtered_ids = filtered["acquisition"].tolist()
    if not filtered_ids:
        st.warning("No acquisition matches the active filters.")
        return

    by_id = {acquisition.acquisition_id: acquisition for acquisition in acquisitions}
    header_cols = st.columns([2.2, 5])
    selected_id = header_cols[0].selectbox("Acquisition", filtered_ids)
    acquisition = by_id[selected_id]

    _render_status_line(header_cols[1], acquisition)

    with st.container(border=True, key="detail_main_tabs"):
        tabs = st.tabs(["Parameters", "Versions", "Media Preview"])
        with tabs[0]:
            render_parameters(acquisition)
        with tabs[1]:
            render_versions(acquisition)
        with tabs[2]:
            render_media_preview(acquisition)


def render_parameters(acquisition: AcquisitionResult) -> None:
    nav_col, content_col = st.columns([0.72, 5.6], vertical_alignment="top")
    stage = _render_stage_toolbar(nav_col, f"params-stage-{acquisition.acquisition_id}")
    with content_col:
        files = acquisition.stages[stage].params_files
        _render_text_files(
            files,
            "No parameter files were indexed for this stage.",
            language="json",
            key_prefix=f"params-{acquisition.acquisition_id}-{stage}",
        )


def render_versions(acquisition: AcquisitionResult) -> None:
    nav_col, content_col = st.columns([0.72, 5.6], vertical_alignment="top")
    stage = _render_stage_toolbar(nav_col, f"versions-stage-{acquisition.acquisition_id}")
    with content_col:
        result = acquisition.stages[stage]
        if not result.version_files:
            st.info("No version files were indexed for this stage.")
            return

        selected = st.selectbox(
            "Version file",
            result.version_files,
            format_func=lambda file_ref: file_ref.name,
            key=f"version-select-{acquisition.acquisition_id}-{stage}",
        )
        _render_file_meta(selected)
        st.code(result.versions.get(selected.name, "(content not loaded)") or "(empty)", language="text")


def _render_stage_toolbar(container, key: str) -> str:
    st.session_state.setdefault(key, STAGE_ORDER[0])
    with container.container(border=True, key=f"{key}-toolbar"):
        for stage in STAGE_ORDER:
            selected = st.session_state[key] == stage
            st.button(
                stage.upper(),
                key=f"{key}-{stage}",
                help=STAGE_LABELS[stage],
                type="primary" if selected else "secondary",
                width="stretch",
                on_click=_select_stage,
                args=(key, stage),
            )
    return str(st.session_state[key])


def _select_stage(key: str, stage: str) -> None:
    st.session_state[key] = stage


def _render_status_line(container, acquisition: AcquisitionResult) -> None:
    stage_chips = [
        _stage_chip(stage.upper(), acquisition.stages[stage].status)
        for stage in STAGE_ORDER
    ]
    container.markdown(
        f'<div class="dm-detail-stage-chips">{"".join(stage_chips)}</div>',
        unsafe_allow_html=True,
    )


def _stage_chip(label: str, status: str) -> str:
    state = _stage_chip_state(status)
    return (
        f'<span class="dm-stage-chip dm-stage-chip-{state}" title="{html.escape(status_text(status), quote=True)}">'
        f'<span class="dm-stage-chip-icon">{_stage_chip_icon(state)}</span>'
        f"<strong>{html.escape(label)}</strong>"
        "</span>"
    )


def _stage_chip_state(status: str) -> str:
    if status == "complete":
        return "complete"
    if status == "error":
        return "error"
    return "review"


def _stage_chip_icon(state: str) -> str:
    if state == "complete":
        return "&#10003;"
    if state == "error":
        return "&times;"
    return "!"


def _render_text_files(files: List[FileRef], empty_message: str, language: str, key_prefix: str) -> None:
    if not files:
        st.info(empty_message)
        return

    selected = st.selectbox("File", files, format_func=lambda file_ref: file_ref.name, key=f"{key_prefix}-file")
    _render_file_meta(selected)
    content = _read_small_text(Path(selected.path), max_bytes=64_000)
    if content is None:
        st.warning("This file is too large or cannot be read safely from the app.")
    else:
        st.code(content or "(empty)", language=language)


def _render_file_meta(file_ref: FileRef) -> None:
    cols = st.columns([1, 1, 3])
    cols[0].caption(f"Size: {format_size(file_ref.size)}")
    cols[1].caption(f"Modified: {format_timestamp(file_ref.modified_ts)}")
    cols[2].caption(file_ref.path)


def _read_small_text(path: Path, max_bytes: int) -> Optional[str]:
    try:
        if path.stat().st_size > max_bytes:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
