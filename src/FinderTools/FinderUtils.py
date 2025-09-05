import os
import json
from pathlib import Path
from Logger import Logger

def is_hd_folder(name: str):
    return "_HD_" in name

def is_ef_folder(name: str):
    return "_EF_" in name

def get_file_size(file_path: str):
    try:
        return os.path.getsize(file_path)/ (1024 * 1024)  # Size in MB
    except Exception:
        return None

def safe_json_load(file_path: str):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def safe_file_read(file_path: str):
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception:
        return None

def safe_isdir(path):
    try:
        return path.is_dir()
    except (PermissionError, OSError) as e:
        # print(f"Access denied or error reading directory: {path} – {e}")
        Logger().error(f"Access denied or error reading directory: {path} – {e}", tags="Filesystem")
        return False

def safe_iterdir(path: str):
    try:
        if safe_isdir(Path(path)):
          return list(path.iterdir())
    except (PermissionError, OSError) as e:
        print(f"Access denied or error reading directory: {path} – {e}")
        return []


def scan_directories(root_dir: str):
    data = []
    
    for date_folder in safe_iterdir(Path(root_dir)):
        print(f"Scanning date folder: {date_folder}")
        if not safe_isdir(Path(date_folder)):
            continue
        
        for hd_folder in safe_iterdir(Path(date_folder)):
            if not hd_folder.is_dir() or not is_hd_folder(hd_folder.name):
                continue

            # --- HD data ---
            raw_data = []
            rendering_params = None
            version_text = None

            raw_folder = hd_folder / "raw"
            if raw_folder.exists():
                raw_files = list(raw_folder.glob("*.raw")) # To check
                h5_files = list(raw_folder.glob("*.h5"))
                for f in raw_files + h5_files:
                    raw_data.append({
                        "path": str(f),
                        "size": get_file_size(f)
                    })


            rendering_json = hd_folder / f"{hd_folder}_RenderingParameters.json"
            # for rendering_json in hd_folder.glob(f"RenderingParameters.json"):
            if rendering_json.exists():
                rendering_params = safe_json_load(rendering_json)

            version_file = hd_folder / "version.txt"
            version_text = safe_file_read(version_file)

            # --- EF data ---
            eyeflow_folder = hd_folder / "eyeflow"
            ef_data = []

            if eyeflow_folder.exists():
                for ef_folder in safe_iterdir(Path(eyeflow_folder)):
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

            data.append({
                "hd_folder": str(hd_folder),
                "raw_files": raw_data,
                "rendering_parameters": rendering_params,
                "version_text": version_text,
                "ef_data": ef_data
            })
    
    return data

#print(timeit.timeit('Path("Y:/250604").iterdir()', number=10000, setup="from pathlib import Path"))
#print(timeit.timeit('walk("Y:/250604")', number=10000, setup="from os import walk"))

