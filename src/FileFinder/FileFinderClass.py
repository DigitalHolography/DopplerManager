import json

import src.FileFinder.FinderUtils as FinderUtils
from src.Logger.LoggerClass import Logger
from src.Database.DBClass import DB


class FileFinder:
    def __init__(self, DB: DB):
        self.searchFolder = ""
        self.DB = DB

    def CreateDB(self) -> None:
        self.DB.create_table(
            "holo_data",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "path": "VARCHAR(255) NOT NULL",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            },
        )

        self.DB.create_table(
            "hd_render",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "holo_id": "INTEGER NOT NULL",
                "path": "VARCHAR(255) NOT NULL",
                "tag": "VARCHAR(255) NOT NULL",
                "render_number": "INTEGER NOT NULL",
                "rendering_parameters": "TEXT",
                "version": "VARCHAR(255)",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (holo_id)": "REFERENCES holo_data (id)",
            },
        )

        self.DB.create_table(
            "ef_render",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "hd_id": "INTEGER NOT NULL",
                "render_number": "INTEGER NOT NULL",
                "path": "VARCHAR(255) NOT NULL",
                "input_parameters": "TEXT",
                "version": "VARCHAR(255)",
                "report_path": "VARCHAR(255)",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (hd_id)": "REFERENCES hd_render (id)",
            },
        )

    def ClearDB(self) -> None:
        # Should really change this to delete the file instead of DROPping tables
        table_names = ["ef_pngs", "raw_files", "ef_render", "hd_render"]
        for table in table_names:
            self.DB.SQLconnect.execute(f"DROP TABLE IF EXISTS {table}")
        self.DB.SQLconnect.commit()
        self.CreateDB()

    def InsertHDRender(
        self,
        holo_id: int,
        path: str,
        tag: str,
        render_number: int,
        rendering_parameters: str,
        version: str | None,
        updated_at: str | None,
    ) -> int | None:
        return self.DB.insert(
            "hd_render",
            {
                "holo_id": holo_id,
                "path": path,
                "tag": tag,
                "render_number": render_number,
                "rendering_parameters": rendering_parameters,
                "version": version,
                "updated_at": updated_at,
            },
        )

    def InsertHoloFile(self, hd_id: int, path: str) -> int | None:
        return self.DB.insert("holo_files", {"hd_id": hd_id, "path": path})

    def InsertEFRender(
        self,
        hd_id: int,
        render_number: int,
        path: str,
        input_parameters: str | None,
        version: str | None,
        report_path: str | None,
        created_at: str,
        updated_at: str,
    ) -> int | None:
        return self.DB.insert(
            "ef_render",
            {
                "hd_id": hd_id,
                "render_number": render_number,
                "path": path,
                "input_parameters": input_parameters,
                "version": version,
                "report_path": report_path,
                "created_at": created_at,
                "updated_at": updated_at,
            },
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
                ef_render = []
                if eyeflow_folder.exists():
                    ef_render = FinderUtils.get_ef_folders_data(eyeflow_folder)

                hd_folder_path = hd_folder.absolute().as_posix()
                hd_rowId = self.InsertHDRender(
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

                for ef in ef_render:
                    last_row = self.InsertEFRender(
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
