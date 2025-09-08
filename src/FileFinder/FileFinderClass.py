import sqlite3
import json
import src.FileFinder.FinderUtils as FinderUtils
from src.Logger.LoggerClass import Logger

class FileFinder:
    def __init__(self, db_connection):
        self.searchFolder = ""
        self.SQLconnect = db_connection

    def CreateDB(self) -> None:
        cursor = self.SQLconnect.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hd_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hd_folder TEXT,
                measure_tag TEXT,
                rendering_parameters TEXT,
                version_text TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS raw_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hd_id INTEGER,
                path TEXT,
                size_MB INTEGER,
                FOREIGN KEY (hd_id) REFERENCES hd_data (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ef_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hd_id INTEGER,
                ef_folder TEXT,
                version_text TEXT,
                FOREIGN KEY (hd_id) REFERENCES hd_data (id)
            )
        ''')


    def Findfiles(self, root_dir: str):
        cursor = self.SQLconnect.cursor()
        
        for date_folder in FinderUtils.safe_iterdir(root_dir):
            Logger.info(f"Scanning date folder: {date_folder}")
            if not FinderUtils.safe_isdir(date_folder):
                continue
            
            for hd_folder in FinderUtils.safe_iterdir(date_folder):
                if not hd_folder.is_dir() or not FinderUtils.is_hd_folder(hd_folder.name):
                    continue

                # --- HD data ---
                raw_folder = hd_folder / "raw"
                raw_data = FinderUtils.get_raw_data(raw_folder)

                rendering_json_path = hd_folder / f"{hd_folder.name}_RenderingParameters.json"
                rendering_params = FinderUtils.safe_json_load(rendering_json_path)
                rendering_params_str = json.dumps(rendering_params) if rendering_params else None

                version_file = hd_folder / "version.txt"
                version_text = FinderUtils.safe_file_read(version_file)

                # Simple parsing for measure_tag from folder name like "date_TAG_HD_..."
                try:
                    measure_tag = hd_folder.name.split('_')[1]
                except IndexError:
                    measure_tag = "UNKNOWN"

                # --- EF data ---
                eyeflow_folder = hd_folder / "eyeflow"
                ef_data = []
                if eyeflow_folder.exists():
                    ef_data = FinderUtils.get_ef_folders_data(eyeflow_folder)

                # --- DB Insertion ---
                # 1. Insert into hd_data
                cursor.execute('''
                    INSERT INTO hd_data (hd_folder, measure_tag, rendering_parameters, version_text)
                    VALUES (?, ?, ?, ?)
                ''', (str(hd_folder), measure_tag, rendering_params_str, version_text))
                
                hd_id = cursor.lastrowid

                # 2. Insert into raw_files
                for raw_file in raw_data:
                    cursor.execute('''
                        INSERT INTO raw_files (hd_id, path, size_MB) VALUES (?, ?, ?)
                    ''', (hd_id, raw_file['path'], raw_file['size']))

                # 3. Insert into ef_data
                for ef in ef_data:
                    cursor.execute('''
                        INSERT INTO ef_data (hd_id, ef_folder, version_text) VALUES (?, ?, ?)
                    ''', (hd_id, ef['ef_folder'], ef.get('version_text')))

                self.SQLconnect.commit()
                Logger.info(f"Successfully added to DB: {hd_folder.name}")