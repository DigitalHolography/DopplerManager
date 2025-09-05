import src.FinderTools.FinderUtils as FinderUtils
import sqlite3
import json
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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ef_pngs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ef_id INTEGER,
                path TEXT,
                type TEXT,
                FOREIGN KEY (ef_id) REFERENCES ef_data (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ef_jsons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ef_id INTEGER,
                json_content TEXT,
                json_name TEXT,
                FOREIGN KEY (ef_id) REFERENCES ef_data (id)
            )
        ''')

    def InsertHDdata(self, hd_folder: str, measure_tag: str, rendering_parameters: str, version_text: str) -> int | None:
        cursor = self.SQLconnect.cursor()

        cursor.execute('''
            INSERT INTO hd_data (hd_folder, measure_tag, rendering_parameters, version_text)
            VALUES (?, ?, ?, ?)
        ''', (hd_folder, measure_tag, rendering_parameters, version_text))
        
        self.SQLconnect.commit()

        return cursor.lastrowid
    

    def InsertRawFile(self, hd_id: int, path: str, size_MB: int) -> int | None:
        cursor = self.SQLconnect.cursor()

        cursor.execute('''
            INSERT INTO raw_files (hd_id, path, size_MB)
            VALUES (?, ?, ?)
        ''', (hd_id, path, size_MB))
        
        self.SQLconnect.commit()

        return cursor.lastrowid

    def InsertEFdata(self, hd_id: int, ef_folder: str, version_text: str) -> int | None:
        cursor = self.SQLconnect.cursor()

        cursor.execute('''
            INSERT INTO ef_data (hd_id, ef_folder, version_text)
            VALUES (?, ?, ?)
        ''', (hd_id, ef_folder, version_text))
        
        self.SQLconnect.commit()

        return cursor.lastrowid
    
    def InsertEFpng(self, ef_id: int, path: str, type: str) -> int | None:
        cursor = self.SQLconnect.cursor()

        cursor.execute('''
            INSERT INTO ef_pngs (ef_id, path, type)
            VALUES (?, ?, ?)
        ''', (ef_id, path, type))
        
        self.SQLconnect.commit()

        return cursor.lastrowid
    
    def InsertEFjson(self, ef_id: int, json_content: str, json_name: str) -> int | None:
        cursor = self.SQLconnect.cursor()

        cursor.execute('''
            INSERT INTO ef_jsons (ef_id, json_content, json_name)
            VALUES (?, ?, ?)
        ''', (ef_id, json_content, json_name))
        
        self.SQLconnect.commit()

        return cursor.lastrowid

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

                raw_folder = hd_folder / "raw"
                raw_data = FinderUtils.get_raw_data(raw_folder)

                rendering_json = hd_folder / f"{hd_folder}_RenderingParameters.json"
                if rendering_json.exists():
                    rendering_params = FinderUtils.safe_json_load(rendering_json)

                version_file = hd_folder / "version.txt"
                version_text = FinderUtils.safe_file_read(version_file)
                if version_text is None:
                    version_text = ""

                # --- EF data ---
                eyeflow_folder = hd_folder / "eyeflow"
                ef_data = []

                if eyeflow_folder.exists():
                    ef_data = FinderUtils.get_ef_folders_data(eyeflow_folder)

                hd_rowId = self.InsertHDdata(
                    hd_folder.absolute().as_posix(), 
                    FinderUtils.get_file_name_without_hd(hd_folder), 
                    json.dumps(rendering_params), 
                    version_text)
                
                if hd_rowId is None:
                    Logger.error(f"Failed to insert HD data for folder: {hd_folder}", tags="DATABASE")
                    continue
                
                for raw in raw_data:
                    last_row = self.InsertRawFile(
                        hd_id = hd_rowId,
                        path = raw["path"],
                        size_MB = raw["size"]
                    )

                    if last_row is None:
                        Logger.error(f"Failed to insert raw_data: {raw["path"]}", tags="DATABASE")
                        continue

                for ef in ef_data:
                    last_row = self.InsertEFdata(
                        hd_id= hd_rowId,
                        ef_folder= ef["ef_folder"],
                        version_text= FinderUtils.get_eyeflow_version(ef["ef_folder"])
                    )

                    if last_row is None:
                        Logger.error(f"Failed to insert EF data for folder: {ef['ef_folder']}", tags="DATABASE")
                        continue

                # data.append({
                #     "hd_folder": str(hd_folder),
                #     "raw_files": raw_data,
                #     "rendering_parameters": rendering_params,
                #     "version_text": version_text,
                #     "ef_data": ef_data
                # })
