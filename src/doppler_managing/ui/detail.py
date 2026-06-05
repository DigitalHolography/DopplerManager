from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd
import streamlit as st

from doppler_managing.models import AcquisitionResult, FileRef, STAGE_LABELS, STAGE_ORDER
from doppler_managing.ui.formatting import format_size, format_timestamp, status_badge
from doppler_managing.ui.media import render_media_preview


def render_acquisition_detail(acquisitions: List[AcquisitionResult], filtered: pd.DataFrame) -> None:
    filtered_ids = filtered["acquisition"].tolist()
    if not filtered_ids:
        st.warning("No acquisition matches the active filters.")
        return

    by_id = {acquisition.acquisition_id: acquisition for acquisition in acquisitions}
    selected_id = st.selectbox("Acquisition", filtered_ids)
    acquisition = by_id[selected_id]

    _render_status_line(acquisition)

    tabs = st.tabs(["Parameters", "Versions", "Media Preview"])
    with tabs[0]:
        render_parameters(acquisition)
    with tabs[1]:
        render_versions(acquisition)
    with tabs[2]:
        render_media_preview(acquisition)


def render_parameters(acquisition: AcquisitionResult) -> None:
    tabs = st.tabs([STAGE_LABELS[stage] for stage in STAGE_ORDER])
    for tab, stage in zip(tabs, STAGE_ORDER):
        with tab:
            files = acquisition.stages[stage].params_files
            _render_text_files(
                files,
                "No parameter files were indexed for this stage.",
                language="json",
                key_prefix=f"params-{acquisition.acquisition_id}-{stage}",
            )


def render_versions(acquisition: AcquisitionResult) -> None:
    tabs = st.tabs([STAGE_LABELS[stage] for stage in STAGE_ORDER])
    for tab, stage in zip(tabs, STAGE_ORDER):
        with tab:
            result = acquisition.stages[stage]
            if not result.version_files:
                st.info("No version files were indexed for this stage.")
                continue

            selected = st.selectbox(
                "Version file",
                result.version_files,
                format_func=lambda file_ref: file_ref.name,
                key=f"version-select-{acquisition.acquisition_id}-{stage}",
            )
            _render_file_meta(selected)
            st.code(result.versions.get(selected.name, "(content not loaded)") or "(empty)", language="text")


def _render_status_line(acquisition: AcquisitionResult) -> None:
    stage_cols = st.columns(5)
    stage_cols[0].markdown(status_badge("Global", acquisition.status), unsafe_allow_html=True)
    for index, stage in enumerate(STAGE_ORDER, start=1):
        stage_result = acquisition.stages[stage]
        stage_cols[index].markdown(status_badge(stage.upper(), stage_result.status), unsafe_allow_html=True)


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
