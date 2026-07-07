from __future__ import annotations

from pathlib import Path

import streamlit as st

from doppler_manager.scan import (
    ScanOptions,
    holo_filter_entries_from_text,
    holo_filter_ids_from_text,
)


DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_ENTRIES = 250_000
DEFAULT_PREVIEW_LIMIT = 80
SCAN_ROOT_KEY = "scan_root_input"
SCAN_ROOT_DROP_KEY = "scan_root_drop"
SCAN_ROOT_DROP_ERROR_KEY = "scan_root_drop_error"
SCAN_ROOT_BROWSE_ERROR_KEY = "scan_root_browse_error"
SCAN_INPUT_MODE_KEY = "scan_input_mode"
HOLO_FILTER_UPLOAD_VERSION_KEY = "holo_filter_upload_version"
HOLO_FILTER_ENTRIES_KEY = "holo_filter_entries"
HOLO_FILTER_IDS_KEY = "holo_filter_ids"


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


def render_scan_bar(default_root: Path):
    root_default = str(default_root if default_root.exists() else Path.cwd())
    st.session_state.setdefault(SCAN_ROOT_KEY, root_default)
    st.session_state.setdefault(SCAN_INPUT_MODE_KEY, "browse")
    st.session_state.setdefault(HOLO_FILTER_UPLOAD_VERSION_KEY, 0)
    with st.container():
        scan_hint_slot = st.empty()
        input_cols = st.columns([5, 1, 0.25, 1.15])
        list_mode_active = _holo_filter_list_is_active()
        root_input = input_cols[0].text_input(
            "Root path",
            key=SCAN_ROOT_KEY,
            label_visibility="collapsed",
            on_change=_select_scan_root,
            disabled=list_mode_active,
            placeholder="Disabled while a .holo list is active",
        )
        if not list_mode_active:
            _render_scan_root_drop_helper()
        _render_scan_root_widget_messages(input_cols[0])
        input_cols[1].button(
            "Browse",
            on_click=_browse_scan_root,
            args=(root_default,),
            width="stretch",
        )
        input_cols[2].markdown('<div class="dm-scan-or">or</div>', unsafe_allow_html=True)
        holo_filter_ids, holo_filter_entries = _render_holo_filter_upload(input_cols[3])

        has_scan_result = "scan_result" in st.session_state
        action_cols = (
            st.columns([1.8, 0.9, 0.45, 5.5])
            if has_scan_result
            else st.columns([1.8, 0.45, 6.4])
        )
        run_scan = action_cols[0].button(
            "Scan",
            type="primary",
            width="stretch",
            key="scan_button",
        )
        refresh_clicked = False
        settings_col = action_cols[2] if has_scan_result else action_cols[1]
        if has_scan_result:
            refresh_clicked = action_cols[1].button(
                "Refresh",
                icon=":material/refresh:",
                help="Refresh",
                width="stretch",
                key="refresh_scan_button",
            )
        max_depth, max_entries, preview_limit, read_versions = _render_scan_settings(settings_col)

    options = ScanOptions(
        max_depth=int(max_depth),
        max_entries=int(max_entries),
        preview_limit_per_stage=int(preview_limit),
        read_versions=bool(read_versions),
        holo_filter_ids=holo_filter_ids,
        holo_filter_entries=holo_filter_entries,
    )
    return root_input, options, run_scan, refresh_clicked, scan_hint_slot


def render_scan_messages(scan_result) -> None:
    if scan_result.truncated:
        st.warning(
            "The scan stopped at the configured entry limit. "
            "Increase the limit or scan a narrower folder."
        )
    for error in scan_result.errors:
        st.error(error)


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


def _render_holo_filter_upload(container) -> tuple[set[str] | None, tuple[str, ...] | None]:
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
            if holo_filter_file is None and st.session_state.get(SCAN_INPUT_MODE_KEY) == "list":
                _clear_holo_filter_list()

            holo_filter_ids = st.session_state.get(HOLO_FILTER_IDS_KEY)
            holo_filter_entries = st.session_state.get(HOLO_FILTER_ENTRIES_KEY)
            if not holo_filter_ids or not holo_filter_entries:
                return None, None

            count = len(holo_filter_ids)
            suffix = "" if count == 1 else "s"
            st.caption(f"{count} .holo name{suffix} loaded.")
            if st.session_state.get(SCAN_INPUT_MODE_KEY) == "list":
                return set(holo_filter_ids), tuple(holo_filter_entries)
            return None, None


def _holo_filter_upload_key() -> str:
    version = int(st.session_state.get(HOLO_FILTER_UPLOAD_VERSION_KEY, 0))
    return f"holo_filter_upload_{version}"


def _holo_filter_list_is_active() -> bool:
    return (
        st.session_state.get(SCAN_INPUT_MODE_KEY) == "list"
        and bool(st.session_state.get(HOLO_FILTER_ENTRIES_KEY))
    )


def _remember_holo_filter_upload(uploaded_file) -> None:
    if uploaded_file is None:
        return
    text = uploaded_file.getvalue().decode("utf-8-sig", errors="replace")
    st.session_state[HOLO_FILTER_ENTRIES_KEY] = holo_filter_entries_from_text(text)
    st.session_state[HOLO_FILTER_IDS_KEY] = holo_filter_ids_from_text(text)
    st.session_state[SCAN_INPUT_MODE_KEY] = "list"


def _clear_holo_filter_list() -> None:
    had_list = (
        HOLO_FILTER_ENTRIES_KEY in st.session_state
        or HOLO_FILTER_IDS_KEY in st.session_state
        or st.session_state.get(SCAN_INPUT_MODE_KEY) == "list"
    )
    st.session_state.pop(HOLO_FILTER_ENTRIES_KEY, None)
    st.session_state.pop(HOLO_FILTER_IDS_KEY, None)
    st.session_state[SCAN_INPUT_MODE_KEY] = "browse"
    if had_list:
        st.session_state[HOLO_FILTER_UPLOAD_VERSION_KEY] = (
            int(st.session_state.get(HOLO_FILTER_UPLOAD_VERSION_KEY, 0)) + 1
        )


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
    _clear_holo_filter_list()


def _select_holo_filter_list() -> None:
    uploaded_file = st.session_state.get(_holo_filter_upload_key())
    if uploaded_file is None:
        _clear_holo_filter_list()
        return
    _remember_holo_filter_upload(uploaded_file)


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
