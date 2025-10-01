import streamlit as st
import pandas as pd
import zipfile
import io
import os
from pathlib import Path


def render_export_section(filtered_ef_df: pd.DataFrame):
    """
    Renders the export section for downloading selected files from the
    EyeFlow dataframe.

    Args:
        filtered_ef_df (pd.DataFrame): DataFrame filtered by all previous selections.
    """
    st.header("Export Data")

    if filtered_ef_df.empty:
        st.info("No EyeFlow data is selected to be exported.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        export_pdfs = st.checkbox("Export PDF Reports", value=True)
    with col2:
        export_h5s = st.checkbox("Export H5 Outputs", value=True)
    with col3:
        export_jsons = st.checkbox("Export JSON files", value=True)

    if st.button("Prepare Export Package"):
        # Clear any previous data from the session state
        if "zip_buffer" in st.session_state:
            del st.session_state["zip_buffer"]

        files_to_zip = []
        seen_paths = set()  # To avoid adding the same file multiple times

        # Pre-scan and collect all files to be added to the zip
        for _, row in filtered_ef_df.iterrows():
            ef_folder_path_str = row.get("ef_folder")
            if not ef_folder_path_str or pd.isna(ef_folder_path_str):
                continue

            base_folder = Path(ef_folder_path_str).name

            # Collect PDF reports
            if (
                export_pdfs
                and row.get("ef_report_path")
                and pd.notna(row["ef_report_path"])
            ):
                file_path = Path(row["ef_report_path"])
                if file_path not in seen_paths:
                    arcname = os.path.join(base_folder, "pdf", file_path.name)
                    files_to_zip.append({"path": file_path, "arcname": arcname})
                    seen_paths.add(file_path)

            # Collect H5 outputs
            if export_h5s and row.get("ef_h5_output") and pd.notna(row["ef_h5_output"]):
                file_path = Path(row["ef_h5_output"])
                if file_path not in seen_paths:
                    arcname = os.path.join(base_folder, "h5", file_path.name)
                    files_to_zip.append({"path": file_path, "arcname": arcname})
                    seen_paths.add(file_path)

            # Collect JSON files
            if export_jsons:
                json_dir = Path(ef_folder_path_str) / "json"
                if json_dir.exists() and json_dir.is_dir():
                    for json_file in json_dir.glob("*.json"):
                        if json_file not in seen_paths:
                            arcname = os.path.join(base_folder, "json", json_file.name)
                            files_to_zip.append({"path": json_file, "arcname": arcname})
                            seen_paths.add(json_file)

        if not files_to_zip:
            st.warning("No files were selected or are available to export.")
            return

        progress_bar = st.progress(0, text="Initializing export...")
        files_processed = 0
        total_files = len(files_to_zip)

        # Create a zip file in an in-memory buffer
        zip_buffer = io.BytesIO()
        skipped_files = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_info in files_to_zip:
                file_path = file_info["path"]
                arcname = file_info["arcname"]

                if file_path.exists() and file_path.is_file():
                    zf.write(file_path, arcname)
                else:
                    skipped_files.append(str(file_path))

                files_processed += 1
                progress_text = f"Processing file {files_processed} of {total_files}: {file_path.name}"
                progress_bar.progress(files_processed / total_files, text=progress_text)

        progress_bar.progress(1.0, text="Export preparation complete!")
        # Store the buffer and any skipped files in the session state
        st.session_state.zip_buffer = zip_buffer
        st.session_state.skipped_files = skipped_files

    # Display download button if a zip buffer exists in the session state
    if "zip_buffer" in st.session_state:
        st.success("Your export package is ready to be downloaded.")
        st.download_button(
            label="Download zip",
            data=st.session_state.zip_buffer.getvalue(),
            file_name="export.zip",
            mime="application/zip",
            # Clean up the session state after the download starts
            on_click=lambda: st.session_state.pop("zip_buffer", None),
        )
        if st.session_state.get("skipped_files"):
            st.warning("The following files were not found and were skipped:")
            st.code("\n".join(st.session_state.get("skipped_files", [])))
