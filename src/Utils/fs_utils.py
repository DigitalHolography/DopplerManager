import json
import os
import datetime

from pathlib import Path
from src.Logger.LoggerClass import Logger

# ┌───────────────────────────────────┐
# │          SAFE IO FUNCTIONS        │
# └───────────────────────────────────┘


def safe_json_load(file_path: Path | str):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        Logger.error(f"{e}", tags="FILESYSTEM")
        return None


def safe_file_read(file_path: Path | str) -> str | None:
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        Logger.error(f"{e}", tags="FILESYSTEM")
        return None


def safe_isdir(path: Path | str) -> bool:
    try:
        path = Path(path)
        return path.is_dir()
    except (PermissionError, OSError) as e:
        Logger.error(
            f"Access denied or error reading directory: {path} – {e}", tags="FILESYSTEM"
        )
        return False


def safe_iterdir(path: Path | str) -> list[Path]:
    try:
        path = Path(path)
        if safe_isdir(path):
            return list(path.iterdir())
        else:
            return []
    except (PermissionError, OSError) as e:
        Logger.error(
            f"Access denied or error reading directory: {path} – {e}", tags="FILESYSTEM"
        )
        return []


def safe_scandir(path: Path | str) -> list[os.DirEntry]:
    try:
        path = Path(path)
        if safe_isdir(path):
            return list(os.scandir(path))
        else:
            return []
    except (PermissionError, OSError) as e:
        Logger.error(
            f"Access denied or error reading directory: {path} – {e}", tags="FILESYSTEM"
        )
        return []


# ┌───────────────────────────────────┐
# │             IO UTILS              │
# └───────────────────────────────────┘


def get_last_update(path: Path) -> datetime.datetime | None:
    if not path.exists():
        Logger.error(f"Path does not exists to get its update: {path}")
        return None

    return datetime.datetime.fromtimestamp(os.path.getmtime(path))


def get_all_files_by_extension(folder: Path, extension: str) -> list[Path]:
    """
    Retrieves all files with a specified extension from a folder.

    Args:
        folder (Path): A Path object representing the folder to search in.
        extension (str): The file extension to search for (e.g., 'txt', 'pdf').

    Returns:
        list[Path]: A list of Path objects for all files that match the given extension.
    """
    return list(folder.glob(f"*.{extension}"))


def json_dump_nullable(text: str | None):
    if text:
        return json.dumps(text)

    return None


def parse_path(path: Path | None) -> str | None:
    # Moved .resolve to export for speed increase
    return str(path) if path else None
