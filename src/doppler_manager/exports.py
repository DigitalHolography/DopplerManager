"""Build EF archives from scanned files and cohort path lists."""
from __future__ import annotations

import io
from pathlib import Path, PureWindowsPath
import re
import zipfile

from doppler_manager.models import AcquisitionResult, FileRef


def ef_h5_files(acquisition: AcquisitionResult) -> list[FileRef]:
    stage = acquisition.stages.get("ef")
    return stage.h5_files if stage else []


def parse_cohorts(text: str) -> dict[str, list[str]]:
    cohorts: dict[str, list[str]] = {}
    current = None
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if (
                not name or name in {".", ".."} or name.endswith((".", " "))
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
                or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name)
                or name.casefold() == "missing_ef.txt"
            ):
                raise ValueError(f"Line {number}: invalid cohort folder name {name!r}.")
            existing = next((key for key in cohorts if key.casefold() == name.casefold()), name)
            current = cohorts.setdefault(existing, [])
        elif current is None:
            raise ValueError(f"Line {number}: add a [cohort name] header before paths.")
        else:
            current.append(line.strip('"'))
    if not cohorts or not any(cohorts.values()):
        raise ValueError("Enter at least one [cohort name] header followed by an acquisition path.")
    return cohorts


def _path_key(value: str) -> str:
    return str(PureWindowsPath(value)).casefold()


def _acquisition_name(value: str) -> str:
    name = PureWindowsPath(value).name
    if name.lower().endswith(".holo"):
        name = name[:-5]
    elif name.lower().endswith("_ef.h5"):
        name = name[:-6]
    return name.casefold()


def _write_files(
    archive: zipfile.ZipFile, files: list[FileRef], folder: str, used: set[str],
) -> None:
    for file in {file.path: file for file in files}.values():
        path = Path(file.path)
        name = f"{folder}{path.name}"
        suffix = 2
        while name.casefold() in used:
            name = f"{folder}{path.stem}_{suffix}{path.suffix}"
            suffix += 1
        archive.write(path, name)
        used.add(name.casefold())


def build_ef_h5_zip(acquisitions: list[AcquisitionResult]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_files(archive, [file for item in acquisitions for file in ef_h5_files(item)], "", set())
    return buffer.getvalue()


def build_cohort_ef_zip(acquisitions: list[AcquisitionResult], text: str) -> bytes:
    cohorts = parse_cohorts(text)
    paths: dict[str, list[int]] = {}
    names: dict[str, list[int]] = {}
    for index, item in enumerate(acquisitions):
        names.setdefault(item.acquisition_id.casefold(), []).append(index)
        aliases = [file.path for file in ef_h5_files(item)]
        aliases.extend(ref.path for ref in (item.source_holo, item.acquisition_dir) if ref)
        for alias in aliases:
            paths.setdefault(_path_key(alias), []).append(index)

    buffer = io.BytesIO()
    missing = []
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        used: set[str] = set()
        for cohort, entries in cohorts.items():
            archive.writestr(f"{cohort}/", "")
            missing_entries = []
            exported: set[int] = set()
            for entry in entries:
                matches = set(paths.get(_path_key(entry), names.get(_acquisition_name(entry), [])))
                if len(matches) != 1:
                    missing_entries.append(entry)
                    continue
                index = matches.pop()
                files = ef_h5_files(acquisitions[index])
                if not files or any(not Path(file.path).is_file() for file in files):
                    missing_entries.append(entry)
                    continue
                if index not in exported:
                    _write_files(archive, files, f"{cohort}/", used)
                    exported.add(index)
            if missing_entries:
                missing.extend([f"[{cohort}]", *dict.fromkeys(missing_entries), ""])
        archive.writestr("missing_EF.txt", "\n".join(missing))
    return buffer.getvalue()
