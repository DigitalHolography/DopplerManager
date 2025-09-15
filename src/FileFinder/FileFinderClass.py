import json

import src.FileFinder.FinderUtils as FinderUtils
from src.Logger.LoggerClass import Logger
from src.Database.DBClass import DB


class FileFinder:
    def __init__(self, DBClass: DB):
        self.searchFolder = ""
        self.DBClass = DBClass

    def CreateDB(self) -> None:
        self.DBClass.create_table(
            "hd_data",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "hd_folder": "TEXT",
                "measure_tag": "TEXT",
                "render_number": "INTEGER",
                "rendering_parameters": "TEXT",
                "version_text": "TEXT",
            },
        )

        self.DBClass.create_table(
            "raw_files",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "hd_id": "INTEGER",
                "path": "TEXT",
                "size_MB": "INTEGER",
                "FOREIGN KEY (hd_id)": "REFERENCES hd_data (id)",
            },
        )

        self.DBClass.create_table(
            "ef_data",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "hd_id": "INTEGER",
                "ef_folder": "TEXT",
                "version_text": "TEXT",
                "json_path": "TEXT",
                "json_content": "TEXT",
                "FOREIGN KEY (hd_id)": "REFERENCES hd_data (id)",
            },
        )

        self.DBClass.create_table(
            "ef_pngs",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "ef_id": "INTEGER",
                "path": "TEXT",
                "type": "INTEGER",
                "FOREIGN KEY (ef_id)": "REFERENCES ef_data (id)",
            },
        )

    def ClearDB(self) -> None:
        # Should really change this to delete the file instead of DROPping tables
        table_names = ["ef_pngs", "raw_files", "ef_data", "hd_data"]
        for table in table_names:
            self.DBClass.SQLconnect.execute(f"DROP TABLE IF EXISTS {table}")
        self.DBClass.SQLconnect.commit()
        self.CreateDB()

    def InsertHDdata(
        self,
        hd_folder: str,
        measure_tag: str,
        render_number: int,
        rendering_parameters: str,
        version_text: str,
    ) -> int | None:

        return self.DBClass.insert(
            "hd_data",
            {
                "hd_folder": hd_folder,
                "measure_tag": measure_tag,
                "render_number": render_number,
                "rendering_parameters": rendering_parameters,
                "version_text": version_text,
            },
        )

    def InsertRawFile(self, hd_id: int, path: str, size_MB: int) -> int | None:
        return self.DBClass.insert(
            "raw_files", {"hd_id": hd_id, "path": path, "size_MB": size_MB}
        )

    def InsertEFdata(
        self,
        hd_id: int,
        ef_folder: str,
        version_text: str,
        json_path: str,
        json_content: str,
    ) -> int | None:
        return self.DBClass.insert(
            "ef_data",
            {
                "hd_id": hd_id,
                "ef_folder": ef_folder,
                "version_text": version_text,
                "json_path": json_path,
                "json_content": json_content,
            },
        )

    def InsertEFpng(self, ef_id: int, path: str, type: str) -> int | None:
        return self.DBClass.insert(
            "ef_pngs", {"ef_id": ef_id, "path": path, "type": type}
        )

    def Findfiles(self, root_dir: str):
        # cursor = self.SQLconnect.cursor()

        for date_folder in FinderUtils.safe_iterdir(root_dir):
            Logger.info(f"Scanning date folder: {date_folder}")
            if not FinderUtils.safe_isdir(date_folder):
                continue

            for hd_folder in FinderUtils.safe_iterdir(date_folder):
                if not hd_folder.is_dir() or not FinderUtils.is_hd_folder(
                    hd_folder.name
                ):
                    continue

                # --- HD data ---
                rendering_params = None

                raw_folder = hd_folder / "raw"
                raw_data = FinderUtils.get_raw_data(raw_folder)

                rendering_json = hd_folder / (
                    f"{hd_folder.name}_RenderingParameters.json"
                )
                if rendering_json.exists():
                    rendering_params = FinderUtils.safe_json_load(rendering_json)

                version_file = hd_folder / "version.txt"
                version_text = FinderUtils.safe_file_read(version_file)
                if version_text is None:
                    version_text = ""
                try:
                    measure_tag = hd_folder.name.split("_")[1]
                except IndexError:
                    measure_tag = "UNKNOWN"

                # --- EF data ---
                eyeflow_folder = hd_folder / "eyeflow"
                ef_data = []
                if eyeflow_folder.exists():
                    ef_data = FinderUtils.get_ef_folders_data(eyeflow_folder)

                hd_folder_path = hd_folder.absolute().as_posix()
                hd_rowId = self.InsertHDdata(
                    hd_folder_path,
                    measure_tag,
                    FinderUtils.get_num_after_hd(hd_folder_path),
                    json.dumps(rendering_params),
                    version_text,
                )

                if hd_rowId is None:
                    Logger.error(
                        f"Failed to insert HD data for folder: {hd_folder}",
                        tags="DATABASE",
                    )
                    continue

                for raw in raw_data:
                    last_row = self.InsertRawFile(
                        hd_id=hd_rowId, path=raw["path"], size_MB=raw["size"]
                    )

                    if last_row is None:
                        Logger.error(
                            f"Failed to insert raw_data: {raw['path']}", tags="DATABASE"
                        )
                        continue

                for ef in ef_data:
                    last_row = self.InsertEFdata(
                        hd_id=hd_rowId,
                        ef_folder=ef["ef_folder"],
                        version_text=FinderUtils.get_eyeflow_version(
                            ef["ef_folder"], hd_folder.name
                        ),
                        json_path=ef["InputEyeFlowParams"]["path"],
                        json_content=json.dumps(ef["InputEyeFlowParams"]["content"]),
                    )

                    if last_row is None:
                        Logger.error(
                            f"Failed to insert EF data for folder: {ef['ef_folder']}",
                            tags="DATABASE",
                        )
                        continue