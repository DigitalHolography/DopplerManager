import os
import json
import re
import datetime

from pathlib import Path
from src.Logger.LoggerClass import Logger


def is_ef_folder(name: str):
    return "_EF_" in name


def safe_json_load(file_path: Path | str):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        Logger.error(f"{e}", tags="FILESYSTEM")
        return None


def safe_file_read(file_path: Path | str) -> str | None:
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        Logger.error(f"{e}", tags="FILESYSTEM")
        return None


def safe_isdir(path: Path | str) -> bool:
    try:
        path = Path(path)
        return path.is_dir()
    except (PermissionError, OSError) as e:
        Logger.error(
            f"Access denied or error reading directory: {path} – {e}", tags="FILESYSTEM"
        )
        return False


def safe_iterdir(path: Path | str) -> list[Path]:
    try:
        path = Path(path)
        if safe_isdir(path):
            return list(path.iterdir())
        else:
            return []
    except (PermissionError, OSError) as e:
        Logger.error(
            f"Access denied or error reading directory: {path} – {e}", tags="FILESYSTEM"
        )
        return []


def get_ef_folders_data(eyeflow_folder: Path) -> list[dict]:
    ef_data = []

    for ef_folder in safe_iterdir(eyeflow_folder):
        if not ef_folder.is_dir() or not is_ef_folder(ef_folder.name):
            continue

        png_paths = []
        InputEyeFlowParams = {"path": None, "content": None}

        png_folder = ef_folder / "png"
        if png_folder.exists():
            for sub in png_folder.rglob("*.png"):
                png_paths.append(str(sub))

        json_folder = ef_folder / "json"
        if json_folder.exists() and json_folder.is_dir():
            input_param = json_folder / "InputEyeFlowParams.json"
            if input_param.exists():
                content = safe_json_load(input_param)

                if content:
                    InputEyeFlowParams = {"path": str(input_param), "content": content}

        ef_data.append(
            {
                "ef_folder": ef_folder,
                "png_files": png_paths,
                "InputEyeFlowParams": InputEyeFlowParams,
            }
        )

    return ef_data


def find_version_in_log(file_path: Path) -> str | None:
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


def get_eyeflow_version(ef_folder: Path, hd_folder_name: str) -> str | None:
    # TODO: To implement better way

    ef_folder = Path(ef_folder)
    log_folder = ef_folder / "log"
    if not log_folder.exists() or not log_folder.is_dir():
        Logger.error(
            f"Eyeflow log folder does not exist: {log_folder}", tags="FILESYSTEM"
        )
        return None

    file_path_list = get_all_files_extension(log_folder, "txt")

    if not file_path_list:
        Logger.error(
            f"Eyeflow log file does not exist inside folder: {log_folder}",
            tags="FILESYSTEM",
        )
        return None

    if len(file_path_list) > 1:
        Logger.warn(
            f"More than one log file found inside {log_folder}", tags="FILESYSTEM"
        )

    # We take the first found
    file_path = file_path_list[0]
    # file_path = log_folder / f"{hd_folder_name}_log.txt"

    version = find_version_in_log(file_path)

    if not version:
        Logger.warn(
            f"No version string in log file: {file_path}",
            tags="FILESYSTEM",
        )
        return None

    return version


def find_all_holo_files(root_folder: Path) -> list[Path]:
    """
    Searches for all .holo files recursively from the root_path.
    Returns a list of unique, absolute file paths.
    """
    found_files = []
    search_paths = [root_folder]

    for path in search_paths:
        for dirpath, dirnames, filenames in os.walk(path):
            # Only keeps the folders that does not contain "_HD_"
            dirnames[:] = [d for d in dirnames if "_HD_" not in d]

            for filename in filenames:
                if filename.endswith(".holo"):
                    # absolute_path = os.path.abspath(os.path.join(dirpath, filename))
                    absolute_path = (Path(dirpath) / filename).resolve()
                    found_files.append(absolute_path)

    return found_files


def find_all_hd_folders_from_holo(holo_file_path: Path) -> dict[int, Path]:
    source_filename = os.path.basename(holo_file_path)
    base_name = os.path.splitext(source_filename)[0]
    hd_pattern = re.compile(f"^{re.escape(base_name)}_HD_(\\d+)$")

    hd_folders = {}

    parent_dir = os.path.dirname(holo_file_path)
    for entry in os.scandir(parent_dir):
        if not entry.is_dir():
            continue

        match = hd_pattern.match(entry.name)
        if match:
            number = int(match.group(1))
            hd_folders[number] = Path(entry.path)

    return hd_folders


def check_folder_name_format(path: Path) -> bool:
    folder_name = os.path.basename(path)
    date_pattern = re.compile(r"^\d{6}.*$")

    return date_pattern.match(folder_name) is not None


def parse_folder_date(path: Path) -> datetime.date:
    folder_name = os.path.basename(path)
    date_pattern = re.compile(r"^(\d{2})(\d{2})(\d{2}).*$")

    matchs = date_pattern.match(folder_name)
    if not matchs:  # or len(matchs.groups()) == 3:
        Logger.error(
            f"{path} does not match date format, defaulting to creation date of folder"
        )
        return datetime.date.fromtimestamp(os.path.getctime(path))

    try:
        return datetime.date(
            2000 + int(matchs.group(1)), int(matchs.group(2)), int(matchs.group(3))
        )
    except Exception as _:
        Logger.error(f"Wrong date format: {folder_name} ({matchs.groups})")
        return datetime.date.fromtimestamp(os.path.getctime(path))


def get_last_update(path: Path) -> datetime.datetime | None:
    if not path.exists():
        Logger.error(f"Path does not exists to get its update: {path}")
        return None

    return datetime.datetime.fromtimestamp(os.path.getmtime(path))


def get_measure_tag(path: Path) -> str | None:
    try:
        tag = path.name.split("_")[1]
        return tag
    except Exception as _:
        return None


def get_render_number(path: Path) -> int | None:
    try:
        return int(path.name.split("_")[-1])
    except Exception as _:
        return None


def get_report_pdf(ef_folder: Path) -> Path | None:
    ef_folder = Path(ef_folder)
    pdf_folder = ef_folder / "pdf"

    if not os.path.isdir(pdf_folder):
        return None

    pdfs = os.listdir(pdf_folder)
    if not pdfs or len(pdfs) == 0:
        return None

    # Need to change in case of more than one pdf
    return pdf_folder / pdfs[0]


def json_dump_nullable(text: str | None):
    if text:
        return json.dumps(text)

    return None


def get_all_files_extension(folder: Path, extension: str) -> list[Path]:
    """
    Retrieves all files with a specified extension from a folder.

    Args:
        folder (Path): A Path object representing the folder to search in.
        extension (str): The file extension to search for (e.g., 'txt', 'pdf').

    Returns:
        list[Path]: A list of Path objects for all files that match the given extension.
    """
    return list(folder.glob(f"*.{extension}"))


def process_date_folder(date_folder: Path) -> tuple[list, list, list]:
    """
    Scans a single date folder and gathers data for .holo, HD, and EF files.
    This function is designed to be run in a separate process.
    It does NOT interact with the database.
    """
    if not check_folder_name_format(date_folder) or not safe_isdir(date_folder):
        Logger.info(f"Skipping: {date_folder}", "SKIP")
        return ([], [], [])

    Logger.info(f"Processing folder: {date_folder.name}", "WORKER")

    holo_data_to_insert = []
    hd_data_to_insert = []
    ef_data_to_insert = []

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

        hd_folders = find_all_hd_folders_from_holo(holo_file)
        for render_number, hd_folder in hd_folders.items():
            rendering_params_json = (
                hd_folder / f"{hd_folder.name}_RenderingParameters.json"
            )

            rendering_params = (
                safe_json_load(rendering_params_json)
                if rendering_params_json.exists()
                else None
            )

            version_text = safe_file_read(hd_folder / "version.txt")

            hd_entry = {
                "holo_id": temp_holo_id,
                "path": hd_folder.absolute().as_posix(),
                "render_number": render_number,
                "rendering_parameters": json_dump_nullable(rendering_params),
                "version": version_text,
                "updated_at": get_last_update(hd_folder),
            }

            # We need a temporary ID to link the data before it's in the DB
            # It will be later replaced by the actual Id row of table
            temp_hd_id = str(hd_folder.absolute())
            hd_data_to_insert.append((temp_hd_id, hd_entry))

            eyeflow_folder = hd_folder / "eyeflow"
            if eyeflow_folder.exists():
                ef_renders = get_ef_folders_data(eyeflow_folder)
                for ef in ef_renders:
                    ef_entry = {
                        "hd_id": temp_hd_id,
                        "render_number": get_render_number(ef["ef_folder"]),
                        "path": ef["ef_folder"],
                        "input_parameters": json_dump_nullable(
                            ef["InputEyeFlowParams"]["content"]
                        ),
                        "version": get_eyeflow_version(ef["ef_folder"], hd_folder.name),
                        "report_path": get_report_pdf(ef["ef_folder"]),
                        "updated_at": get_last_update(ef["ef_folder"]),
                    }
                    ef_data_to_insert.append(ef_entry)

    return (holo_data_to_insert, hd_data_to_insert, ef_data_to_insert)
