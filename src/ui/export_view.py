import streamlit as st
import pandas as pd
import zipfile
import io
import os
import json
from pathlib import Path


def _collect_pdf_reports(
    row: pd.Series, base_folder: str, files_to_zip: list, seen_paths: set
) -> None:
    """Collects PDF report files."""
    if row.get("ef_report_path") and pd.notna(row["ef_report_path"]):
        file_path = Path(row["ef_report_path"])
        if file_path not in seen_paths:
            arcname = os.path.join(base_folder, "pdf", file_path.name)
            files_to_zip.append({"path": file_path, "arcname": arcname})
            seen_paths.add(file_path)


def _collect_h5_outputs(
    row: pd.Series, base_folder: str, files_to_zip: list, seen_paths: set
) -> None:
    """Collects H5 output files."""
    if row.get("ef_h5_output") and pd.notna(row["ef_h5_output"]):
        file_path = Path(row["ef_h5_output"])
        if file_path not in seen_paths:
            arcname = os.path.join(base_folder, "h5", file_path.name)
            files_to_zip.append({"path": file_path, "arcname": arcname})
            seen_paths.add(file_path)


def _collect_json_outputs(
    ef_folder_path: Path, base_folder: str, files_to_zip: list, seen_paths: set
) -> None:
    """Collects all JSON files from the 'json' subdirectory."""
    json_dir = ef_folder_path / "json"
    if json_dir.exists() and json_dir.is_dir():
        for json_file in json_dir.glob("*.json"):
            if json_file not in seen_paths:
                arcname = os.path.join(base_folder, "json", json_file.name)
                files_to_zip.append({"path": json_file, "arcname": arcname})
                seen_paths.add(json_file)


def _collect_input_params(
    row: pd.Series, base_folder: str, files_to_zip: list, seen_paths: set
) -> None:
    """Collects HD and EF input parameter JSON files with case-insensitive search."""
    # Collect HD input parameters
    hd_folder_str = row.get("hd_folder")
    if hd_folder_str and pd.notna(hd_folder_str):
        hd_folder_path = Path(hd_folder_str)
        expected_hd_filename_lower = (
            f"{hd_folder_path.name}_input_hd_params.json".lower()
        )
        if hd_folder_path.is_dir():
            for file in hd_folder_path.iterdir():
                if (
                    file.name.lower() == expected_hd_filename_lower
                    and file not in seen_paths
                ):
                    arcname = os.path.join(base_folder, "json", file.name)
                    files_to_zip.append({"path": file, "arcname": arcname})
                    seen_paths.add(file)
                    break

    # Collect EF input parameters
    ef_folder_str = row.get("ef_folder")
    if ef_folder_str and pd.notna(ef_folder_str):
        ef_folder_path = Path(ef_folder_str)
        json_dir = ef_folder_path / "json"
        expected_ef_filename_lower = (
            f"{ef_folder_path.name}_input_ef_params.json".lower()
        )
        if json_dir.is_dir():
            for file in json_dir.iterdir():
                if (
                    file.name.lower() == expected_ef_filename_lower
                    and file not in seen_paths
                ):
                    arcname = os.path.join(base_folder, "json", file.name)
                    files_to_zip.append({"path": file, "arcname": arcname})
                    seen_paths.add(file)
                    break


def _collect_files_to_zip(
    filtered_df: pd.DataFrame,
    export_pdfs,
    export_h5s,
    export_jsons,
    export_input_params,
) -> list:
    """
    Scans the filtered DataFrame and collects a list of files to be zipped
    based on user selections.

    Args:
        filtered_df (pd.DataFrame): The DataFrame containing file paths.
        export_pdfs (bool): Whether to include PDF files.
        export_h5s (bool): Whether to include H5 files.
        export_jsons (bool): Whether to include JSON files.
        export_input_params (bool): Whether to include input parameter JSON files.

    Returns:
        list: A list of dictionaries, where each dictionary contains the
              'path' and 'arcname' for a file.
    """
    files_to_zip = []
    seen_paths = set()  # To avoid adding the same file multiple times

    for _, row in filtered_df.iterrows():
        ef_folder_path_str = row.get("ef_folder")
        if not ef_folder_path_str or pd.isna(ef_folder_path_str):
            continue

        base_folder = Path(ef_folder_path_str).name
        ef_folder_path = Path(ef_folder_path_str)

        if export_pdfs:
            _collect_pdf_reports(row, base_folder, files_to_zip, seen_paths)

        if export_h5s:
            _collect_h5_outputs(row, base_folder, files_to_zip, seen_paths)

        if export_jsons:
            _collect_json_outputs(ef_folder_path, base_folder, files_to_zip, seen_paths)

        if export_input_params:
            _collect_input_params(row, base_folder, files_to_zip, seen_paths)

    return files_to_zip


def _create_zip_archive(files_to_zip: list, csv_data: bytes | None) -> tuple:
    """
    Creates a zip archive in an in-memory buffer from a list of files and
    optionally adds CSV data.

    Args:
        files_to_zip (list): A list of files to include in the zip.
        csv_data (bytes | None): The CSV data to add to the zip.

    Returns:
        tuple: A tuple containing the BytesIO buffer of the zip file and a
               list of paths for files that were skipped.
    """
    total_items = len(files_to_zip) + (1 if csv_data else 0)
    if total_items == 0:
        return io.BytesIO(), []

    progress_bar = st.progress(0, text="Initializing export...")
    zip_buffer = io.BytesIO()
    skipped_files = []
    items_processed = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add files from disk
        for file_info in files_to_zip:
            file_path = file_info["path"]
            arcname = file_info["arcname"]

            if file_path.exists() and file_path.is_file():
                zf.write(file_path, arcname)
            else:
                skipped_files.append(str(file_path))

            items_processed += 1
            progress_text = (
                f"Processing file {items_processed} of {total_items}: {file_path.name}"
            )
            progress_bar.progress(items_processed / total_items, text=progress_text)

        # Add CSV data from memory
        if csv_data:
            zf.writestr("eyeflow_data_export.csv", csv_data)
            items_processed += 1
            progress_text = f"Processing item {items_processed} of {total_items}: eyeflow_data_export.csv"
            progress_bar.progress(items_processed / total_items, text=progress_text)

    progress_bar.progress(1.0, text="Export preparation complete!")
    return zip_buffer, skipped_files


def _generate_csv_data(filtered_df: pd.DataFrame) -> bytes | None:
    """
    Generates a CSV string by reading and compiling data from JSON files
    associated with each row in the filtered DataFrame. It adds additional metadata
    from the main DataFrame to each row.

    Args:
        filtered_df (pd.DataFrame): DataFrame filtered by all previous selections.

    Returns:
        bytes | None: The generated CSV data as a string, or None if no data
                    could be processed.
    """
    all_json_data = []
    skipped_folders = []

    for _, row in filtered_df.iterrows():
        ef_folder_str = row.get("ef_folder")
        if not ef_folder_str or pd.isna(ef_folder_str):
            continue

        ef_folder_path = Path(ef_folder_str)
        json_dir = ef_folder_path / "json"

        # Find the JSON file containing "output"
        json_file_path = None
        if json_dir.exists() and json_dir.is_dir():
            matching_files = list(json_dir.glob("*output*.json"))
            if matching_files:
                json_file_path = matching_files[0]  # Take the first match

        if json_file_path and json_file_path.is_file():
            try:
                with open(json_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Add identifiers from the main DataFrame
                    data["ef_folder"] = ef_folder_path.name
                    data["measure_tag"] = row.get("measure_tag")
                    data["hd_version"] = row.get("hd_version")
                    data["ef_version"] = row.get("ef_version")
                    data["creation_date"] = row.get("holo_created_at")
                    all_json_data.append(data)
            except (json.JSONDecodeError, Exception) as e:
                st.warning(f"Could not read or parse {json_file_path.name}: {e}")
                skipped_folders.append(ef_folder_path.name)
        else:
            skipped_folders.append(ef_folder_path.name)

    if not all_json_data:
        st.warning("No JSON output files were found in the selected EyeFlow folders.")
        return None

    if skipped_folders:
        st.info(
            "Note: No JSON output file was found for the following folders: "
            f"{', '.join(skipped_folders)}"
        )

    # Normalize the JSON data into a flat table
    df = pd.json_normalize(all_json_data)
    return df.to_csv(index=False).encode("utf-8")


def render_export_section(filtered_ef_df: pd.DataFrame) -> None:
    """
    Renders the export section, allowing users to download selected files
    as a ZIP archive using a state-driven UI to prevent widget duplication.

    Args:
        filtered_ef_df (pd.DataFrame): DataFrame filtered by all previous selections.
    """
    st.header("Export Data")

    if filtered_ef_df.empty:
        st.info("No EyeFlow data is selected to be exported.")
        return

    # Initialize state if it doesn't exist
    if "export_status" not in st.session_state:
        st.session_state.export_status = "ready_to_export"

    # --- STATE 3: Ready to Download ---
    # If a zip file has been created, show the download button.
    if st.session_state.export_status == "ready_to_download":
        st.success("Your export package is ready to be downloaded.")
        st.download_button(
            label="Download ZIP",
            data=st.session_state.zip_buffer.getvalue(),
            file_name=st.session_state.get("zip_file_name", "eyeflow_export.zip"),
            mime="application/zip",
            on_click=lambda: st.session_state.update(export_status="ready_to_export"),
        )
        if st.session_state.get("skipped_files"):
            st.warning("The following files were not found and were skipped:")
            st.code("\n".join(st.session_state.get("skipped_files", [])))

    # --- STATE 2: Processing ---
    # If an export has been triggered, run the zipping process.
    # The buttons from the 'else' block will NOT be rendered.
    elif st.session_state.export_status == "processing":
        export_type = st.session_state.get("export_type", "full")

        # Determine which files to collect based on the button clicked
        if export_type == "pdf_csv":
            files_to_zip = _collect_files_to_zip(
                filtered_ef_df,
                export_pdfs=True,
                export_h5s=False,
                export_jsons=False,
                export_input_params=False,
            )
            st.session_state.zip_file_name = "eyeflow_pdf_csv_export.zip"
        else:  # 'full' export
            files_to_zip = _collect_files_to_zip(
                filtered_ef_df,
                export_pdfs=True,
                export_h5s=True,
                export_jsons=True,
                export_input_params=True,
            )
            st.session_state.zip_file_name = "eyeflow_full_export.zip"

        csv_data = _generate_csv_data(filtered_ef_df)

        if not files_to_zip and not csv_data:
            st.warning("No files or data are available to export.")
            st.session_state.export_status = "ready_to_export"  # Reset state
            st.rerun()
        else:
            zip_buffer, skipped_files = _create_zip_archive(files_to_zip, csv_data)
            st.session_state.zip_buffer = zip_buffer
            st.session_state.skipped_files = skipped_files

            # Transition to the next state and rerun
            st.session_state.export_status = "ready_to_download"
            st.rerun()

    # --- STATE 1: Ready to Export (Default) ---
    # Otherwise, show the export buttons.
    else:
        st.subheader("Create an export package")
        col1, col2 = st.columns(2)

        def set_export_type(export_type: str):
            st.session_state.export_status = "processing"
            st.session_state.export_type = export_type

        with col1:
            st.button(
                "Export pdf reports + csv data",
                use_container_width=True,
                on_click=set_export_type,
                args=("pdf_csv",),
            )

        with col2:
            st.button(
                "Export all (pdf reports, csv data, h5 outputs, json outputs and params)",
                use_container_width=True,
                on_click=set_export_type,
                args=("full",),
            )
