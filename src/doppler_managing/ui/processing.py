from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from doppler_managing.models import AcquisitionResult, ScanResult
from doppler_managing.processing import (
    PROCESSING_STAGES,
    PROGRESS_LOG_PREFIX,
    available_pipelines_for_stage,
    build_processing_jobs,
    default_pipelines_for_stage,
    discover_holodoppler_settings,
    holodoppler_settings_from_path,
    missing_default_processing_tools,
    needed_processing_stages,
    preferred_holodoppler_settings,
    run_processing_jobs,
)
from doppler_managing.scanner import ScanOptions


STAGE_OPTIONS = {
    "hd": "Holodoppler",
    "dv": "DopplerView",
    "ef": "EyeFlow",
    "ae": "AngioEye",
}

LOG_LIMIT = 700


def render_processing_tab(
    scan_result: ScanResult,
    filtered: pd.DataFrame,
    root_input: str,
    scan_options: ScanOptions,
    refresh_scan,
) -> None:
    st.subheader("Processing")

    filtered_ids = filtered["acquisition"].tolist()
    if not filtered_ids:
        st.warning("No acquisition matches the active filters.")
        _render_previous_log()
        return

    acquisitions_by_id = {
        acquisition.acquisition_id: acquisition
        for acquisition in scan_result.acquisitions
    }
    selected_ids = st.multiselect(
        "Acquisitions",
        filtered_ids,
        default=filtered_ids if len(filtered_ids) == 1 else [],
    )
    selected_stages = st.multiselect(
        "Run or rerun",
        list(PROCESSING_STAGES),
        format_func=lambda stage: STAGE_OPTIONS[stage],
    )
    only_incomplete = st.checkbox("Only missing or needs review", value=False)
    selected_eyeflow_pipelines = _render_pipeline_selection("ef", selected_stages)
    selected_angioeye_pipelines = _render_pipeline_selection("ae", selected_stages)

    selected_acquisitions = [
        acquisitions_by_id[acquisition_id] for acquisition_id in selected_ids
    ]
    runnable_stages = needed_processing_stages(
        selected_acquisitions,
        selected_stages,
        only_incomplete=only_incomplete,
    )

    hd_settings = _render_hd_settings(root_input, runnable_stages)
    missing_tools = missing_default_processing_tools(runnable_stages)
    if missing_tools:
        missing_labels = ", ".join(STAGE_OPTIONS[stage] for stage in missing_tools)
        st.warning(
            f"Missing processing package(s): {missing_labels}. "
            "Run `uv sync --extra processing`, then restart the app."
        )
    log_placeholder = st.empty()
    _render_previous_log(log_placeholder)

    can_run = bool(
        selected_ids
        and selected_stages
        and runnable_stages
        and not missing_tools
        and ("hd" not in runnable_stages or hd_settings is not None)
        and ("ef" not in runnable_stages or selected_eyeflow_pipelines)
        and ("ae" not in runnable_stages or selected_angioeye_pipelines)
    )
    if st.button("Run Processing", type="primary", disabled=not can_run, width="stretch"):
        try:
            jobs = build_processing_jobs(
                selected_acquisitions,
                selected_ids,
                selected_stages,
                hd_settings_path=hd_settings,
                cache_dir=Path(".doppler_cache"),
                only_incomplete=only_incomplete,
                eyeflow_pipelines=selected_eyeflow_pipelines,
                angioeye_pipelines=selected_angioeye_pipelines,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return
        if not jobs:
            st.info("No selected stage needs processing.")
            return

        _run_jobs_and_refresh(
            jobs=jobs,
            root_input=root_input,
            scan_options=scan_options,
            refresh_scan=refresh_scan,
            log_placeholder=log_placeholder,
        )

    if not can_run:
        if only_incomplete and selected_ids and selected_stages and not runnable_stages:
            st.caption("Selected stages are already complete for the selected acquisitions.")
        else:
            st.caption(
                "Select at least one acquisition and one stage. HD also needs a settings JSON file."
            )


def _render_pipeline_selection(
    stage: str,
    selected_stages: list[str],
) -> Optional[tuple[str, ...]]:
    if stage not in selected_stages:
        return None

    available = list(available_pipelines_for_stage(stage))
    defaults = [
        pipeline
        for pipeline in default_pipelines_for_stage(stage)
        if pipeline in available
    ]
    selected = st.multiselect(
        f"{STAGE_OPTIONS[stage]} pipelines",
        available,
        default=defaults,
        key=f"{stage}_pipelines",
    )
    if not selected:
        st.warning(f"Select at least one {STAGE_OPTIONS[stage]} pipeline.")
    return tuple(selected)


def _render_hd_settings(root_input: str, selected_stages: list[str]) -> Optional[Path]:
    if "hd" not in selected_stages:
        return None

    discovered = discover_holodoppler_settings(root_input)
    preferred = preferred_holodoppler_settings(discovered)
    default_value = str(preferred.parent if preferred else "")
    settings_input = st.text_input(
        "HoloDoppler settings",
        value=st.session_state.get("hd_settings_input", default_value),
        placeholder=r"D:\path\to\HoloDopplerPython\parameters or a JSON file",
    )
    st.session_state.hd_settings_input = settings_input

    options = holodoppler_settings_from_path(settings_input)
    if not options:
        st.warning(
            "Point HoloDoppler settings to a folder containing JSON settings, or to one JSON file."
        )
        return None

    default_index = _preferred_index(options)
    selected = st.selectbox(
        "Settings file",
        options,
        index=default_index,
        format_func=lambda path: path.name,
    )
    return selected


def _preferred_index(options: list[Path]) -> int:
    preferred = preferred_holodoppler_settings(options)
    if preferred is None:
        return 0
    try:
        return options.index(preferred)
    except ValueError:
        return 0


def _run_jobs_and_refresh(
    *,
    jobs,
    root_input: str,
    scan_options: ScanOptions,
    refresh_scan,
    log_placeholder,
) -> None:
    log_lines = deque(maxlen=LOG_LIMIT)
    last_log_was_progress = False
    st.session_state.processing_log = []

    def append_log(line: str) -> None:
        nonlocal last_log_was_progress
        is_progress_update = line.startswith(PROGRESS_LOG_PREFIX)
        if is_progress_update:
            line = line[len(PROGRESS_LOG_PREFIX):]
            if last_log_was_progress and log_lines:
                log_lines[-1] = line
            else:
                log_lines.append(line)
            last_log_was_progress = True
        else:
            log_lines.append(line)
            last_log_was_progress = False
        st.session_state.processing_log = list(log_lines)
        log_placeholder.code("\n".join(log_lines), language="text")

    results = run_processing_jobs(jobs, append_log)
    failures = [result for result in results if not result.succeeded]

    append_log("[SCAN] Refreshing acquisition index...")
    st.session_state.scan_result = refresh_scan(
        root_input,
        scan_options.max_depth,
        scan_options.max_entries,
        scan_options.preview_limit_per_stage,
        scan_options.read_versions,
        _holo_filter_cache_key(scan_options),
    )
    append_log("[SCAN] Refresh complete.")

    if failures:
        st.session_state.processing_summary = (
            f"Processing finished with {len(failures)} failed job(s)."
        )
    else:
        st.session_state.processing_summary = "Processing finished successfully."
    st.rerun()


def _render_previous_log(log_placeholder=None) -> None:
    summary = st.session_state.get("processing_summary")
    if summary:
        if "failed" in summary:
            st.warning(summary)
        else:
            st.success(summary)

    log_lines = st.session_state.get("processing_log", [])
    if not log_lines:
        return
    target = log_placeholder if log_placeholder is not None else st
    target.code("\n".join(log_lines), language="text")


def _holo_filter_cache_key(scan_options: ScanOptions) -> tuple[str, ...] | None:
    if scan_options.holo_filter_ids is None:
        return None
    return tuple(sorted(scan_options.holo_filter_ids))
