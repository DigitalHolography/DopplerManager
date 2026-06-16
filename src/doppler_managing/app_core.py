from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from doppler_managing.scanner import ScanOptions, holo_filter_ids_from_text, scan_root
from doppler_managing.ui.dashboard import (
    render_filters,
    render_overview_table,
)
from doppler_managing.ui.detail import render_acquisition_detail
from doppler_managing.ui.theme import apply_dark_theme


DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_ENTRIES = 250_000
DEFAULT_PREVIEW_LIMIT = 80
SCAN_ROOT_KEY = "scan_root_input"
SCAN_ROOT_DROP_KEY = "scan_root_drop"
SCAN_ROOT_DROP_ERROR_KEY = "scan_root_drop_error"
SCAN_ROOT_BROWSE_ERROR_KEY = "scan_root_browse_error"
SCAN_INPUT_MODE_KEY = "scan_input_mode"
HOLO_FILTER_UPLOAD_VERSION_KEY = "holo_filter_upload_version"


_SCAN_ROOT_DROP_HELPER = (
    st.components.v2.component(
        "scan_root_drop_helper",
        html='<span data-scan-root-drop-helper="true"></span>',
        js="""
export default function(component) {
    const { setTriggerValue } = component;

    function firstPayloadLine(value) {
        return String(value || "")
            .split(/\\r?\\n/)
            .map((line) => line.trim())
            .find((line) => line && !line.startsWith("#")) || "";
    }

    function fromFileUri(value) {
        try {
            const url = new URL(value);
            if (url.protocol !== "file:") {
                return "";
            }
            const path = decodeURIComponent(url.pathname || "");
            if (url.hostname) {
                return "\\\\\\\\" + url.hostname + path.replace(/\\//g, "\\\\");
            }
            if (/^\\/[a-zA-Z]:\\//.test(path)) {
                return path.slice(1).replace(/\\//g, "\\\\");
            }
            return path;
        } catch {
            return "";
        }
    }

    function isAbsolutePath(value) {
        return /^[a-zA-Z]:[\\\\/]/.test(value) || /^\\\\\\\\/.test(value) || /^\\//.test(value);
    }

    function normalizeCandidate(value) {
        let candidate = firstPayloadLine(value);
        if (!candidate) {
            return "";
        }
        if (
            (candidate.startsWith('"') && candidate.endsWith('"')) ||
            (candidate.startsWith("'") && candidate.endsWith("'"))
        ) {
            candidate = candidate.slice(1, -1);
        }
        if (/^file:/i.test(candidate)) {
            candidate = fromFileUri(candidate);
        }
        if (/^[a-zA-Z]:\\//.test(candidate) || /^\\/\\//.test(candidate)) {
            candidate = candidate.replace(/\\//g, "\\\\");
        }
        return isAbsolutePath(candidate) ? candidate : "";
    }

    function pathFromFile(file) {
        if (!file) {
            return "";
        }
        for (const attribute of ["path", "mozFullPath", "webkitRelativePath", "name"]) {
            const candidate = normalizeCandidate(file[attribute]);
            if (candidate) {
                return candidate;
            }
        }
        return "";
    }

    function droppedPath(dataTransfer) {
        for (const type of ["text/uri-list", "text/plain"]) {
            try {
                const candidate = normalizeCandidate(dataTransfer.getData(type));
                if (candidate) {
                    return candidate;
                }
            } catch {
            }
        }

        for (const item of Array.from(dataTransfer.items || [])) {
            if (item.kind !== "file" || typeof item.getAsFile !== "function") {
                continue;
            }
            const candidate = pathFromFile(item.getAsFile());
            if (candidate) {
                return candidate;
            }
        }

        for (const file of Array.from(dataTransfer.files || [])) {
            const candidate = pathFromFile(file);
            if (candidate) {
                return candidate;
            }
        }

        return "";
    }

    const input =
        document.querySelector(".st-key-scan_root_input input") ||
        document.querySelector('input[aria-label="Root path"]');
    if (!input) {
        return;
    }

    const target = input.closest('[data-testid="stTextInput"]') || input.closest(".stTextInput") || input;
    if (target.dataset.scanRootDropAttached === "true") {
        return;
    }
    target.dataset.scanRootDropAttached = "true";

    function setActive(active) {
        input.style.outline = active ? "2px solid var(--st-primary-color)" : "";
        input.style.outlineOffset = active ? "2px" : "";
    }

    function handleDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
        setActive(true);
    }

    function handleDragLeave(event) {
        if (!event.relatedTarget || !target.contains(event.relatedTarget)) {
            setActive(false);
        }
    }

    function handleDrop(event) {
        event.preventDefault();
        setActive(false);

        const path = droppedPath(event.dataTransfer);
        if (path) {
            setTriggerValue("selected", path);
        } else {
            setTriggerValue(
                "error",
                "The browser did not provide a folder path. Use Browse or paste the path."
            );
        }
    }

    target.addEventListener("dragover", handleDragOver);
    target.addEventListener("dragleave", handleDragLeave);
    target.addEventListener("drop", handleDrop);

    return () => {
        target.dataset.scanRootDropAttached = "";
        target.removeEventListener("dragover", handleDragOver);
        target.removeEventListener("dragleave", handleDragLeave);
        target.removeEventListener("drop", handleDrop);
    };
}
""",
        isolate_styles=False,
    )
    if hasattr(st.components, "v2")
    else None
)


ProcessingRenderer = Callable[..., None]


def main(processing_renderer: ProcessingRenderer | None = None) -> None:
    st.set_page_config(
        page_title="Doppler Manager",
        page_icon="DM",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_dark_theme()

    default_root = Path.cwd() / "software_pipeline_validation"
    st.title("Doppler Manager")

    root_input, scan_options, run_scan, scan_hint_slot = _render_scan_bar(default_root)

    if run_scan:
        with st.spinner("Scanning pipeline format..."):
            st.session_state.scan_result = _scan_with_options(root_input, scan_options)

    if "scan_result" not in st.session_state:
        scan_hint_slot.info(
            "Select a NAS or local root path, then run a scan. Large .holo and .h5 files are never loaded."
        )
        return

    scan_result = st.session_state.scan_result
    acquisitions = scan_result.acquisitions

    _render_scan_messages(scan_result)

    if not acquisitions:
        st.warning("No compatible acquisition was detected under this root.")
        return

    if processing_renderer is None:
        index_tab, detail_tab = st.tabs(["Acquisition Index", "Acquisition Details"])
        processing_tab = None
    else:
        index_tab, detail_tab, processing_tab = st.tabs(
            ["Acquisition Index", "Acquisition Details", "Processing"]
        )

    with index_tab:
        frame = render_filters(acquisitions, scan_result)
        render_overview_table(frame)
        st.caption(
            f"{scan_result.visited_entries:,}".replace(",", " ")
            + f" entries inspected across {scan_result.visited_dirs} folders."
        )

    with detail_tab:
        render_acquisition_detail(acquisitions, frame)

    if processing_tab is not None and processing_renderer is not None:
        with processing_tab:
            processing_renderer(scan_result, frame, root_input, scan_options, _refresh_scan)


@st.cache_data(show_spinner=False)
def _cached_scan(
    root: str,
    max_depth: int,
    max_entries: int,
    preview_limit: int,
    read_versions: bool,
    holo_filter_ids: tuple[str, ...] | None,
):
    options = ScanOptions(
        max_depth=max_depth,
        max_entries=max_entries,
        preview_limit_per_stage=preview_limit,
        read_versions=read_versions,
        holo_filter_ids=set(holo_filter_ids) if holo_filter_ids is not None else None,
    )
    return scan_root(root, options)


def _refresh_scan(
    root: str,
    options: ScanOptions,
):
    _cached_scan.clear()
    return _scan_with_options(root, options)


def _scan_with_options(root: str, options: ScanOptions):
    return _cached_scan(
        root,
        options.max_depth,
        options.max_entries,
        options.preview_limit_per_stage,
        options.read_versions,
        _holo_filter_cache_key(options),
    )


def _render_scan_bar(default_root: Path):
    root_default = str(default_root if default_root.exists() else Path.cwd())
    st.session_state.setdefault(SCAN_ROOT_KEY, root_default)
    st.session_state.setdefault(SCAN_INPUT_MODE_KEY, "browse")
    st.session_state.setdefault(HOLO_FILTER_UPLOAD_VERSION_KEY, 0)
    with st.container():
        scan_hint_slot = st.empty()
        input_cols = st.columns([5, 1, 0.25, 1.15])
        root_input = input_cols[0].text_input(
            "Root path",
            key=SCAN_ROOT_KEY,
            label_visibility="collapsed",
            on_change=_select_scan_root,
        )
        _render_scan_root_drop_helper()
        _render_scan_root_widget_messages(input_cols[0])
        input_cols[1].button("Browse", on_click=_browse_scan_root, args=(root_default,), width="stretch")
        input_cols[2].markdown('<div class="dm-scan-or">or</div>', unsafe_allow_html=True)
        holo_filter_ids = _render_holo_filter_upload(input_cols[3])

        action_cols = st.columns([1.8, 0.45, 6.4])
        run_scan = action_cols[0].button(
            "Scan",
            type="primary",
            width="stretch",
            key="scan_button",
        )
        max_depth, max_entries, preview_limit, read_versions = _render_scan_settings(action_cols[1])

    options = ScanOptions(
        max_depth=int(max_depth),
        max_entries=int(max_entries),
        preview_limit_per_stage=int(preview_limit),
        read_versions=bool(read_versions),
        holo_filter_ids=holo_filter_ids,
    )
    return root_input, options, run_scan, scan_hint_slot


def _render_scan_settings(container) -> tuple[int, int, int, bool]:
    with container:
        with st.popover(
            "",
            icon=":material/settings:",
            help="Scan settings",
            use_container_width=True,
        ):
            max_depth = st.slider("Max depth", min_value=1, max_value=20, value=DEFAULT_MAX_DEPTH)
            max_entries = st.number_input(
                "Max entries",
                min_value=1_000,
                max_value=2_000_000,
                value=DEFAULT_MAX_ENTRIES,
                step=10_000,
            )
            preview_limit = st.slider(
                "Media files per stage",
                min_value=10,
                max_value=200,
                value=DEFAULT_PREVIEW_LIMIT,
            )
            read_versions = st.checkbox("Read version files", value=True)
    return int(max_depth), int(max_entries), int(preview_limit), bool(read_versions)


def _render_holo_filter_upload(container) -> set[str] | None:
    upload_key = _holo_filter_upload_key()
    with container:
        with st.popover("Upload list", use_container_width=True):
            st.caption("Use a .txt list of .holo paths or names.")
            holo_filter_file = st.file_uploader(
                ".holo filter list",
                type=["txt"],
                accept_multiple_files=False,
                key=upload_key,
                label_visibility="collapsed",
                on_change=_select_holo_filter_list,
            )
            holo_filter_ids = _uploaded_holo_filter_ids(holo_filter_file)
            if holo_filter_ids is None:
                return None

            count = len(holo_filter_ids)
            suffix = "" if count == 1 else "s"
            st.caption(f"{count} .holo name{suffix} loaded.")
            return holo_filter_ids if st.session_state.get(SCAN_INPUT_MODE_KEY) == "list" else None


def _holo_filter_upload_key() -> str:
    version = int(st.session_state.get(HOLO_FILTER_UPLOAD_VERSION_KEY, 0))
    return f"holo_filter_upload_{version}"


def _uploaded_holo_filter_ids(uploaded_file) -> set[str] | None:
    if uploaded_file is None:
        return None
    text = uploaded_file.getvalue().decode("utf-8-sig", errors="replace")
    return holo_filter_ids_from_text(text)


def _holo_filter_cache_key(options: ScanOptions) -> tuple[str, ...] | None:
    if options.holo_filter_ids is None:
        return None
    return tuple(sorted(options.holo_filter_ids))


def _render_scan_root_drop_helper() -> None:
    if _SCAN_ROOT_DROP_HELPER is None:
        return
    try:
        _SCAN_ROOT_DROP_HELPER(
            key=SCAN_ROOT_DROP_KEY,
            height=1,
            on_selected_change=_apply_dropped_scan_root,
            on_error_change=_apply_dropped_scan_root,
        )
    except ValueError as exc:
        if "not registered" not in str(exc):
            raise


def _apply_dropped_scan_root() -> None:
    state = st.session_state.get(SCAN_ROOT_DROP_KEY, {})
    selected = _state_value(state, "selected")
    error = _state_value(state, "error")
    if selected:
        st.session_state[SCAN_ROOT_KEY] = str(selected)
        _select_scan_root()
        st.session_state.pop(SCAN_ROOT_DROP_ERROR_KEY, None)
    elif error:
        st.session_state[SCAN_ROOT_DROP_ERROR_KEY] = str(error)


def _select_scan_root() -> None:
    st.session_state[SCAN_INPUT_MODE_KEY] = "browse"
    st.session_state[HOLO_FILTER_UPLOAD_VERSION_KEY] = (
        int(st.session_state.get(HOLO_FILTER_UPLOAD_VERSION_KEY, 0)) + 1
    )


def _select_holo_filter_list() -> None:
    st.session_state[SCAN_INPUT_MODE_KEY] = "list"


def _browse_scan_root(default_root: str) -> None:
    dialog_root = None
    try:
        import tkinter as tk
        from tkinter import filedialog

        dialog_root = tk.Tk()
        dialog_root.withdraw()
        dialog_root.attributes("-topmost", True)
        dialog_root.update()
        selected = filedialog.askdirectory(
            title="Select scan root",
            initialdir=_initial_browse_dir(default_root),
            mustexist=True,
        )
    except Exception as exc:
        st.session_state[SCAN_ROOT_BROWSE_ERROR_KEY] = f"Unable to open folder picker: {exc}"
        return
    finally:
        if dialog_root is not None:
            dialog_root.destroy()

    if selected:
        st.session_state[SCAN_ROOT_KEY] = selected
        _select_scan_root()
        st.session_state.pop(SCAN_ROOT_BROWSE_ERROR_KEY, None)


def _initial_browse_dir(default_root: str) -> str:
    candidates = (
        str(st.session_state.get(SCAN_ROOT_KEY) or ""),
        default_root,
        str(Path.cwd()),
    )
    for candidate in candidates:
        if not candidate:
            continue
        try:
            path = Path(candidate).expanduser()
            if path.is_file():
                path = path.parent
            if path.exists() and path.is_dir():
                return str(path)
        except OSError:
            continue
    return str(Path.cwd())


def _render_scan_root_widget_messages(container) -> None:
    for key in (SCAN_ROOT_BROWSE_ERROR_KEY, SCAN_ROOT_DROP_ERROR_KEY):
        message = st.session_state.pop(key, "")
        if message:
            container.caption(message)


def _state_value(state, key: str):
    if isinstance(state, dict):
        return state.get(key)
    return getattr(state, key, None)


def _render_scan_messages(scan_result) -> None:
    if scan_result.truncated:
        st.warning("The scan stopped at the configured entry limit. Increase the limit or scan a narrower folder.")
    for error in scan_result.errors:
        st.error(error)
