import os
import json

from pathlib import Path
from src.Logger.LoggerClass import Logger


def is_hd_folder(name: str):
    return "_HD_" in name


def is_ef_folder(name: str):
    return "_EF_" in name


def get_file_size(file_path: Path | str):
    try:
        return os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
    except Exception:
        return None


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
        # print(f"Access denied or error reading directory: {path} – {e}")
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
        # print(f"Access denied or error reading directory: {path} – {e}")
        return []


def get_raw_data(raw_folder: Path) -> list[dict]:
    raw_data = []

    if raw_folder.exists():
        raw_files = list(raw_folder.glob("*.raw"))  # To check if needed
        h5_files = list(raw_folder.glob("*.h5"))
        for f in raw_files + h5_files:
            raw_data.append({"path": str(f), "size": get_file_size(f)})

    return raw_data


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
                "ef_folder": str(ef_folder),
                "png_files": png_paths,
                "InputEyeFlowParams": InputEyeFlowParams,
            }
        )

    return ef_data


def scan_directories(root_dir: str):
    data = []

    for date_folder in safe_iterdir(root_dir):
        Logger.info(f"Scanning date folder: {date_folder}")
        if not safe_isdir(date_folder):
            continue

        for hd_folder in safe_iterdir(date_folder):
            if not hd_folder.is_dir() or not is_hd_folder(hd_folder.name):
                continue

            # --- HD data ---
            rendering_params = None
            version_text = None

            raw_folder = hd_folder / "raw"
            raw_data = get_raw_data(raw_folder)

            rendering_json = hd_folder / f"{hd_folder}_RenderingParameters.json"
            if rendering_json.exists():
                rendering_params = safe_json_load(rendering_json)

            version_file = hd_folder / "version.txt"
            version_text = safe_file_read(version_file)

            # --- EF data ---
            eyeflow_folder = hd_folder / "eyeflow"
            ef_data = []

            if eyeflow_folder.exists():
                ef_data = get_ef_folders_data(eyeflow_folder)

            data.append(
                {
                    "hd_folder": str(hd_folder),
                    "raw_files": raw_data,
                    "rendering_parameters": rendering_params,
                    "version_text": version_text,
                    "ef_data": ef_data,
                }
            )

    return data


def get_file_name_without_hd(folder_path):
    # Get the base name of the file from the folder path
    file_name = os.path.basename(folder_path)

    # Find the index of '_HD_'
    hd_index = file_name.find("_HD_")

    if hd_index != -1:
        # Slice the string up to '_HD_'
        file_name = file_name[:hd_index]

    return file_name


def get_num_after_hd(file_path) -> int:
    # Get the base name of the file from the file path
    file_name = os.path.basename(file_path)

    # Use regular expression to find the pattern HD_[any number]_
    hd_index = file_name.find("_HD_")

    if hd_index != -1:
        return file_name[hd_index:]
    return -1


def get_eyeflow_version(ef_folder: Path, hd_folder_name: str) -> str:
    # TODO: To implement better way

    # Logger.debug(f"Getting eyeflow version for EF folder: {ef_folder}, HD folder name: {hd_folder_name}", tags="FILESYSTEM")

    log_folder = Path(ef_folder) / "log"
    if not log_folder.exists() or not log_folder.is_dir():
        Logger.error(
            f"Eyeflow log folder does not exist: {log_folder}", tags="FILESYSTEM"
        )
        return "None"

    file_path = log_folder / f"{hd_folder_name}_log.txt"

    if not file_path.exists() or not file_path.is_file():
        Logger.error(f"Eyeflow log file does not exist: {file_path}", tags="FILESYSTEM")
        return "None"

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find indices of lines that are bars (lines containing only '=' chars)
    bar_lines = [
        i for i, line in enumerate(lines) if line.strip() and set(line.strip()) == {"="}
    ]

    if len(bar_lines) < 2:
        Logger.error(
            f"Eyeflow log file does not contain block: {file_path}", tags="FILESYSTEM"
        )
        return "None"

    # Get the last two bars to find the last block
    start = bar_lines[-2]
    end = bar_lines[-1]

    # Extract lines between the bars (excluding the bars themselves)
    block_lines = lines[start + 1 : end]

    # Join and strip trailing spaces/newlines
    return "".join(block_lines).strip()
