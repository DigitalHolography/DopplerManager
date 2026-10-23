"""Persistent application and processing logs shared by development and releases."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4


APP_FOLDERS = {
    "hd": "Holodoppler",
    "dv": "DopplerView",
    "ef": "EyeFlow",
    "ae": "AngioEye",
    "ae_postprocess": "AngioEye",
}
_WRITE_LOCK = RLock()


def logs_dir() -> Path:
    base = os.getenv("APPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    directory = root / "DopplerManager" / "logs"
    for folder in set(APP_FOLDERS.values()):
        (directory / folder).mkdir(parents=True, exist_ok=True)
    return directory


def main_log_path() -> Path:
    return logs_dir() / "DopplerManager.log"


def _timestamped(message: str) -> str:
    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    lines = message.lstrip("\r").rstrip().splitlines() or [""]
    return "".join(f"[{timestamp}] {line}\n" for line in lines)


def append_log(path: Path, message: str) -> None:
    with _WRITE_LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(_timestamped(message))


def log_manager(message: str) -> None:
    append_log(main_log_path(), message)


def processing_log_path(stage: str, acquisition_id: str, command: tuple[str, ...]) -> Path:
    source = next((arg for arg in command if arg.lower().endswith(".holo")), None)
    name = Path(source).stem if source else acquisition_id
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "acquisition"
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(
        f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
    )}:
        name = "_" + name
    return logs_dir() / APP_FOLDERS[stage] / f"{name}.log"


@contextmanager
def processing_log(
    stage: str,
    acquisition_id: str,
    command: tuple[str, ...],
    cwd: Path,
    on_log: Callable[[str], None],
) -> Iterator[Callable[[str], None]]:
    path = processing_log_path(stage, acquisition_id, command)
    run_id = uuid4().hex
    context = f"[{APP_FOLDERS[stage]}][{acquisition_id}][{run_id}]"
    # Open before preparing outputs so a logging failure cannot erase old results.
    with path.open("a", encoding="utf-8", buffering=1) as handle:
        def emit(line: str) -> None:
            with _WRITE_LOCK:
                handle.write(_timestamped(line))
                handle.flush()
            if line.startswith(("[START]", "[CMD]", "[OK]", "[FAIL]", "[SKIP]")):
                log_manager(f"{context} {line}")
            on_log(line)

        with _WRITE_LOCK:
            handle.write(_timestamped(
                f"[RUN] {run_id}\n[ACQUISITION] {acquisition_id}\n[CWD] {cwd}\n"
                f"[MANAGER] {sys.executable}; frozen={getattr(sys, 'frozen', False)}; "
                f"pid={os.getpid()}\n[ARGV] {command!r}"
            ))
        log_manager(f"{context} [LOG] {path}")
        try:
            yield emit
        finally:
            with _WRITE_LOCK:
                handle.write(_timestamped(f"[END RUN] {run_id}"))
