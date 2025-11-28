import streamlit as st
import time
import tkinter as tk
from tkinter import filedialog

from src.FileFinder.FileFinderClass import FileFinder
from src.Logger.LoggerClass import Logger
from src.Utils.ParamsLoader import ConfigManager


def add_directory_to_scan_list():
    """
    Opens a directory selection dialog and adds the selected path
    to the list in the session state.
    """
    # Create a Tkinter root window
    root = tk.Tk()
    # Make the root window appear on top
    root.attributes("-topmost", True)
    # Hide the root window
    root.withdraw()
    # Open the directory selection dialog
    folder_path = filedialog.askdirectory(parent=root)
    # Destroy the root window
    root.destroy()

    if folder_path:
        # Add the new path if it's not already in the list
        if folder_path not in st.session_state.scan_paths:
            st.session_state.scan_paths.append(folder_path)
        else:
            st.sidebar.warning("Directory already in the list.")


def render_sidebar(ff: FileFinder) -> None:
    """
    Renders the sidebar UI components and handles the associated logic.
    """
    st.sidebar.title("Database Controls")

    # Initialize scan_paths as a list in the session state if it doesn't exist
    if "scan_paths" not in st.session_state:
        st.session_state.scan_paths = []

    st.sidebar.markdown("##### Directories to Scan")

    # Display the list of directories to be scanned
    if not st.session_state.scan_paths:
        st.sidebar.info("No directories selected for scanning.")
    else:
        for path in st.session_state.scan_paths:
            st.sidebar.code(path, language=None)

    # --- Buttons for Directory Management ---
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.button(
            "Add Directory",
            on_click=add_directory_to_scan_list,
            help="Add a directory to the scan list.",
        )
    with col2:
        if st.button("Clear List"):
            st.session_state.scan_paths = []
            st.rerun()

    st.sidebar.markdown("---")

    # --- Database Update Button ---
    if st.sidebar.button("Start scan/update"):
        # override = ConfigManager.get("DB.OVERRIDE_DB") or False
        _handle_scan("The update may take a few minutes. Please wait.", ff, False, False)

    if st.sidebar.button("Scan New folders"):
        _handle_scan("Scanning for new files only...", ff, False, True)

    # --- Clear Database Button ---
    st.sidebar.markdown("---")
    if st.sidebar.button("Clear database"):
        ff.ClearDB()
        st.cache_data.clear()
        st.sidebar.success("Database cleared.")
        st.rerun()

def _handle_scan(info_text: str, ff: FileFinder, resetDB: bool, onlyNew: bool):
    scan_paths = st.session_state.scan_paths
    if not scan_paths:
        st.sidebar.error("No directories to scan. Please add a directory.")
        return

    

    st.sidebar.info(info_text)
    with st.spinner("Updating database..."):
        progress_bar = st.sidebar.progress(0, text="Starting scan...")
        t1 = time.time()

        parallelism = ConfigManager.get("FINDER.USE_PARALLISM") or False

        ff.Findfiles(
            scan_paths,
            reset_db=resetDB,
            callback_bar=progress_bar,
            use_parallelism=parallelism,
            only_new=onlyNew
        )

        t2 = time.time()
        Logger.info(f"Total time taken: {t2 - t1:.6f}", "TIME")
        progress_bar.progress(1.0, "Scan complete!")
        st.sidebar.success("Database updated successfully!")

        time.sleep(2)
        progress_bar.empty()
        st.cache_data.clear()
        st.rerun()
