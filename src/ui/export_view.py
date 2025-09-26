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

    col1, col2 = st.columns(2)
    with col1:
        export_pdfs = st.checkbox("Export PDF Reports", value=True)
    with col2:
        export_h5s = st.checkbox("Export H5 Outputs", value=True)

    if st.button("Prepare Export Package"):
        # Clear any previous data from the session state
        if "zip_buffer" in st.session_state:
            del st.session_state["zip_buffer"]

        pdf_paths = []
        if export_pdfs:
            pdf_paths = filtered_ef_df["ef_report_path"].dropna().unique().tolist()

        h5_paths = []
        if export_h5s:
            h5_paths = filtered_ef_df["ef_h5_output"].dropna().unique().tolist()

        if not pdf_paths and not h5_paths:
            st.warning("No files were selected or are available to export.")
            return

        total_files = len(pdf_paths) + len(h5_paths)
        if total_files == 0:
            st.warning("No files found for the selected export types.")
            return

        progress_bar = st.progress(0, text="Initializing export...")
        files_processed = 0

        # Create a zip file in an in-memory buffer
        zip_buffer = io.BytesIO()
        skipped_files = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add PDF reports to the zip
            for path_str in pdf_paths:
                file_path = Path(path_str)
                if file_path.exists() and file_path.is_file():
                    arcname = os.path.join("pdf_reports", file_path.name)
                    zf.write(file_path, arcname)
                else:
                    skipped_files.append(f"(PDF) {path_str}")

                files_processed += 1
                progress_text = f"Processing file {files_processed} of {total_files}: {file_path.name}"
                progress_bar.progress(files_processed / total_files, text=progress_text)

            # Add H5 outputs to the zip
            for path_str in h5_paths:
                file_path = Path(path_str)
                if file_path.exists() and file_path.is_file():
                    arcname = os.path.join("h5_outputs", file_path.name)
                    zf.write(file_path, arcname)
                else:
                    skipped_files.append(f"(H5) {path_str}")

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
            label="Download Export.zip",
            data=st.session_state.zip_buffer.getvalue(),
            file_name="export.zip",
            mime="application/zip",
            # Clean up the session state after the download starts
            on_click=lambda: st.session_state.pop("zip_buffer", None),
        )
        if st.session_state.get("skipped_files"):
            st.warning("The following files were not found and were skipped:")
            st.code("\n".join(st.session_state.get("skipped_files", [])))
