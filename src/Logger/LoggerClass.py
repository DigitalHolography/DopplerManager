from typing import List, Dict, Tuple # For Python before 3.9
from ColorClass import col

# ┌───────────────────────────────────┐
# │            TAGS_COLORS            │
# └───────────────────────────────────┘

tags_color = {
    "INFO":     [col.bg.CYA, col.BLA, col.BOLD],
    "WARN":     [col.bg.YEL, col.BLA, col.BOLD],
    "INFO ":    [col.bg.CYA, col.BLA, col.BOLD], # For alignment
    "WARN ":    [col.bg.YEL, col.BLA, col.BOLD], # For alignment
    "ERROR":    [col.bg.RED, col.BLA, col.BOLD],
    "DEBUG":    [col.bg.BLU, col.BLA, col.BOLD],
    "DOWNLOAD": [col.bg.PUR, col.BLA, col.BOLD],
    "DONE":     [col.bg.GRE, col.BLA, col.BOLD],
    "TIME":     [col.bg.BLU, col.BLA, col.BOLD],
}

################################################################################


def log(msg: str, colors: List[str], end: str = "\n") -> None:
    for x in colors:
        print(x, end="")
    print(f"{msg}{col.RES}", end=end)

def log_tags(msg: str, tags: List[Tuple[str, List[str]]]) -> None:
    for tag in tags:
        log(f" {tag[0]} ", tag[1], "")
    print("", msg)


def log_t(msg: str, tags: List[str] | str) -> None:
    """
    This function will print tags before the message with color codes defined in
    the tags_color global var.
    You should maybe use the Logger class.
    """
    if type(tags) == str:
        tags = [tags]
    for t in tags:
        # print(tags_color.get(t, []))
        if t in tags_color:
            log(f" {t} ", tags_color.get(t, []), "")
            # log(f" {t:<8} ", tags_color.get(t, []), "")
        else:
            log(f"[ {t} ]", [], "")
    print("", msg)


# Logger class
# @param    msg     The message to be printed
# @param    tags    Take the tag (or list of tags) to be printed before 
class Logger:
    @staticmethod
    def info(msg : str, tags: List[str] | str = []) -> None:
        if type(tags) == str:
            tags = [tags]
        log_t(msg, ["INFO "] + tags) # type: ignore

    @staticmethod
    def warn(msg : str, tags: List[str] | str  = []) -> None:
        if type(tags) == str:
            tags = [tags]
        log_t(msg, ["WARN "] + tags) # type: ignore

    @staticmethod
    def error(msg : str, tags: List[str] | str  = []) -> None:
        if type(tags) == str:
            tags = [tags]
        log_t(msg, ["ERROR"] + tags) # type: ignore

    @staticmethod
    def debug(msg : str, tags: List[str] | str  = []) -> None:
        if type(tags) == str:
            tags = [tags]
        log_t(msg, ["DEBUG"] + tags) # type: ignore