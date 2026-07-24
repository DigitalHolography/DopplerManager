from __future__ import annotations

import html
from collections import deque
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from doppler_manager.models import AcquisitionResult, ScanResult
from doppler_manager.processing import (
    PROCESSING_STAGES,
    PROGRESS_LOG_PREFIX,
    available_pipelines_for_stage,
    build_processing_jobs,
    bundled_holodoppler_settings_dir,
    default_pipelines_for_stage,
    discover_angioeye_postprocesses,
    holodoppler_settings_from_path,
    proposed_angioeye_postprocesses,
    missing_default_processing_tools,
    needed_processing_stages,
    preferred_holodoppler_settings,
    run_processing_jobs,
)
from doppler_manager.scan import ScanOptions


STAGE_OPTIONS = {
    "hd": "Holodoppler",
    "dv": "DopplerView",
    "ef": "EyeFlow",
    "ae": "AngioEye",
}

LOG_LIMIT = 700
CUSTOM_HOLODOPPLER_SETTINGS = "Upload custom settings..."
PROCESSING_LOG_ENTRIES_KEY = "processing_log_entries"
PROCESSING_LOG_ALL_FILES = "All files"
PROCESSING_LOG_ALL_APPS = "All apps"
PROCESSING_LOG_MANAGER_APP = "DopplerManager"


@st.cache_resource(show_spinner=False)
def _cached_angioeye_postprocesses():
    """Keep decorator discovery cached across Streamlit reruns."""

    return discover_angioeye_postprocesses()


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
        _render_processing_summary()
        if _has_processing_output():
            _render_processing_log_view([], [])
        return

    acquisitions_by_id = {
        acquisition.acquisition_id: acquisition
        for acquisition in scan_result.acquisitions
    }
    processing_cols = st.columns([0.95, 1.35], vertical_alignment="top")
    with processing_cols[0]:
        selected_ids = _render_acquisition_selection(st, filtered_ids)
        selected_stages, only_incomplete = _render_processing_scope(st)

    selected_acquisitions = [
        acquisitions_by_id[acquisition_id] for acquisition_id in selected_ids
    ]

    runnable_stages = needed_processing_stages(
        selected_acquisitions,
        selected_stages,
        only_incomplete=only_incomplete,
    )
    (
        selected_eyeflow_pipelines,
        selected_angioeye_pipelines,
        selected_angioeye_postprocesses,
        hd_settings,
        missing_tools,
    ) = _render_processing_options(
        processing_cols[1],
        selected_acquisitions,
        selected_stages,
        only_incomplete,
        runnable_stages,
        root_input,
    )

    can_run = bool(
        selected_ids
        and not missing_tools
        and (runnable_stages or selected_angioeye_postprocesses)
        and ("hd" not in runnable_stages or hd_settings is not None)
        and ("ef" not in runnable_stages or selected_eyeflow_pipelines)
        and ("ae" not in runnable_stages or selected_angioeye_pipelines)
    )
    no_incomplete_selected_scope = bool(
        only_incomplete
        and selected_ids
        and selected_stages
        and not runnable_stages
        and not selected_angioeye_postprocesses
    )
    run_button_help = (
        "No files need to be processed: no selected acquisition is missing or needs "
        "review for the chosen processing method(s)."
        if no_incomplete_selected_scope
        else None
    )
    if not can_run:
        if no_incomplete_selected_scope:
            st.caption("Selected stages are already complete for the selected acquisitions.")
        else:
            st.caption(
                "Select at least one acquisition and one stage or postprocess. "
                "HD also needs a settings JSON file."
            )
    _render_processing_summary()
    if no_incomplete_selected_scope:
        _render_disabled_run_button(run_button_help)
        run_clicked = False
    else:
        run_clicked = st.button(
            "Run Processing",
            type="primary",
            disabled=not can_run,
            width="stretch",
            key="run_processing_button",
        )

    if run_clicked:
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
                angioeye_postprocesses=selected_angioeye_postprocesses,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return
        if not jobs:
            st.info("No selected stage needs processing.")
            return

        selected_log_file, selected_log_app, log_placeholder = _render_processing_log_view(
            selected_ids,
            selected_stages,
        )
        _run_jobs_and_refresh(
            jobs=jobs,
            root_input=root_input,
            scan_options=scan_options,
            refresh_scan=refresh_scan,
            log_placeholder=log_placeholder,
            selected_file_ids=selected_ids,
            file_filter=selected_log_file,
            app_filter=selected_log_app,
            allowed_file_ids=selected_ids,
            allowed_apps=_processing_app_labels(selected_stages),
        )
    elif _has_processing_output():
        _render_processing_log_view(selected_ids, selected_stages)


def _render_acquisition_selection(container, filtered_ids: list[str]) -> list[str]:
    with container.container(border=True, key="processing_acquisition_selection"):
        st.markdown("#### Acquisitions")
        selected_ids = st.multiselect(
            "Acquisitions",
            filtered_ids,
            default=filtered_ids if len(filtered_ids) == 1 else [],
            label_visibility="collapsed",
        )
        st.caption(f"{len(selected_ids)} of {len(filtered_ids)} selected")
        return selected_ids


def _render_processing_scope(container) -> tuple[list[str], bool]:
    with container.container(border=True, key="processing_stage_selection"):
        st.markdown("#### Processing scope")
        return _render_stage_checklist(st)


def _render_disabled_run_button(help_text: str | None) -> None:
    title = html.escape(help_text or "", quote=True)
    st.markdown(
        (
            f'<div class="dm-disabled-run-button" title="{title}" '
            'role="button" aria-disabled="true">Run Processing</div>'
        ),
        unsafe_allow_html=True,
    )


def _render_processing_options(
    container,
    selected_acquisitions: list[AcquisitionResult],
    selected_stages: list[str],
    only_incomplete: bool,
    runnable_stages: list[str],
    root_input: str,
) -> tuple[
    Optional[tuple[str, ...]],
    Optional[tuple[str, ...]],
    tuple[str, ...],
    Optional[Path],
    list[str],
]:
    with container.container(border=True, key="processing_options"):
        st.markdown("#### Options")
        if not selected_acquisitions:
            _clear_processing_option_state()
            st.caption(
                "Select at least one acquisition to configure processing options."
            )
            return None, None, (), None, []

        if only_incomplete and selected_acquisitions and not runnable_stages:
            st.caption("Selected acquisitions already satisfy the current scope.")
        pipeline_selection_stages = selected_stages
        hd_settings = (
            _render_hd_settings(root_input, pipeline_selection_stages)
            if selected_stages
            else None
        )
        selected_eyeflow_pipelines = (
            _render_pipeline_selection("ef", pipeline_selection_stages)
            if selected_stages
            else None
        )
        selected_angioeye_pipelines = (
            _render_pipeline_selection("ae", pipeline_selection_stages)
            if selected_stages
            else None
        )
        selected_angioeye_postprocesses = (
            _render_postprocess_selection(
                selected_acquisitions,
                selected_angioeye_pipelines,
            )
            if "ae" in selected_stages
            else ()
        )
        tool_stages = list(runnable_stages)
        if selected_angioeye_postprocesses and "ae" not in tool_stages:
            tool_stages.append("ae")
        missing_tools = missing_default_processing_tools(tool_stages)
        if missing_tools:
            missing_labels = ", ".join(STAGE_OPTIONS[stage] for stage in missing_tools)
            st.warning(
                f"Missing processing package(s): {missing_labels}. "
                "Run `uv sync --extra processing`, then restart the app."
            )
        if not any(stage in pipeline_selection_stages for stage in ("hd", "ef", "ae")):
            if not selected_angioeye_postprocesses:
                st.caption("No additional options for this scope.")
        return (
            selected_eyeflow_pipelines,
            selected_angioeye_pipelines,
            selected_angioeye_postprocesses,
            hd_settings,
            missing_tools,
        )


def _clear_processing_option_state() -> None:
    """Drop selections that should not survive an empty acquisition scope."""

    for key in (
        "ef_pipelines",
        "ae_pipelines",
        "angioeye_postprocesses",
        "angioeye_postprocesses_loading",
        "hd_settings_upload",
    ):
        st.session_state.pop(key, None)


def _render_postprocess_selection(
    selected_acquisitions: list[AcquisitionResult],
    selected_angioeye_pipelines: Optional[tuple[str, ...]],
) -> tuple[str, ...]:
    if not selected_acquisitions:
        st.caption("Select at least one acquisition to discover compatible postprocesses.")
        return ()

    loading_dropdown = st.empty()
    loading_dropdown.multiselect(
        "AngioEye postprocesses",
        ["Discovering compatible postprocesses..."],
        default=[],
        disabled=True,
        key="angioeye_postprocesses_loading",
    )
    with st.spinner("Discovering compatible AngioEye postprocesses..."):
        proposed = proposed_angioeye_postprocesses(
            _cached_angioeye_postprocesses(),
            len(selected_acquisitions),
            selected_pipelines=selected_angioeye_pipelines,
        )
    if not proposed:
        loading_dropdown.empty()
        st.caption(
            "No AngioEye postprocess supports this selection size and pipeline "
            "selection. "
            "ZIP postprocess mode is not available from the acquisition scan."
        )
        return ()

    options = [postprocess.name for postprocess in proposed]
    selected = loading_dropdown.multiselect(
        "AngioEye postprocesses",
        options,
        default=[],
        key="angioeye_postprocesses",
        help="One acquisition uses single_file; multiple acquisitions use file_batch.",
    )
    return tuple(selected)


def _render_stage_checklist(container) -> tuple[list[str], bool]:
    selected_stages: list[str] = []
    for stage in PROCESSING_STAGES:
        selected = container.checkbox(
            STAGE_OPTIONS[stage],
            key=f"processing_stage_{stage}",
        )
        if selected:
            selected_stages.append(stage)
    only_incomplete = container.checkbox(
        "Only missing or needs review",
        value=False,
        key="processing_only_incomplete",
    )

    return selected_stages, only_incomplete


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


def _render_hd_settings(_root_input: str, selected_stages: list[str]) -> Optional[Path]:
    if "hd" not in selected_stages:
        return None

    options = holodoppler_settings_from_path(bundled_holodoppler_settings_dir())
    if not options:
        st.warning("No bundled HoloDoppler settings were found.")
        return _render_custom_hd_settings_upload()

    default_index = _preferred_index(options)
    select_options: list[Path | str] = [*options, CUSTOM_HOLODOPPLER_SETTINGS]
    selected = st.selectbox(
        "HoloDoppler settings",
        select_options,
        index=default_index,
        format_func=_format_hd_settings_option,
    )
    if selected == CUSTOM_HOLODOPPLER_SETTINGS:
        return _render_custom_hd_settings_upload()
    return selected if isinstance(selected, Path) else None


def _format_hd_settings_option(option: Path | str) -> str:
    if isinstance(option, Path):
        return option.name
    return option


def _render_custom_hd_settings_upload() -> Optional[Path]:
    uploaded = st.file_uploader(
        "Upload HoloDoppler settings",
        type=["json", "yaml", "yml"],
        key="hd_settings_upload",
    )
    if uploaded is None:
        st.warning("Upload a HoloDoppler settings file.")
        return None

    safe_name = Path(uploaded.name).name or "uploaded_holodoppler_settings.yaml"
    target = Path(".doppler_cache") / "processing" / "holodoppler_settings" / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(uploaded.getvalue())
    return target


def _preferred_index(options: list[Path]) -> int:
    preferred = preferred_holodoppler_settings(options)
    if preferred is None:
        return 0
    try:
        return options.index(preferred)
    except ValueError:
        return 0


def _render_processing_summary() -> None:
    summary = st.session_state.get("processing_summary")
    if not summary:
        return
    if "failed" in summary:
        st.warning(summary)
    else:
        st.success(summary)


def _has_processing_output() -> bool:
    return bool(
        st.session_state.get(PROCESSING_LOG_ENTRIES_KEY)
        or st.session_state.get("processing_log")
        or st.session_state.get("processing_summary")
    )


def _processing_app_labels(stages: list[str]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(_processing_app_label(stage) for stage in stages)
    )


def _render_processing_log_view(
    selected_file_ids: list[str],
    selected_stages: list[str],
) -> tuple[str, str, object]:
    selected_log_file, selected_log_app = _render_log_filters(
        selected_file_ids,
        selected_stages,
    )
    st.markdown("#### Log")
    log_placeholder = st.empty()
    _render_previous_log(
        log_placeholder,
        file_filter=selected_log_file,
        app_filter=selected_log_app,
        allowed_file_ids=selected_file_ids,
        allowed_apps=_processing_app_labels(selected_stages),
    )
    return selected_log_file, selected_log_app, log_placeholder


def _render_log_filters(
    selected_file_ids: list[str],
    selected_stages: list[str],
) -> tuple[str, str]:
    file_options = sorted(dict.fromkeys(str(file_id) for file_id in selected_file_ids))
    app_options = list(_processing_app_labels(selected_stages))
    file_options = [PROCESSING_LOG_ALL_FILES, *file_options]
    app_options = [PROCESSING_LOG_ALL_APPS, *app_options]

    file_key = "processing_log_file_filter"
    app_key = "processing_log_app_filter"
    if st.session_state.get(file_key) not in file_options:
        st.session_state[file_key] = file_options[0]
    if st.session_state.get(app_key) not in app_options:
        st.session_state[app_key] = app_options[0]

    filter_cols = st.columns([1.4, 1])
    selected_file = filter_cols[0].selectbox(
        "File log to show",
        file_options,
        key=file_key,
    )
    selected_app = filter_cols[1].selectbox(
        "App",
        app_options,
        key=app_key,
    )
    return str(selected_file), str(selected_app)


def _processing_log_entries() -> list[dict[str, object]]:
    raw_entries = st.session_state.get(PROCESSING_LOG_ENTRIES_KEY)
    if isinstance(raw_entries, list) and raw_entries:
        entries: list[dict[str, object]] = []
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                continue
            files = raw_entry.get("files", ())
            if isinstance(files, str):
                files = (files,)
            elif isinstance(files, (list, tuple)):
                files = tuple(str(file_id) for file_id in files if file_id)
            else:
                files = ()
            entries.append(
                {
                    "line": str(raw_entry.get("line", "")),
                    "files": files,
                    "app": str(raw_entry.get("app", "")),
                }
            )
        if entries:
            return entries

    return [
        {
            "line": str(line),
            "files": (),
            "app": PROCESSING_LOG_MANAGER_APP,
        }
        for line in st.session_state.get("processing_log", [])
    ]


def _run_jobs_and_refresh(
    *,
    jobs,
    root_input: str,
    scan_options: ScanOptions,
    refresh_scan,
    log_placeholder,
    selected_file_ids: list[str],
    file_filter: str,
    app_filter: str,
    allowed_file_ids: list[str],
    allowed_apps: tuple[str, ...],
) -> None:
    log_lines = deque(maxlen=LOG_LIMIT)
    log_entries = deque(maxlen=LOG_LIMIT)
    last_log_was_progress = False
    current_file_ids: tuple[str, ...] = ()
    current_app = PROCESSING_LOG_MANAGER_APP
    st.session_state.processing_log = []
    st.session_state[PROCESSING_LOG_ENTRIES_KEY] = []

    def set_job_context(job) -> None:
        nonlocal current_file_ids, current_app
        if job.acquisition_id == "__angioeye_postprocess__":
            current_file_ids = tuple(selected_file_ids)
        else:
            current_file_ids = (job.acquisition_id,)
        current_app = _processing_app_label(job.stage)

    def append_log(line: str) -> None:
        nonlocal last_log_was_progress
        is_progress_update = line.startswith(PROGRESS_LOG_PREFIX)
        if is_progress_update:
            line = line[len(PROGRESS_LOG_PREFIX):]
            if last_log_was_progress and log_lines:
                log_lines[-1] = line
                log_entries[-1]["line"] = line
            else:
                log_lines.append(line)
                log_entries.append(
                    {
                        "line": line,
                        "files": current_file_ids,
                        "app": current_app,
                    }
                )
            last_log_was_progress = True
        else:
            log_lines.append(line)
            log_entries.append(
                {
                    "line": line,
                    "files": current_file_ids,
                    "app": current_app,
                }
            )
            last_log_was_progress = False
        st.session_state.processing_log = list(log_lines)
        st.session_state[PROCESSING_LOG_ENTRIES_KEY] = list(log_entries)
        _render_previous_log(
            log_placeholder,
            file_filter=file_filter,
            app_filter=app_filter,
            allowed_file_ids=allowed_file_ids,
            allowed_apps=allowed_apps,
        )

    results = run_processing_jobs(jobs, append_log, on_job=set_job_context)
    failures = [result for result in results if not result.succeeded]

    current_file_ids = ()
    current_app = PROCESSING_LOG_MANAGER_APP
    append_log("[SCAN] Refreshing acquisition index...")
    st.session_state.scan_result = refresh_scan(root_input, scan_options)
    append_log("[SCAN] Refresh complete.")

    if failures:
        st.session_state.processing_summary = (
            f"Processing finished with {len(failures)} failed job(s)."
        )
    else:
        st.session_state.processing_summary = "Processing finished successfully."
    st.rerun()


def _processing_app_label(stage: str) -> str:
    if stage == "ae_postprocess":
        return STAGE_OPTIONS["ae"]
    return STAGE_OPTIONS.get(stage, stage)


def _render_previous_log(
    log_placeholder=None,
    *,
    file_filter: str = PROCESSING_LOG_ALL_FILES,
    app_filter: str = PROCESSING_LOG_ALL_APPS,
    allowed_file_ids: list[str] | None = None,
    allowed_apps: tuple[str, ...] | None = None,
) -> None:
    entries = _processing_log_entries()
    if not entries:
        return

    visible_entries = [
        entry
        for entry in entries
        if (
            allowed_file_ids is None
            or (
                allowed_file_ids
                and bool(set(entry["files"]).intersection(allowed_file_ids))
            )
        )
        and (
            allowed_apps is None
            or (
                allowed_apps
                and entry["app"] in allowed_apps
            )
        )
        and (
            file_filter == PROCESSING_LOG_ALL_FILES
            or file_filter in entry["files"]
        )
        and (
            app_filter == PROCESSING_LOG_ALL_APPS
            or app_filter == entry["app"]
        )
    ]
    target = log_placeholder if log_placeholder is not None else st
    if not visible_entries:
        target.caption("No log entries match the selected file and app.")
        return
    target.code(
        "\n".join(str(entry["line"]) for entry in visible_entries),
        language="text",
    )
