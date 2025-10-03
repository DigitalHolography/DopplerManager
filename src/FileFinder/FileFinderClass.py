import datetime
import multiprocessing
from pathlib import Path

import src.FileFinder.FinderUtils as FinderUtils
from src.Logger.LoggerClass import Logger
from src.Database.DBClass import DB
from src.FileFinder.ReportGen import generate_report

from src.Utils.fs_utils import parse_path, get_all_files_by_extension, safe_iterdir


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
                "path": parse_path(path),
                "render_number": render_number,
                "rendering_parameters": rendering_parameters,
                "raw_h5_path": parse_path(raw_h5_path),
                "version": version,
                "updated_at": updated_at,
            },
            do_commit=False,
        )

    def InsertHoloFile(
        self, path: Path, tag: str | None, created_at: datetime.date | None
    ) -> int | None:
        return self.DB.insert(
            "holo_data",
            {"path": str(path), "tag": tag, "created_at": created_at},
            do_commit=False,
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
                "path": parse_path(path),
                "input_parameters": input_parameters,
                "version": version,
                "report_path": parse_path(report_path),
                "h5_output": parse_path(h5_output),
                "updated_at": updated_at,
            },
            do_commit=False,
        )

    def InsertPreviewVideo(self, holo_id: int, path: Path) -> int | None:
        return self.DB.insert(
            "preview_doppler_video",
            {
                "holo_id": holo_id,
                "path": parse_path(path),
            },
            do_commit=False,
        )

    def Findfiles(
        self,
        root_dir: str,
        reset_db: bool = False,
        callback_bar=None,
        use_parallelism=False,
    ):
        if reset_db:
            self.ClearDB()
            Logger.info("Database cleared before new scan.", "DATABASE")

        if get_all_files_by_extension(Path(root_dir), "holo"):
            search_folders = [Path(root_dir)]
        else:
            search_folders = list(safe_iterdir(root_dir))

        total_folders = len(search_folders)

        results = []

        start_scan_date = datetime.datetime.now()

        if use_parallelism:
            # Use as many processes as there are CPU cores
            with multiprocessing.Pool() as pool:
                for i, result in enumerate(
                    pool.imap_unordered(FinderUtils.process_date_folder, search_folders)
                ):
                    if callback_bar:
                        progress_text = f"Scanning ({i + 1}/{total_folders})"
                        callback_bar.progress(
                            ((i + 1) / total_folders), text=progress_text
                        )
                    results.append(result)
        else:
            Logger.info("Running scan in sequential mode.", "FILESYSTEM")
            for i, date_folder in enumerate(search_folders):
                if callback_bar:
                    progress_text = (
                        f"Scanning ({i + 1}/{total_folders}): {date_folder.name}"
                    )
                    callback_bar.progress(((i + 1) / total_folders), text=progress_text)

                result = FinderUtils.process_date_folder(date_folder)
                results.append(result)

        # --- Data Insertion Phase ---
        Logger.info(
            "All folders scanned. Inserting data into the database...", "DATABASE"
        )

        if callback_bar:
            callback_bar.progress(0.5, text="Inserting data into database...")

        start_insert_date = datetime.datetime.now()

        holo_id_map = {}  # To map temporary string IDs to final database integer IDs
        # total_results_to_insert = len(results)

        try:
            for i, (holo_list, hd_list, ef_list, preview_list) in enumerate(results):
                # if callback_bar:
                #     progress_value = 0.5 + (((i + 1) / total_results_to_insert) * 0.5)
                #     progress_text = (
                #         f"Inserting data ({i + 1}/{total_results_to_insert})"
                #     )
                #     callback_bar.progress(progress_value, text=progress_text)

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

            report = {
                "headers": {
                    "scan_path": root_dir,
                    "scan_date": start_scan_date,
                    "insert_date": start_insert_date,
                    "end_date": datetime.datetime.now(),
                },
                "data": {
                    "found_holo": sum(len(r[0]) for r in results),
                    "found_hd": sum(len(r[1]) for r in results),
                    "found_ef": sum(len(r[2]) for r in results),
                    "found_preview": sum(len(r[3]) for r in results),
                },
            }

            generate_report(report, self.DB)

        except Exception as e:
            self.DB.SQLconnect.rollback()
            Logger.fatal(
                f"An error occurred during database insertion. Transaction rolled back. Error: {e}",
                "DATABASE",
            )
