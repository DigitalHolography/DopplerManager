import datetime
import os
import re
from pathlib import Path

from src.Logger.LoggerClass import Logger


def is_ef_folder(name: str):
    return "_EF_" in name


def parse_folder_date(path: Path) -> datetime.date:
    folder_name = os.path.basename(path)
    date_pattern = re.compile(r"^(\d{2})(\d{2})(\d{2}).*$")

    matchs = date_pattern.match(folder_name)
    if not matchs:  # or len(matchs.groups()) == 3:
        Logger.error(
            f"{path} does not match date format, defaulting to creation date of folder"
        )
        return datetime.date.fromtimestamp(os.path.getctime(path))

    try:
        return datetime.date(
            2000 + int(matchs.group(1)), int(matchs.group(2)), int(matchs.group(3))
        )
    except Exception as _:
        Logger.error(f"Wrong date format: {folder_name} ({path})")
        return datetime.date.fromtimestamp(os.path.getctime(path))


def check_folder_name_format(path: Path) -> bool:
    folder_name = os.path.basename(path)
    date_pattern = re.compile(r"^\d{6}.*$")

    return date_pattern.match(folder_name) is not None


def get_measure_tag(path: Path) -> str | None:
    try:
        path = Path(path)
        return path.stem.split("_")[1]
    except Exception as _:
        return None


def get_render_number(path: Path) -> int | None:
    try:
        return int(path.stem.split("_")[-1])
    except Exception as _:
        return None
