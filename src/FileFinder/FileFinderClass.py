import datetime
import multiprocessing
from pathlib import Path

import src.FileFinder.FinderUtils as FinderUtils
from src.Logger.LoggerClass import Logger
from src.Database.DBClass import DB
from src.Utils.ParamsLoader import ConfigManager
from src.FileFinder.ReportGen import generate_report


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
            "preview_doppler_video": {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "holo_id": "INTEGER NOT NULL",
                "path": "VARCHAR(255) NOT NULL",
                "FOREIGN KEY (holo_id)": "REFERENCES holo_data (id) ON DELETE CASCADE",
            },
            "hd_render": {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "holo_id": "INTEGER NOT NULL",
                "path": "VARCHAR(255) NOT NULL",
                "render_number": "INTEGER NOT NULL",
                "rendering_parameters": "TEXT",
                "raw_h5_path": "VARCHAR(255)",
                "version": "VARCHAR(255)",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (holo_id)": "REFERENCES holo_data (id) ON DELETE CASCADE",
            },
            "ef_render": {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "hd_id": "INTEGER NOT NULL",
                "render_number": "INTEGER NOT NULL",
                "path": "VARCHAR(255) NOT NULL",
                "input_parameters": "TEXT",
                "version": "VARCHAR(255)",
                "report_path": "VARCHAR(255)",
                "h5_output": "VARCHAR(255)",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (hd_id)": "REFERENCES hd_render (id) ON DELETE CASCADE",
            },
        }

        for key, val in tables.items():
            self.DB.create_table(key, val)

    def ClearDB(self) -> None:
        self.DB.clear_db()  # Is fully empty
        self.CreateDB()  # Adds the tables

    def InsertHDRender(
        self,
        holo_id: int,
        path: Path,
        render_number: int | None,
        rendering_parameters: str | None,
        raw_h5_path: Path | None,
        version: str | None,
        updated_at: datetime.datetime | None,
    ) -> int | None:
        return self.DB.insert(
            "hd_render",
            {
                "holo_id": holo_id,
                "path": FinderUtils.parse_path(path),
                "render_number": render_number,
                "rendering_parameters": rendering_parameters,
                "raw_h5_path": FinderUtils.parse_path(raw_h5_path),
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
        path: Path,
        input_parameters: str | None,
        version: str | None,
        report_path: Path | None,
        h5_output: Path | None,
        updated_at: datetime.datetime | None,
    ) -> int | None:
        return self.DB.insert(
            "ef_render",
            {
                "hd_id": hd_id,
                "render_number": render_number,
                "path": FinderUtils.parse_path(path),
                "input_parameters": input_parameters,
                "version": version,
                "report_path": FinderUtils.parse_path(report_path),
                "h5_output": FinderUtils.parse_path(h5_output),
                "updated_at": updated_at,
            },
        )

    def InsertPreviewVideo(self, holo_id: int, path: Path) -> int | None:
        return self.DB.insert(
            "preview_doppler_video",
            {
                "holo_id": holo_id,
                "path": FinderUtils.parse_path(path),
            },
        )

    def Findfiles(self, root_dir: str, callback_bar=None, use_parallelism=True):
        date_folders = list(FinderUtils.safe_iterdir(root_dir))
        total_folders = len(date_folders)

        results = []

        if use_parallelism:
            # Use as many processes as there are CPU cores
            with multiprocessing.Pool() as pool:
                for i, result in enumerate(
                    pool.imap_unordered(FinderUtils.process_date_folder, date_folders)
                ):
                    if callback_bar:
                        progress_text = f"Scanning ({i + 1}/{total_folders})"
                        callback_bar.progress(
                            (i + 1) / total_folders, text=progress_text
                        )
                    results.append(result)
        else:
            Logger.info("Running scan in sequential mode.", "FILESYSTEM")
            for i, date_folder in enumerate(date_folders):
                if callback_bar:
                    progress_text = (
                        f"Scanning ({i + 1}/{total_folders}): {date_folder.name}"
                    )
                    callback_bar.progress((i + 1) / total_folders, text=progress_text)

                result = FinderUtils.process_date_folder(date_folder)
                results.append(result)

        # --- Data Insertion Phase ---
        Logger.info(
            "All folders scanned. Inserting data into the database...", "DATABASE"
        )

        report = {
            "headers": {"scan_path": root_dir, "scan_date": datetime.datetime.now()},
            "data": {
                "found_holo": sum(len(r[0]) for r in results),
                "found_hd": sum(len(r[1]) for r in results),
                "found_ef": sum(len(r[2]) for r in results),
                "found_preview": sum(len(r[3]) for r in results),
            },
        }

        holo_id_map = {}  # To map temporary string IDs to final database integer IDs

        try:
            for holo_list, hd_list, ef_list, preview_list in results:
                # Holo data
                for temp_holo_id, holo_data in holo_list:
                    db_id = self.InsertHoloFile(**holo_data)
                    if db_id:
                        holo_id_map[temp_holo_id] = db_id

                # Preview video data
                for preview_data in preview_list:
                    temp_parent_holo_id = preview_data["holo_id"]
                    if temp_parent_holo_id in holo_id_map:
                        preview_data["holo_id"] = holo_id_map[temp_parent_holo_id]
                        self.InsertPreviewVideo(**preview_data)
                    else:
                        Logger.error(
                            f".holo file ({temp_parent_holo_id}) is not found for preview_video: {preview_data['path']}"
                        )

                # HoloDoppler data
                hd_id_map = {}
                for temp_hd_id, hd_data in hd_list:
                    # Replace temporary parent ID with the real one
                    temp_parent_holo_id = hd_data["holo_id"]
                    if temp_parent_holo_id in holo_id_map:
                        hd_data["holo_id"] = holo_id_map[temp_parent_holo_id]
                        db_id = self.InsertHDRender(**hd_data)
                        if db_id:
                            hd_id_map[temp_hd_id] = db_id
                    else:
                        Logger.error(
                            f".holo file ({temp_parent_holo_id}) is not found for HD_folder: {hd_data['path']}"
                        )

                # EyeFlow data
                for ef_data in ef_list:
                    temp_parent_hd_id = ef_data["hd_id"]
                    if temp_parent_hd_id in hd_id_map:
                        ef_data["hd_id"] = hd_id_map[temp_parent_hd_id]
                        self.InsertEFRender(**ef_data)
                    else:
                        Logger.error(
                            f"HD folder ({temp_parent_hd_id}) is not found for EF_folder: {ef_data['path']}"
                        )

            self.DB.SQLconnect.commit()  # Commit everything in one single transaction
            Logger.info("Database insertion complete.", "DATABASE")

            generate_report(
                report, self.DB, Path(ConfigManager.get("FINDER.REPORT_PATH") or "")
            )

        except Exception as e:
            self.DB.SQLconnect.rollback()
            Logger.fatal(
                f"An error occurred during database insertion. Transaction rolled back. Error: {e}",
                "DATABASE",
            )

    #################
    #  OLD  IMPLEM  #
    #################

    # def Findfiles(self, root_dir: str, callback_bar=None):
    #     date_folders = list(FinderUtils.safe_iterdir(root_dir))
    #     total_folders = len(date_folders)

    #     for i, date_folder in enumerate(date_folders):
    #         if callback_bar:
    #             # Update progress bar with the percentage and current folder name
    #             progress_text = (
    #                 f"Scanning ({i + 1}/{total_folders}): {date_folder.name}"
    #             )
    #             callback_bar.progress((i + 1) / total_folders, text=progress_text)

    #         if not FinderUtils.check_folder_name_format(date_folder):
    #             Logger.info(f"Skipping: {date_folder}", "SKIP")
    #             continue

    #         Logger.info(f"Scanning date folder: {date_folder}")
    #         if not FinderUtils.safe_isdir(date_folder):
    #             continue

    #         # Search .holo
    #         holo_files = FinderUtils.find_all_holo_files(date_folder)

    #         for holo_file in holo_files:
    #             holo_id = self.InsertHoloFile(
    #                 path=holo_file,
    #                 tag=FinderUtils.get_measure_tag(Path(holo_file)),
    #                 created_at=FinderUtils.parse_folder_date(holo_file),
    #             )

    #             if not holo_id:
    #                 Logger.error(
    #                     f"Failed to insert .holo file in DB: {holo_file}",
    #                     tags="DATABASE",
    #                 )
    #                 continue

    #             hd_folders = FinderUtils.find_all_hd_folders_from_holo(holo_file)

    #             for render_number, hd_folder in hd_folders.items():
    #                 # --- HD data ---
    #                 rendering_params = None

    #                 rendering_json = hd_folder / (
    #                     f"{hd_folder.name}_RenderingParameters.json"
    #                 )
    #                 if rendering_json.exists():
    #                     rendering_params = FinderUtils.safe_json_load(rendering_json)

    #                 version_file = hd_folder / "version.txt"
    #                 version_text = FinderUtils.safe_file_read(version_file)

    #                 # --- EF data ---
    #                 eyeflow_folder = hd_folder / "eyeflow"
    #                 ef_render = []
    #                 if eyeflow_folder.exists():
    #                     ef_render = FinderUtils.get_ef_folders_data(eyeflow_folder)

    #                 hd_folder_path = hd_folder.absolute().as_posix()

    #                 hd_rowId = self.InsertHDRender(
    #                     holo_id=holo_id,
    #                     path=hd_folder_path,
    #                     render_number=render_number,
    #                     rendering_parameters=FinderUtils.json_dump_nullable(
    #                         rendering_params
    #                     ),
    #                     version=version_text,
    #                     updated_at=FinderUtils.get_last_update(Path(hd_folder_path)),
    #                 )

    #                 if hd_rowId is None:
    #                     Logger.error(
    #                         f"Failed to insert HD data for folder: {hd_folder}",
    #                         tags="DATABASE",
    #                     )
    #                     continue
    #                 for ef in ef_render:
    #                     last_row = self.InsertEFRender(
    #                         hd_id=hd_rowId,
    #                         render_number=FinderUtils.get_render_number(
    #                             ef["ef_folder"]
    #                         ),
    #                         path=ef["ef_folder"],
    #                         input_parameters=FinderUtils.json_dump_nullable(
    #                             ef["InputEyeFlowParams"]["content"]
    #                         ),
    #                         version=FinderUtils.get_eyeflow_version(
    #                             ef["ef_folder"], hd_folder.name
    #                         ),
    #                         report_path=FinderUtils.get_report_pdf(ef["ef_folder"]),
    #                         updated_at=FinderUtils.get_last_update(
    #                             Path(hd_folder_path)
    #                         ),
    #                     )

    #                     if last_row is None:
    #                         Logger.error(
    #                             f"Failed to insert EF data for folder: {ef['ef_folder']}",
    #                             tags="DATABASE",
    #                         )
    #                         continue
