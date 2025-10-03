import streamlit as st
from pathlib import Path
import time
import tkinter as tk
from tkinter import filedialog

from src.FileFinder.FileFinderClass import FileFinder
from src.Logger.LoggerClass import Logger


def add_directory_to_scan_list():
    """
    Opens a directory selection dialog and adds the selected path
    to the list in the session state.
    """
    # Create a Tkinter root window and hide it
    root = tk.Tk()
    root.withdraw()
    # Open the directory selection dialog
    folder_path = filedialog.askdirectory()
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
        st.session_state.scan_paths = ["Y:\\"]

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
    if st.sidebar.button("Update database"):
        scan_paths = st.session_state.scan_paths
        if not scan_paths:
            st.sidebar.error("No directories to scan. Please add a directory.")
            return

        st.sidebar.info("The update may take a few minutes. Please wait.")
        with st.spinner("Updating database..."):
            progress_bar = st.sidebar.progress(0, text="Starting scan...")
            t1 = time.time()
            total_paths = len(scan_paths)

            # Reset the database only before scanning the first directory
            reset_db_flag = True

            for i, path_str in enumerate(scan_paths):
                path_obj = Path(path_str)
                if path_obj.is_dir():
                    progress_text = f"Scanning {i + 1}/{total_paths}: {path_str}"
                    progress_bar.progress((i) / total_paths, text=progress_text)

                    ff.Findfiles(
                        path_str,
                        reset_db=reset_db_flag,
                        callback_bar=None,  # Progress within a single dir is complex
                        use_parallelism=False,
                    )
                    # After the first directory, subsequent scans should append
                    if reset_db_flag:
                        reset_db_flag = False
                else:
                    st.sidebar.error(
                        f"Path {i + 1} is not a valid directory: {path_str}"
                    )

            t2 = time.time()
            Logger.info(f"Total time taken: {t2 - t1:.6f}", "TIME")
            progress_bar.progress(1.0, "Update complete!")
            st.sidebar.success("Database updated successfully!")

            time.sleep(2)  # Give user time to see the success message
            progress_bar.empty()
            st.cache_data.clear()
            st.rerun()

    # --- Clear Database Button ---
    st.sidebar.markdown("---")
    if st.sidebar.button("Clear database"):
        ff.ClearDB()
        st.sidebar.success("Database cleared.")
        st.rerun()
