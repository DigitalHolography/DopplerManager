import streamlit as st
from pathlib import Path
import time
import tkinter as tk
from tkinter import filedialog

from src.FileFinder.FileFinderClass import FileFinder
from src.Logger.LoggerClass import Logger
from src.Utils.ParamsLoader import ConfigManager


def select_directory():
    """
    Opens a directory selection dialog and updates the session state.
    This function is intended to be used as a callback.
    """
    # Create a Tkinter root window
    root = tk.Tk()
    # Hide the main window
    root.withdraw()
    # Open the directory selection dialog
    folder_path = filedialog.askdirectory()
    # Destroy the root window
    root.destroy()
    if folder_path:
        st.session_state.scan_path = folder_path


def render_sidebar(ff: FileFinder) -> None:
    """
    Renders the sidebar UI components and handles the associated logic.
    """
    st.sidebar.title("Database Controls")

    if "scan_path" not in st.session_state:
        st.session_state.scan_path = "Y:\\"

    st.sidebar.text_input("Directory to scan", key="scan_path")

    st.sidebar.button(
        "Select Directory",
        on_click=select_directory,
    )

    scan_path = st.session_state.scan_path

    if st.sidebar.button("Update database"):
        if Path(scan_path).is_dir():
            st.sidebar.info("The update may take a few minutes. Please wait.")
            with st.spinner(f"Updating database with files from {scan_path}..."):
                progress_bar = st.sidebar.progress(0, text="Starting scan...")

                t1 = time.time()
                ff.Findfiles(
                    scan_path,
                    reset_db=True,
                    callback_bar=progress_bar,
                    use_parallelism=ConfigManager.get("FINDER.USE_PARALLISM") or False,
                )
                t2 = time.time()
                Logger.info(f"Time taken: {t2 - t1:.6f}", "TIME")
                progress_bar.progress(1.0, "Update complete!")
                st.sidebar.success("Database updated successfully!")

                progress_bar.empty()
                # Clear the data cache and rerun the app to show new data
                st.cache_data.clear()
                st.rerun()
        else:
            st.sidebar.error("The specified path is not a valid directory.")

    st.sidebar.markdown("---")
    if st.sidebar.button("Clear database"):
        ff.ClearDB()
        st.cache_data.clear()
        st.sidebar.success("Database cleared.")
        st.rerun()
