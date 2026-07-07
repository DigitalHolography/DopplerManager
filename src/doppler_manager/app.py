from __future__ import annotations

from pathlib import Path

import streamlit as st

from doppler_manager.scan.cache import refresh_scan, scan_with_options
from doppler_manager.ui.dashboard import (
    render_filters,
    render_overview_table,
)
from doppler_manager.ui.detail import render_acquisition_detail
from doppler_manager.ui.processing import render_processing_tab
from doppler_manager.ui.scan import (
    render_scan_bar,
    render_scan_messages,
)
from doppler_manager.ui.theme import apply_dark_theme


def main() -> None:
    st.set_page_config(
        page_title="Doppler Manager",
        page_icon="DM",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_dark_theme()

    default_root = Path.cwd() / "software_pipeline_validation"
    st.title("Doppler Manager")

    root_input, scan_options, run_scan, refresh_clicked, scan_hint_slot = render_scan_bar(
        default_root
    )

    if run_scan:
        with st.spinner("Scanning pipeline format..."):
            st.session_state.scan_result = scan_with_options(root_input, scan_options)
        st.rerun()
    elif refresh_clicked:
        with st.spinner("Refreshing pipeline format..."):
            st.session_state.scan_result = refresh_scan(root_input, scan_options)
        st.rerun()

    if "scan_result" not in st.session_state:
        scan_hint_slot.info(
            "Select a NAS or local root path, then run a scan. "
            "Large .holo and .h5 files are never loaded."
        )
        return

    scan_result = st.session_state.scan_result
    acquisitions = scan_result.acquisitions

    render_scan_messages(scan_result)

    if not acquisitions:
        st.warning("No compatible acquisition was detected under this root.")
        return

    with st.container(border=True, key="main_mode_tabs"):
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

        with processing_tab:
            render_processing_tab(scan_result, frame, root_input, scan_options, refresh_scan)


if __name__ == "__main__":
    main()
