import streamlit as st
from pathlib import Path
import time

from src.FileFinder.FileFinderClass import FileFinder
from src.Logger.LoggerClass import Logger

def render_sidebar(ff: FileFinder) -> None:
    """
    Renders the sidebar UI components and handles the associated logic.
    """
    st.sidebar.title("Actions")
    scan_path = st.sidebar.text_input("Directory to scan", "Y:\\")

    if st.sidebar.button("Start directory scan"):
        if Path(scan_path).is_dir():
            st.sidebar.info("The scan may take a long time. Please wait.")
            with st.spinner(f"Scanning {scan_path}..."):
                t1 = time.time()
                ff.Findfiles(scan_path)
                t2 = time.time()
                Logger.info(f"Time taken: {t2 - t1:.6f}", "TIME")
                st.sidebar.success("Scan completed successfully!")
                # Clear the data cache and rerun the app to show new data
                st.cache_data.clear()
                st.rerun()
        else:
            st.sidebar.error("The specified path is not a valid directory.")

    st.sidebar.markdown("---")
    if st.sidebar.button("Clear database"):
        ff.ClearDB()
        st.sidebar.success("Database cleared.")
        st.rerun()