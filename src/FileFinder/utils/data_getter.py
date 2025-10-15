import os
import re
from pathlib import Path

from src.Utils.fs_utils import (
    safe_scandir,
    safe_json_load,
    get_all_files_by_extension,
    safe_file_read,
)

from src.FileFinder.utils.path_parser import is_ef_folder


def find_all_holo_files(root_folder: Path) -> list[Path]:
    """
    Searches for all .holo files recursively from the root_path.
    Returns a list of unique, absolute file paths.
    """
    found_files = []
    search_paths = [root_folder]

    for path in search_paths:
        for dirpath, dirnames, filenames in os.walk(path):
            # Only keeps the folders that does not contain "_HD_"
            dirnames[:] = [d for d in dirnames if "_HD_" not in d]

            for filename in filenames:
                if filename.endswith(".holo"):
                    # absolute_path = os.path.abspath(os.path.join(dirpath, filename))
                    # Moved .resolve to export for speed increase
                    absolute_path = Path(dirpath) / filename
                    found_files.append(absolute_path)

    return found_files


def find_preview_video(holo_file_path: Path) -> Path | None:
    """Looks for a .avi file with the same base name as the .holo file."""
    holo_base_name = holo_file_path.stem
    preview_video_name = f"R_{holo_base_name}_p.avi"
    avi_path = holo_file_path.parent / preview_video_name

    if avi_path.exists() and avi_path.is_file():
        return avi_path

    return None


def gather_all_hd_folders_data_from_holo(holo_file_path: Path) -> dict[int, dict]:
    source_filename = os.path.basename(holo_file_path)
    base_name = os.path.splitext(source_filename)[0]
    hd_pattern = re.compile(f"^{re.escape(base_name)}_HD_(\\d+)$")

    hd_folders = {}

    parent_dir = os.path.dirname(holo_file_path)
    for entry in os.scandir(parent_dir):
        if not entry.is_dir():
            continue

        match = hd_pattern.match(entry.name)
        if match:
            number = int(match.group(1))
            hd_folder = Path(entry.path)

            rendering_params_json = (
                hd_folder / f"{hd_folder.name}_RenderingParameters.json"
            )
            rendering_params = (
                safe_json_load(rendering_params_json)
                if rendering_params_json.exists()
                else None
            )
            version_text = safe_file_read(hd_folder / "version.txt")

            hd_folders[number] = {
                "path": hd_folder,
                "rendering_params": rendering_params,
                "version_text": version_text,
                "raw_h5_path": _get_raw_h5_file(hd_folder),
            }

    return hd_folders


def gather_ef_folders_data(
    eyeflow_folder: Path, get_input_params: bool = False
) -> list[dict]:
    ef_data = []

    for ef_folder in safe_scandir(eyeflow_folder):
        if not ef_folder.is_dir() or not is_ef_folder(ef_folder.name):
            continue

        InputEyeFlowParams = {"path": None, "content": None}

        h5_output = None

        ef_folder = Path(ef_folder.path)

        json_folder = ef_folder / "json"
        if json_folder.is_dir():
            if get_input_params:
                input_param = json_folder / "InputEyeFlowParams.json"
                if input_param.exists():
                    content = safe_json_load(input_param)

                    if content:
                        InputEyeFlowParams = {
                            "path": str(input_param),
                            "content": content,
                        }

            h5_files = get_all_files_by_extension(ef_folder / "h5", "h5")
            if h5_files:
                h5_output = h5_files[0]

        ef_data.append(
            {
                "ef_folder": ef_folder,
                "InputEyeFlowParams": InputEyeFlowParams,
                "h5_output": h5_output,
                "report_path": _get_report_pdf(ef_folder),
            }
        )

    return ef_data


def _get_report_pdf(ef_folder: Path) -> Path | None:
    ef_folder = Path(ef_folder)
    pdf_folder = ef_folder / "pdf"

    if not os.path.isdir(pdf_folder):
        return None

    pdfs = os.listdir(pdf_folder)
    if not pdfs or len(pdfs) == 0:
        return None

    # Need to change in case of more than one pdf
    return pdf_folder / pdfs[0]


def _get_raw_h5_file(hd_folder: Path) -> Path | None:
    # Dummy check
    hd_folder = Path(hd_folder)
    raw_folder = hd_folder / "raw"

    if not raw_folder.is_dir():
        return None

    raw_file = get_all_files_by_extension(raw_folder, "h5")

    return raw_file[0] if raw_file else None
