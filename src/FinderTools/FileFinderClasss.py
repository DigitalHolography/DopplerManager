import FinderUtils
import sqlite3
from src.Logger.LoggerClass import Logger

class FileFinder:
    def __init__(self, DB_PATH):
        # Folder that will be searched
        self.searchFolder = ""
        self.DB_PATH = DB_PATH
        self.SQLconnect = sqlite3.connect(DB_PATH)

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
        data = []
        for date_folder in FinderUtils.safe_iterdir(root_dir):
            Logger.info(f"Scanning date folder: {date_folder}")
            if not FinderUtils.safe_isdir(date_folder):
                continue
            
            for hd_folder in FinderUtils.safe_iterdir(date_folder):
                if not hd_folder.is_dir() or not FinderUtils.is_hd_folder(hd_folder.name):
                    continue

                # --- HD data ---
                rendering_params = None
                version_text = None

                raw_folder = hd_folder / "raw"
                raw_data = FinderUtils.get_raw_data(raw_folder)

                rendering_json = hd_folder / f"{hd_folder}_RenderingParameters.json"
                if rendering_json.exists():
                    rendering_params = FinderUtils.safe_json_load(rendering_json)

                version_file = hd_folder / "version.txt"
                version_text = FinderUtils.safe_file_read(version_file)

                # --- EF data ---
                eyeflow_folder = hd_folder / "eyeflow"
                ef_data = []

                if eyeflow_folder.exists():
                    ef_data = FinderUtils.get_ef_folders_data(eyeflow_folder)

                data.append({
                    "hd_folder": str(hd_folder),
                    "raw_files": raw_data,
                    "rendering_parameters": rendering_params,
                    "version_text": version_text,
                    "ef_data": ef_data
                })
