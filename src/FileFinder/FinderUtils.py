import re

from pathlib import Path
from src.Logger.LoggerClass import Logger
from src.Utils.ParamsLoader import ConfigManager

from src.Utils.fs_utils import (
    safe_isdir,
    safe_file_read,
    get_last_update,
    json_dump_nullable,
)

from src.FileFinder.utils.path_parser import (
    get_measure_tag,
    get_render_number,
    parse_folder_date,
)

from src.FileFinder.utils.data_getter import (
    find_all_holo_files,
    find_preview_video,
    gather_all_hd_folders_data_from_holo,
    gather_ef_folders_data,
)


def _find_version_in_log(file_path: Path) -> str | None:
    """
    Efficiently finds and extracts a version number from a log file using regex.
    """
    version_patterns = [
        re.compile(r"PulseWave GitHub version (v[\d.]+)"),
        re.compile(r"Most recent tag : ([-a-z0-9.]+)"),
        re.compile(r"Welcome to EyeFlow (v[\d.]+)"),
    ]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                for pattern in version_patterns:
                    match = pattern.search(line)
                    if match:
                        # Return the version string as soon as it's found
                        return match.group(1).strip()
    except FileNotFoundError:
        Logger.error(
            f"File not found during version search: {file_path}", tags="FILESYSTEM"
        )
        return None

    return None


def _get_eyeflow_version(ef_folder: Path, hd_folder_name: str) -> str | None:
    ef_folder = Path(ef_folder)
    version_txt = ef_folder / f"{ef_folder.name}_version.txt"
    if not version_txt.is_file():
        Logger.warn(
            f"Eyeflow version file does not exist: {version_txt}", tags="FILESYSTEM"
        )
        return None

    version = safe_file_read(version_txt)
    if version:
        return version.strip()

    return None


def process_date_folder(date_folder: Path) -> tuple[list, list, list, list]:
    """
    Scans a single date folder and gathers data for .holo, HD, and EF files.
    This function is designed to be run in a separate process.
    It does NOT interact with the database.
    """
    if not safe_isdir(date_folder):  # or not check_folder_name_format(date_folder)
        Logger.info(f"Skipping: {date_folder}", "SKIP")
        return ([], [], [], [])

    Logger.info(f"Processing folder: {date_folder.name}", "WORKER")

    holo_data_to_insert = []
    hd_data_to_insert = []
    ef_data_to_insert = []
    preview_data_to_insert = []

    get_input_params = ConfigManager.get("FINDER.EF.GET_INPUT_PARAMS") or False

    holo_files = find_all_holo_files(date_folder)

    for holo_file in holo_files:
        holo_entry = {
            "path": holo_file,
            "tag": get_measure_tag(holo_file),
            "created_at": parse_folder_date(holo_file),
        }

        # We need a temporary ID to link the data before it's in the DB
        # It will be later replaced by the actual Id row of table
        temp_holo_id = str(holo_file)
        holo_data_to_insert.append((temp_holo_id, holo_entry))

        preview_video_path = find_preview_video(holo_file)
        if preview_video_path:
            preview_entry = {
                "holo_id": temp_holo_id,
                "path": preview_video_path,
            }
            preview_data_to_insert.append(preview_entry)

        hd_folders = gather_all_hd_folders_data_from_holo(holo_file)
        for render_number, hd_folder in hd_folders.items():
            hd_folder_path = hd_folder["path"]
            hd_entry = {
                "holo_id": temp_holo_id,
                "path": hd_folder_path,
                "render_number": render_number,
                "rendering_parameters": json_dump_nullable(
                    hd_folder["rendering_params"]
                ),
                "raw_h5_path": hd_folder["raw_h5_path"],
                "version": hd_folder["version_text"],
                "updated_at": get_last_update(hd_folder_path),
            }

            # We need a temporary ID to link the data before it's in the DB
            # It will be later replaced by the actual Id row of table
            temp_hd_id = str(hd_folder_path.absolute())
            hd_data_to_insert.append((temp_hd_id, hd_entry))

            eyeflow_folder = hd_folder_path / "eyeflow"
            if eyeflow_folder.exists():
                ef_renders = gather_ef_folders_data(eyeflow_folder, get_input_params)
                for ef in ef_renders:
                    ef_entry = {
                        "hd_id": temp_hd_id,
                        "render_number": get_render_number(ef["ef_folder"]),
                        "path": ef["ef_folder"],
                        "input_parameters": json_dump_nullable(
                            ef["InputEyeFlowParams"]["content"]
                        ),
                        "version": _get_eyeflow_version(
                            ef["ef_folder"], hd_folder_path.name
                        ),
                        "report_path": ef["report_path"],
                        "h5_output": ef["h5_output"],
                        "updated_at": get_last_update(ef["ef_folder"]),
                    }
                    ef_data_to_insert.append(ef_entry)

    return (
        holo_data_to_insert,
        hd_data_to_insert,
        ef_data_to_insert,
        preview_data_to_insert,
    )
