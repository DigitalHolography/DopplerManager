import os
import sqlite3
import json
from Tools.utils import *

from pathlib import Path

def is_hd_folder(name):
    return "_HD_" in name

def is_ef_folder(name):
    return "_EF_" in name

def get_file_size(file_path):
    try:
        return os.path.getsize(file_path)/ (1024 * 1024)  # Size in MB
    except Exception:
        return None

def safe_json_load(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception:
        return None
    
def safe_iterdir(path):
    try:
        if path.is_dir():
          return list(path.iterdir())
    except (PermissionError, OSError) as e:
        print(f"Access denied or error reading directory: {path} – {e}")
        return []
    
def safe_isdir(path):
    try:
        if path.is_dir():
          return path.is_dir()
    except (PermissionError, OSError) as e:
        print(f"Access denied or error reading directory: {path} – {e}")
        return False

def scan_directories(root_dir):
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
                raw_files = list(raw_folder.glob("*.raw"))
                h5_files = list(raw_folder.glob("*.h5"))
                for f in raw_files + h5_files:
                    raw_data.append({
                        "path": str(f),
                        "size": get_file_size(f)
                    })

            for rendering_json in hd_folder.glob("RenderingParameters*.json"):
              if rendering_json.exists():
                  rendering_params = safe_json_load(rendering_json)

            version_file = hd_folder / "version.txt"
            if version_file.exists():
                try:
                    with open(version_file, "r") as f:
                        version_text = f.read()
                except Exception:
                    pass

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

def create_database(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS hd_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hd_folder TEXT,
            measure_tag TEXT,
            rendering_parameters TEXT,
            version_text TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS raw_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hd_id INTEGER,
            path TEXT,
            size_MB INTEGER,
            FOREIGN KEY (hd_id) REFERENCES hd_data (id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS ef_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hd_id INTEGER,
            ef_folder TEXT,
            version_text TEXT,
            FOREIGN KEY (hd_id) REFERENCES hd_data (id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS ef_pngs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ef_id INTEGER,
            path TEXT,
            type TEXT,
            FOREIGN KEY (ef_id) REFERENCES ef_data (id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS ef_jsons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ef_id INTEGER,
            json_content TEXT,
            json_name TEXT,
            FOREIGN KEY (ef_id) REFERENCES ef_data (id)
        )
    ''')

    conn.commit()
    return conn

def store_data(conn, data):
    c = conn.cursor()

    for hd in data:
        measure_tag = get_file_name_without_hd(hd["hd_folder"])
        c.execute("INSERT INTO hd_data (hd_folder, rendering_parameters, version_text, measure_tag) VALUES (?, ?, ?, ?)",
                  (hd["hd_folder"], json.dumps(hd["rendering_parameters"]), hd["version_text"], measure_tag))
        hd_id = c.lastrowid

        for raw in hd["raw_files"]:
            c.execute("INSERT INTO raw_files (hd_id, path, size_MB) VALUES (?, ?, ?)",
                      (hd_id, raw["path"], raw["size"]))

        for ef in hd["ef_data"]:
            for log_file_path in (Path(ef["ef_folder"]) / "log").glob("*log.txt"):
                if log_file_path.exists():
                    version_text = extract_last_block_between_bars(log_file_path)
              
            c.execute("INSERT INTO ef_data (hd_id, ef_folder, version_text) VALUES (?, ?, ?)",
                      (hd_id, ef["ef_folder"], version_text))
            ef_id = c.lastrowid

            for png_path in ef["png_files"]:
                output_type = get_name_after_hd(png_path)
                c.execute("INSERT INTO ef_pngs (ef_id, path, type) VALUES (?, ?, ?)",
                          (ef_id, png_path, output_type))

            for json_obj in ef["json_objects"]:
                c.execute("INSERT INTO ef_jsons (ef_id, json_content, json_name) VALUES (?, ?, ?)",
                          (ef_id, json.dumps(json_obj["content"]), json_obj["name"]))

    conn.commit()

def main():
    ROOT_DIR = "Y:\\"  # Change to the real root
    DB_PATH = "collected_data.db"

    print("Scanning directories...")
    data = scan_directories(ROOT_DIR)

    print(f"Found {len(data)} HD folders.")
    
    print("Creating database...")
    conn = create_database(DB_PATH)

    print("Storing data...")
    store_data(conn, data)

    print("Done.")
    conn.close()

if __name__ == "__main__":
    main()
