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
        Logger.error(
            f"Access denied or error reading json: {file_path} – {e}", tags="FILESYSTEM"
        )
        return None


def safe_file_read(file_path: Path | str):
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        Logger.error(
            f"Access denied or error reading file: {file_path} – {e}", tags="FILESYSTEM"
        )
        return None


def safe_isdir(path: Path | str):
    try:
        path = Path(path)
        return path.is_dir()
    except (PermissionError, OSError) as e:
        Logger.error(
            f"Access denied or error reading directory: {path} – {e}", tags="FILESYSTEM"
        )
        return False


def safe_iterdir(path: Path | str):
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


def get_eyeflow_version(ef_folder: Path, hd_folder_name: str) -> str | None:
    # TODO: To implement better way

    # Logger.debug(f"Getting eyeflow version for EF folder: {ef_folder}, HD folder name: {hd_folder_name}", tags="FILESYSTEM")

    ef_folder = Path(ef_folder)
    log_folder = ef_folder / "log"
    if not log_folder.exists() or not log_folder.is_dir():
        Logger.error(
            f"Eyeflow log folder does not exist: {log_folder}", tags="FILESYSTEM"
        )
        return None

    file_path = log_folder / f"{hd_folder_name}_log.txt"

    if not file_path.exists() or not file_path.is_file():
        Logger.error(f"Eyeflow log file does not exist: {file_path}", tags="FILESYSTEM")
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find indices of lines that are bars (lines containing only '=' chars)
    bar_lines = [
        i for i, line in enumerate(lines) if line.strip() and set(line.strip()) == {"="}
    ]

    if len(bar_lines) < 4:
        Logger.error(
            f"Eyeflow log file does not contain block: {file_path}", tags="FILESYSTEM"
        )
        return None

    # Get the second block
    start = bar_lines[2]
    end = bar_lines[3]

    # Extract lines between the bars (excluding the bars themselves)
    block_lines = lines[start + 1 : end]

    match len(block_lines):
        # Got the "ERROR" (ver. si not found)
        case 1:
            return None

        # Got the release version
        case 2:  # Release PulseWave
            return block_lines[1]

        case 3:  # Release Eyeflow
            return block_lines[0].split(" ")[-1]

        case 4:  # dev Eyeflow
            return block_lines[-1].split(":")[1][1:]

        case _:
            Logger.error(
                f"Wrong Split to block lines for {ef_folder} ({block_lines})",
                "EYEFLOW",
            )


def find_all_holo_files(root_folder: Path) -> list[Path]:
    """
    Searches for all .holo files recursively from the root_path.
    Returns a list of unique, absolute file paths.
    """
    found_files = []
    search_paths = [root_folder]

    for path in search_paths:
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                if filename.endswith(".holo"):
                    absolute_path = os.path.abspath(os.path.join(dirpath, filename))
                    found_files.append(absolute_path)

    return found_files


def find_all_hd_folders_from_holo(holo_file_path: Path) -> dict[int, Path]:
    source_filename = os.path.basename(holo_file_path)
    base_name = os.path.splitext(source_filename)[0]
    hd_pattern = re.compile(f"^{re.escape(base_name)}_HD_(\\d+)$")

    hd_folders = {}

    parent_dir = os.path.dirname(holo_file_path)
    for f in os.listdir(parent_dir):
        f_path = os.path.join(parent_dir, f)
        if not os.path.isdir(f_path):
            continue

        match = hd_pattern.match(f)
        if match:
            number = int(match.group(1))
            hd_folders[number] = Path(f_path)

    return hd_folders


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


def get_meusure_tag(path: Path) -> str | None:
    try:
        return path.name.split("_")[1]
    except IndexError:
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
