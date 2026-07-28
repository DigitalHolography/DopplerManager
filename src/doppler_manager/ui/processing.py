from __future__ import annotations

import html
import copy
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

from doppler_manager.models import AcquisitionResult, ScanResult
from doppler_manager.processing import (
    PROCESSING_STAGES,
    available_pipelines_for_stage,
    build_processing_jobs,
    bundled_holodoppler_settings_dir,
    default_pipelines_for_stage,
    discover_angioeye_postprocesses,
    discover_processing_pipelines,
    holodoppler_settings_from_path,
    proposed_angioeye_postprocesses,
    missing_default_processing_tools,
    needed_processing_stages,
    preferred_holodoppler_settings,
)
from doppler_manager.processing.execution.session import ProcessingRun
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
PROCESSING_RUN_KEY = "processing_run"
PROCESSING_RUN_CONTEXT_KEY = "processing_run_context"
PROCESSING_RUN_FINALIZED_KEY = "processing_run_finalized"
PROCESSING_CURRENT_SCAN_CONTEXT_KEY = "processing_current_scan_context"
PROCESSING_LOG_ALL_FILES = "All files"
PROCESSING_LOG_ALL_APPS = "All apps"
PROCESSING_LOG_MANAGER_APP = "DopplerManager"
PROCESSING_INFO_OPTIONS = {
    "EyeFlow pipelines": "ef",
    "AngioEye pipelines": "ae",
    "AngioEye postprocesses": "postprocesses",
}
INPUT_METHOD_LABELS = {
    "single_file": "single file",
    "file_batch": "file batch",
    "cohort_batch": "cohort batch",
    "zip_batch": "ZIP batch",
}


@st.cache_resource(show_spinner=False)
def _cached_angioeye_postprocesses() -> tuple[Any, ...]:
    """Keep decorator discovery cached across Streamlit reruns."""

    return discover_angioeye_postprocesses()


@st.cache_resource(show_spinner=False)
def _cached_processing_pipelines(stage: str) -> tuple[Any, ...]:
    """Keep decorator discovery cached across Streamlit reruns."""

    return discover_processing_pipelines(stage)


def _render_processing_run_contents() -> None:
    run = st.session_state.get(PROCESSING_RUN_KEY)
    if not isinstance(run, ProcessingRun):
        return

    snapshot = run.snapshot()
    selected_file, selected_app = _render_log_filters(
        list(run.selected_file_ids),
        [],
        allowed_apps=run.allowed_apps,
    )
    st.markdown("#### Log")
    log_placeholder = st.empty()
    _render_previous_log(
        log_placeholder,
        file_filter=selected_file,
        app_filter=selected_app,
        allowed_file_ids=list(run.selected_file_ids),
        allowed_apps=run.allowed_apps,
        entries=snapshot.log_entries,
    )

    if snapshot.status in {"pending", "running"}:
        st.info(
            "Processing is running. Changes to the controls above are saved for "
            "the next run."
        )
        return

    if _finalize_processing_run(run):
        st.rerun()


_render_processing_run_fragment = (
    st.fragment(run_every="1s")(_render_processing_run_contents)
    if hasattr(st, "fragment")
    else _render_processing_run_contents
)


def render_processing_tab(
    scan_result: ScanResult,
    filtered: pd.DataFrame,
    root_input: str,
    scan_options: ScanOptions,
    refresh_scan,
) -> None:
    st.subheader("Processing")
    st.session_state[PROCESSING_CURRENT_SCAN_CONTEXT_KEY] = _scan_context_key(
        root_input,
        scan_options,
    )
    processing_run = st.session_state.get(PROCESSING_RUN_KEY)

    filtered_ids = filtered["acquisition"].tolist()
    if not filtered_ids:
        st.warning("No acquisition matches the active filters.")
        if isinstance(processing_run, ProcessingRun):
            if st.session_state.get(PROCESSING_RUN_FINALIZED_KEY, False):
                _render_processing_summary()
            _render_processing_run_panel(processing_run)
        else:
            _render_processing_summary()
        if not isinstance(processing_run, ProcessingRun) and _has_processing_output():
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
    run_is_active = (
        isinstance(processing_run, ProcessingRun)
        and not bool(st.session_state.get(PROCESSING_RUN_FINALIZED_KEY, False))
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
            st.caption(
                "Selected stages are already complete for the selected acquisitions."
            )
        else:
            st.caption(
                "Select at least one acquisition and one stage or postprocess. "
                "HD also needs a settings JSON file."
            )
    if not run_is_active:
        _render_processing_summary()
    if no_incomplete_selected_scope:
        _render_disabled_run_button(run_button_help)
        run_clicked = False
    else:
        run_clicked = st.button(
            "Run Processing",
            type="primary",
            disabled=not can_run or run_is_active,
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

        processing_run = ProcessingRun(
            jobs,
            selected_file_ids=selected_ids,
            allowed_apps=_processing_app_labels(selected_stages),
            log_limit=LOG_LIMIT,
        )
        st.session_state[PROCESSING_RUN_KEY] = processing_run
        st.session_state[PROCESSING_RUN_CONTEXT_KEY] = (
            str(root_input),
            copy.deepcopy(scan_options),
            refresh_scan,
        )
        st.session_state[PROCESSING_RUN_FINALIZED_KEY] = False
        st.session_state.pop("processing_summary", None)
        st.session_state.processing_log = []
        st.session_state[PROCESSING_LOG_ENTRIES_KEY] = []
        processing_run.start()
        _render_processing_run_fragment()
    elif isinstance(processing_run, ProcessingRun):
        _render_processing_run_panel(processing_run)
    elif _has_processing_output():
        _render_processing_log_view(selected_ids, selected_stages)


def _render_processing_run_panel(run: ProcessingRun) -> None:
    if not st.session_state.get(PROCESSING_RUN_FINALIZED_KEY, False):
        _render_processing_run_fragment()
        return

    snapshot = run.snapshot()
    _render_processing_log_view(
        list(run.selected_file_ids),
        [],
        entries=snapshot.log_entries,
        allowed_file_ids=list(run.selected_file_ids),
        allowed_apps=run.allowed_apps,
    )


def _scan_context_key(root_input: str, scan_options: ScanOptions) -> tuple[object, ...]:
    return (
        str(root_input),
        int(scan_options.max_depth),
        int(scan_options.max_entries),
        int(scan_options.preview_limit_per_stage),
        bool(scan_options.read_versions),
        tuple(sorted(scan_options.holo_filter_ids or ())),
        tuple(scan_options.holo_filter_entries or ()),
    )


def _finalize_processing_run(run: ProcessingRun) -> bool:
    if not run.claim_completion():
        return False

    snapshot = run.snapshot()
    failures = [result for result in snapshot.results if not result.succeeded]
    if snapshot.error:
        summary = f"Processing failed: {snapshot.error}"
    elif failures:
        summary = f"Processing finished with {len(failures)} failed job(s)."
    else:
        summary = "Processing finished successfully."

    context = st.session_state.get(PROCESSING_RUN_CONTEXT_KEY)
    current_scan_context = st.session_state.get(PROCESSING_CURRENT_SCAN_CONTEXT_KEY)
    if isinstance(context, tuple) and len(context) == 3:
        original_root, original_options, refresh_scan = context
        if (
            current_scan_context
            == _scan_context_key(str(original_root), original_options)
        ):
            run.append_manager_log("[SCAN] Refreshing acquisition index...")
            try:
                st.session_state.scan_result = refresh_scan(
                    original_root,
                    original_options,
                )
            except Exception as exc:  # noqa: BLE001
                run.append_manager_log(f"[SCAN] Refresh failed: {exc}")
                summary += " Scan refresh failed."
            else:
                run.append_manager_log("[SCAN] Refresh complete.")

    snapshot = run.snapshot()
    st.session_state.processing_log = [
        str(entry["line"]) for entry in snapshot.log_entries
    ]
    st.session_state[PROCESSING_LOG_ENTRIES_KEY] = list(snapshot.log_entries)
    st.session_state.processing_summary = summary
    st.session_state[PROCESSING_RUN_FINALIZED_KEY] = True
    return True


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
        with st.container(
            horizontal=True,
            vertical_alignment="center",
            gap="small",
            key="processing_options_header",
        ):
            st.markdown(
                '<div class="dm-processing-options-heading">Options</div>',
                unsafe_allow_html=True,
            )
            help_clicked = st.button(
                "",
                icon=":material/help_outline:",
                help="Show pipeline and postprocess descriptions",
                type="tertiary",
                width="content",
                key="processing_options_info_button",
            )
        if help_clicked:
            _render_processing_info_dialog()
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
                "Run `scripts\\sync_processing.ps1`, then restart the app."
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
        "hd_settings_upload",
    ):
        st.session_state.pop(key, None)


@st.dialog(
    "Processing information",
    width="large",
    icon=":material/help_outline:",
    on_dismiss="rerun",
)
def _render_processing_info_dialog() -> None:
    selection_columns = st.columns(2)
    category = selection_columns[0].selectbox(
        "Information type",
        list(PROCESSING_INFO_OPTIONS),
        key="processing_info_category",
    )
    stage_or_postprocesses = PROCESSING_INFO_OPTIONS[category]

    if stage_or_postprocesses == "postprocesses":
        descriptors = tuple(
            descriptor
            for descriptor in _cached_angioeye_postprocesses()
            if descriptor.visibility != "hidden"
        )
        _render_processing_information(
            descriptors,
            empty_message=(
                "No AngioEye postprocesses were discovered. Install the optional "
                "AngioEye processing package and restart the application if needed."
            ),
            show_input_methods=True,
            selector_container=selection_columns[1],
        )
        return

    _render_processing_information(
        _cached_processing_pipelines(stage_or_postprocesses),
        empty_message=(
            f"No {category.lower()} were discovered. Install the corresponding "
            "optional processing package and restart the application if needed."
        ),
        selector_container=selection_columns[1],
    )


def _render_processing_information(
    descriptors: Sequence[Any],
    *,
    empty_message: str,
    show_input_methods: bool = False,
    selector_container=None,
) -> None:
    if not descriptors:
        st.info(empty_message)
        return

    descriptor_names = [descriptor.name for descriptor in descriptors]
    selector = st if selector_container is None else selector_container
    selected_name = selector.selectbox(
        "Postprocess" if show_input_methods else "Pipeline",
        descriptor_names,
        key="processing_info_descriptor",
    )
    descriptor = next(
        descriptor for descriptor in descriptors if descriptor.name == selected_name
    )
    _render_processing_descriptor(descriptor, show_input_methods=show_input_methods)


def _render_processing_descriptor(
    descriptor: Any,
    *,
    show_input_methods: bool,
) -> None:
    title = f"**{descriptor.name}**"
    if show_input_methods:
        input_methods = ", ".join(
            INPUT_METHOD_LABELS.get(method, method.replace("_", " "))
            for method in getattr(descriptor, "input_methods", ())
        )
        if input_methods:
            title += f"\n\n*Allowed inputs: {input_methods}*"
    st.markdown(f"## {title}")
    st.markdown(descriptor.description or "No description provided by the decorator.")
    if not descriptor.available:
        reason = ", ".join(
            (
                *getattr(descriptor, "missing_deps", ()),
                *getattr(descriptor, "missing_pipelines", ()),
            )
        )
        if not reason:
            reason = str(getattr(descriptor, "error_msg", "") or "").strip()
        st.caption("Unavailable" + (f": {reason}" if reason else "."))


def _render_postprocess_selection(
    selected_acquisitions: list[AcquisitionResult],
    selected_angioeye_pipelines: Optional[tuple[str, ...]],
) -> tuple[str, ...]:
    if not selected_acquisitions:
        st.caption(
            "Select at least one acquisition to show compatible postprocesses."
        )
        return ()

    proposed = proposed_angioeye_postprocesses(
        _cached_angioeye_postprocesses(),
        len(selected_acquisitions),
        selected_pipelines=selected_angioeye_pipelines,
    )
    if not proposed:
        st.caption(
            "No AngioEye postprocess supports this selection size and pipeline "
            "selection. "
            "ZIP postprocess mode is not available from the acquisition scan."
        )
        return ()

    options = [postprocess.name for postprocess in proposed]
    selected = st.multiselect(
        "AngioEye postprocesses",
        options,
        default=[],
        key="angioeye_postprocesses",
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
    return tuple(dict.fromkeys(_processing_app_label(stage) for stage in stages))


def _render_processing_log_view(
    selected_file_ids: list[str],
    selected_stages: list[str],
    *,
    entries: Sequence[dict[str, object]] | None = None,
    allowed_file_ids: list[str] | None = None,
    allowed_apps: tuple[str, ...] | None = None,
) -> tuple[str, str, object]:
    selected_log_file, selected_log_app = _render_log_filters(
        selected_file_ids,
        selected_stages,
        allowed_apps=allowed_apps,
    )
    st.markdown("#### Log")
    log_placeholder = st.empty()
    _render_previous_log(
        log_placeholder,
        file_filter=selected_log_file,
        app_filter=selected_log_app,
        allowed_file_ids=(
            selected_file_ids if allowed_file_ids is None else allowed_file_ids
        ),
        allowed_apps=(
            _processing_app_labels(selected_stages)
            if allowed_apps is None
            else allowed_apps
        ),
        entries=entries,
    )
    return selected_log_file, selected_log_app, log_placeholder


def _render_log_filters(
    selected_file_ids: list[str],
    selected_stages: list[str],
    *,
    allowed_apps: tuple[str, ...] | None = None,
) -> tuple[str, str]:
    file_options = sorted(dict.fromkeys(str(file_id) for file_id in selected_file_ids))
    app_options = list(
        _processing_app_labels(selected_stages)
        if allowed_apps is None
        else allowed_apps
    )
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


def _processing_log_entries(
    entries: Sequence[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    using_explicit_entries = entries is not None
    raw_entries = entries if using_explicit_entries else st.session_state.get(
        PROCESSING_LOG_ENTRIES_KEY
    )
    if isinstance(raw_entries, (list, tuple)) and raw_entries:
        normalized: list[dict[str, object]] = []
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
            normalized.append(
                {
                    "line": str(raw_entry.get("line", "")),
                    "files": files,
                    "app": str(raw_entry.get("app", "")),
                }
            )
        if normalized:
            return normalized
        if using_explicit_entries:
            return []

    if using_explicit_entries:
        return []

    return [
        {
            "line": str(line),
            "files": (),
            "app": PROCESSING_LOG_MANAGER_APP,
        }
        for line in st.session_state.get("processing_log", [])
    ]


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
    entries: Sequence[dict[str, object]] | None = None,
) -> None:
    normalized_entries = _processing_log_entries(entries)
    if not normalized_entries:
        return

    visible_entries = [
        entry
        for entry in normalized_entries
        if (
            allowed_file_ids is None
            or (
                allowed_file_ids
                and bool(set(entry["files"]).intersection(allowed_file_ids))
            )
        )
        and (allowed_apps is None or (allowed_apps and entry["app"] in allowed_apps))
        and (file_filter == PROCESSING_LOG_ALL_FILES or file_filter in entry["files"])
        and (app_filter == PROCESSING_LOG_ALL_APPS or app_filter == entry["app"])
    ]
    target = log_placeholder if log_placeholder is not None else st
    if not visible_entries:
        target.caption("No log entries match the selected file and app.")
        return
    target.code(
        "\n".join(str(entry["line"]) for entry in visible_entries),
        language="text",
    )
