import datetime
from pathlib import Path

import src.FileFinder.FinderUtils as FinderUtils
from src.Logger.LoggerClass import Logger
from src.Database.DBClass import DB


class FileFinder:
    def __init__(self, DB: DB):
        self.searchFolder = ""
        self.DB = DB

    def CreateDB(self) -> None:
        tables = {
            "holo_data": {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "path": "VARCHAR(255) NOT NULL",
                "tag": "VARCHAR(255)",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            },
            "hd_render": {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "holo_id": "INTEGER NOT NULL",
                "path": "VARCHAR(255) NOT NULL",
                "render_number": "INTEGER",
                "rendering_parameters": "TEXT",
                "version": "VARCHAR(255)",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (holo_id)": "REFERENCES holo_data (id)",
            },
            "ef_render": {
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
        }

        for key, val in tables.items():
            self.DB.create_table(key, val)

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
        render_number: int | None,
        rendering_parameters: str | None,
        version: str | None,
        updated_at: datetime.datetime | None,
    ) -> int | None:
        return self.DB.insert(
            "hd_render",
            {
                "holo_id": holo_id,
                "path": path,
                "render_number": render_number,
                "rendering_parameters": rendering_parameters,
                "version": version,
                "updated_at": updated_at,
            },
        )

    def InsertHoloFile(
        self, path: Path, tag: str | None, created_at: datetime.date | None
    ) -> int | None:
        return self.DB.insert(
            "holo_data", {"path": str(path), "tag": tag, "created_at": created_at}
        )

    def InsertEFRender(
        self,
        hd_id: int,
        render_number: int | None,
        path: str,
        input_parameters: str | None,
        version: str | None,
        report_path: Path | None,
        updated_at: datetime.datetime | None,
    ) -> int | None:
        return self.DB.insert(
            "ef_render",
            {
                "hd_id": hd_id,
                "render_number": render_number,
                "path": str(path),
                "input_parameters": input_parameters,
                "version": version,
                "report_path": str(report_path) if report_path else None,
                "updated_at": updated_at,
            },
        )

    def Findfiles(self, root_dir: str):
        for date_folder in FinderUtils.safe_iterdir(root_dir):
            if not FinderUtils.check_folder_name_format(date_folder):
                Logger.info(f"Skipping: {date_folder}", "SKIP")
                continue

            Logger.info(f"Scanning date folder: {date_folder}")
            if not FinderUtils.safe_isdir(date_folder):
                continue

            # Search .holo
            holo_files = FinderUtils.find_all_holo_files(date_folder)

            for holo_file in holo_files:
                holo_id = self.InsertHoloFile(
                    path=holo_file,
                    tag=FinderUtils.get_measure_tag(Path(holo_file)),
                    created_at=FinderUtils.parse_folder_date(holo_file)
                )

                if not holo_id:
                    Logger.error(
                        f"Failed to insert .holo file in DB: {holo_file}",
                        tags="DATABASE",
                    )
                    continue

                hd_folders = FinderUtils.find_all_hd_folders_from_holo(holo_file)

                for render_number, hd_folder in hd_folders.items():
                    # --- HD data ---
                    rendering_params = None

                    rendering_json = hd_folder / (
                        f"{hd_folder.name}_RenderingParameters.json"
                    )
                    if rendering_json.exists():
                        rendering_params = FinderUtils.safe_json_load(rendering_json)

                    version_file = hd_folder / "version.txt"
                    version_text = FinderUtils.safe_file_read(version_file)

                    # --- EF data ---
                    eyeflow_folder = hd_folder / "eyeflow"
                    ef_render = []
                    if eyeflow_folder.exists():
                        ef_render = FinderUtils.get_ef_folders_data(eyeflow_folder)

                    hd_folder_path = hd_folder.absolute().as_posix()

                    hd_rowId = self.InsertHDRender(
                        holo_id=holo_id,
                        path=hd_folder_path,
                        render_number=render_number,
                        rendering_parameters=FinderUtils.json_dump_nullable(
                            rendering_params
                        ),
                        version=version_text,
                        updated_at=FinderUtils.get_last_update(Path(hd_folder_path)),
                    )

                    if hd_rowId is None:
                        Logger.error(
                            f"Failed to insert HD data for folder: {hd_folder}",
                            tags="DATABASE",
                        )
                        continue
                    for ef in ef_render:
                        last_row = self.InsertEFRender(
                            hd_id=hd_rowId,
                            render_number=FinderUtils.get_render_number(
                                ef["ef_folder"]
                            ),
                            path=ef["ef_folder"],
                            input_parameters=FinderUtils.json_dump_nullable(
                                ef["InputEyeFlowParams"]["content"]
                            ),
                            version=FinderUtils.get_eyeflow_version(
                                ef["ef_folder"], hd_folder.name
                            ),
                            report_path=FinderUtils.get_report_pdf(ef["ef_folder"]),
                            updated_at=FinderUtils.get_last_update(
                                Path(hd_folder_path)
                            ),
                        )

                        if last_row is None:
                            Logger.error(
                                f"Failed to insert EF data for folder: {ef['ef_folder']}",
                                tags="DATABASE",
                            )
                            continue
