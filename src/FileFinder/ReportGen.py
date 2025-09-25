import datetime
import os
from pathlib import Path

from src.Logger.LoggerClass import Logger
from src.Database.DBClass import DB
from src.Utils.ParamsLoader import ConfigManager

# Data dictionary format:
# {
#       "headers": {
#           "scan_path"     : str,
#           "scan_date"     : datetime.datetime,
#           "insert_date"   : datetime.datetime,
#           "end_date"      : datetime.datetime,
#       },
#       "data": {
#           "found_holo"    : str,
#           "found_hd"      : str,
#           "found_ef"      : str,
#           "found_preview" : str,
#       }
# }

# ┌───────────────────────────────────┐
# │          HELPER FUNCTIONS         │
# └───────────────────────────────────┘


def __s_get_dict(data: dict, key: str, default=None):
    return data.get(key, default)


def __s_get_r_dict(data: dict, keys: str, default=None):
    d = data
    for key in keys.split("."):
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d


def __format_date(date, timespec: str = "seconds") -> str:
    if not isinstance(date, datetime.datetime):
        return "N/A"

    return date.isoformat(" ", timespec=timespec)


def __get_duration(start, end) -> str:
    if not isinstance(start, datetime.datetime) or not isinstance(
        end, datetime.datetime
    ):
        return "N/A"

    duration = end - start

    return str(duration).split(".")[0]  # Remove microseconds for cleaner output


def __parse_data(data: dict, DB: DB, sep: str = "=", width: int = 40) -> str:
    now = datetime.datetime.now()
    scan_date = __s_get_r_dict(data, "headers.scan_date")
    insert_date = __s_get_r_dict(data, "headers.insert_date")
    end_date = __s_get_r_dict(data, "headers.end_date")

    scan_date_str = __format_date(scan_date)
    insert_date_str = __format_date(insert_date)
    end_date_str = __format_date(end_date)

    separator = sep * width

    return f"""
{separator}
{"DopplerManager Scan Report":^{width}}
{separator}

Scan Path       : {__s_get_r_dict(data, "headers.scan_path", "N/A")}
DB Path         : {DB.DB_PATH}

Scan Date       : {scan_date_str}
Insert Date     : {insert_date_str}
End Date        : {end_date_str}
Report Date     : {__format_date(now)}

Scan Duration   : {__get_duration(scan_date, insert_date)}
Insert Duration : {__get_duration(insert_date, end_date)}
Total Duration  : {__get_duration(scan_date, now)}

{separator}
{"METRICS":^{width}}
{separator}

{"WHILE SCANNING":^{width}}

Found Holo      : {__s_get_r_dict(data, "data.found_holo", "N/A")}
Found HD        : {__s_get_r_dict(data, "data.found_hd", "N/A")}
Found EF        : {__s_get_r_dict(data, "data.found_ef", "N/A")}
Found Preview   : {__s_get_r_dict(data, "data.found_preview", "N/A")}

{separator}

{"CURRENT IN DB":^{width}}

Total Holo      : {DB.count("holo_data")}
Total HD        : {DB.count("hd_render")}
Total EF        : {DB.count("ef_render")}
Total Preview   : {DB.count("preview_doppler_video")}

"""


def get_report_path() -> Path:
    tmp_config = ConfigManager.get("FINDER.REPORT_PATH") or ""

    if tmp_config != "":
        return Path(tmp_config)

    appdata_path = os.getenv("APPDATA")

    if not appdata_path:
        return Path("reports")

    app_dir = Path(appdata_path) / "DopplerManager" / "reports"
    os.makedirs(app_dir, exist_ok=True)

    return app_dir


# ┌───────────────────────────────────┐
# │           MAIN FUNCTIONS          │
# └───────────────────────────────────┘


def generate_report(data: dict, DB: DB, report_path: Path | None = None) -> None:
    """
    Generates a simple text report from the provided data dictionary
    and saves it to the specified report path.

    Args:
        data (dict): A dictionary containing report data.
        report_path (Path): The file path where the report will be saved.
    """

    # TODO: think about the possibility of exporting a pdf report with reportlab

    if report_path is None:
        report_path = get_report_path()
    else:
        os.makedirs(report_path, exist_ok=True)

    report_path = (
        report_path / f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    try:
        with open(report_path, "w") as report_file:
            report_file.write(__parse_data(data, DB) + "\n")

        Logger.info(f"Report generated successfully at {report_path}", "REPORT")
    except Exception as e:
        Logger.error(f"Failed to generate report at {report_path}: {e}", "REPORT")
