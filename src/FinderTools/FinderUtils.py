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
        Logger.error(f"Access denied or error reading json: {file_path} – {e}", tags="FILESYSTEM")
        return None

def safe_file_read(file_path: Path | str):
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        Logger.error(f"Access denied or error reading file: {file_path} – {e}", tags="FILESYSTEM")
        return None

def safe_isdir(path: Path | str):
    try:
        path = Path(path)
        return path.is_dir()
    except (PermissionError, OSError) as e:
        # print(f"Access denied or error reading directory: {path} – {e}")
        Logger.error(f"Access denied or error reading directory: {path} – {e}", tags="FILESYSTEM")
        return False

def safe_iterdir(path: Path | str):
    try:
        path = Path(path)
        if safe_isdir(path):
          return list(path.iterdir())
        else:
            return []
    except (PermissionError, OSError) as e:
        Logger.error(f"Access denied or error reading directory: {path} – {e}", tags="FILESYSTEM")
        # print(f"Access denied or error reading directory: {path} – {e}")
        return []

def get_raw_data(raw_folder: Path) -> list[dict]:
    raw_data = []

    if raw_folder.exists():
        raw_files = list(raw_folder.glob("*.raw")) # To check if needed
        h5_files = list(raw_folder.glob("*.h5"))
        for f in raw_files + h5_files:
            raw_data.append({
                "path": str(f),
                "size": get_file_size(f)
            })

    return raw_data


def get_ef_folders_data(eyeflow_folder: Path) -> list[dict]:
    ef_data = []

    for ef_folder in safe_iterdir(eyeflow_folder):
        if not ef_folder.is_dir() or not is_ef_folder(ef_folder.name):
            continue

        png_paths = []
        json_data = []

        png_folder = ef_folder / "png"
        if png_folder.exists():
            for sub in png_folder.rglob("*.png"):
                png_paths.append(str(sub))

        json_folder = ef_folder / "json"
        if json_folder.exists():
            for json_file in json_folder.glob("*.json"):
                j = safe_json_load(json_file)
                if j:
                    json_data.append({"content" : j,
                                        "name": json_file.name})

        ef_data.append({
            "ef_folder": str(ef_folder),
            "png_files": png_paths,
            "json_objects": json_data
        })

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

            data.append({
                "hd_folder": str(hd_folder),
                "raw_files": raw_data,
                "rendering_parameters": rendering_params,
                "version_text": version_text,
                "ef_data": ef_data
            })
    
    return data

def get_file_name_without_hd(folder_path):
    # Get the base name of the file from the folder path
    file_name = os.path.basename(folder_path)

    # Find the index of '_HD_'
    hd_index = file_name.find('_HD_')

    if hd_index != -1:
        # Slice the string up to '_HD_'
        file_name = file_name[:hd_index]

    return file_name

def get_eyeflow_version(ef_folder: Path) -> str:
    # TODO: To implement
    return ""