import datetime
from pathlib import Path

from src.Logger.LoggerClass import Logger
from src.Database.DBClass import DB

# Data dictionary format:
# {
#       "headers": {
#           "scan_path": str,
#           "scan_date": datetime.datetime,
#       },
#       "data": {
#           "found_holo": str,
#           "found_hd": str,
#           "found_ef": str,
#           "found_preview": str,
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


def __get_duration(start, end) -> str:
    if not isinstance(start, datetime.datetime) or not isinstance(
        end, datetime.datetime
    ):
        return "N/A"

    duration = end - start
    return str(duration).split(".")[0]  # Remove microseconds


def __parse_data(data: dict, DB: DB, sep: str = "=", width: int = 40) -> str:
    now = datetime.datetime.now()
    scan_date = __s_get_r_dict(data, "headers.scan_date", "N/A").split(".")[0]  # type: ignore (will default to "N/A")

    separator = sep * width

    return f"""
{separator}
{"DopplerManager Scan Report":^{width}}
{separator}

Scan Path       : {__s_get_r_dict(data, "headers.scan_path", "N/A")}
Scan Date       : {scan_date}
Report Date     : {now.strftime("%Y-%m-%d %H:%M:%S")}
Total Duration  : {__get_duration(__s_get_r_dict(data, "headers.scan_date"), now)}
DB Path         : {DB.DB_PATH}


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

"""


# ┌───────────────────────────────────┐
# │           MAIN FUNCTIONS          │
# └───────────────────────────────────┘


def generate_report(data: dict, DB: DB, report_path: Path) -> None:
    """
    Generates a simple text report from the provided data dictionary
    and saves it to the specified report path.

    Args:
        data (dict): A dictionary containing report data.
        report_path (Path): The file path where the report will be saved.
    """

    # TODO: think about the possibility of exporting a pdf report with reportlab

    try:
        with open(report_path, "w") as report_file:
            report_file.write(__parse_data(data, DB) + "\n")

        Logger.info(f"Report generated successfully at {report_path}", "REPORT")
    except Exception as e:
        Logger.error(f"Failed to generate report at {report_path}: {e}", "REPORT")
