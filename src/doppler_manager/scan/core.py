from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from doppler_manager.models import (
    AcquisitionResult,
    FileRef,
    STAGE_LABELS,
    STAGE_ORDER,
    StageResult,
    ScanResult,
)
from doppler_manager.scan.filters import (
    holo_filter_allows,
    holo_filter_entry_path,
    normalize_holo_filter_entry,
)
from doppler_manager.scan.options import DEFAULT_SKIP_DIRS, ScanOptions


STAGE_SUFFIXES = {
    "hd": "_HD",
    "dv": "_DV",
    "ef": "_EF",
    "ae": "_AE",
}

TEXT_SUFFIXES = {".txt", ".log"}
PARAM_SUFFIXES = {".json"}
PREVIEW_SUFFIXES = {".png", ".jpg", ".jpeg", ".avi", ".mp4", ".mov"}


@dataclass
class Discovery:
    root: Path
    all_holo_paths: List[Path] = field(default_factory=list)
    holo_by_id: Dict[str, Path] = field(default_factory=dict)
    acquisition_dirs: Dict[str, Path] = field(default_factory=dict)
    stage_dirs: Dict[Tuple[str, str], Path] = field(default_factory=dict)
    listed_ids: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)
    visited_dirs: int = 0
    visited_entries: int = 0
    truncated: bool = False


def scan_root(root: Union[Path, str], options: Optional[ScanOptions] = None) -> ScanResult:
    options = options or ScanOptions()
    root_path = Path(root).expanduser()

    try:
        root_path = root_path.resolve()
    except OSError:
        root_path = root_path.absolute()

    if options.holo_filter_entries is not None:
        return _scan_holo_filter_entries(root_path, options)

    if not root_path.exists():
        return ScanResult(root=str(root_path), acquisitions=[], errors=[f"Path not found: {root_path}"])

    discovery = _discover(root_path, options)
    acquisition_ids = _candidate_ids(discovery, options)
    acquisitions = [
        _build_acquisition(acquisition_id, discovery, options)
        for acquisition_id in sorted(acquisition_ids)
    ]

    return ScanResult(
        root=str(root_path),
        acquisitions=acquisitions,
        all_holo_files=[
            FileRef.from_path(path, "holo")
            for path in sorted(_dedupe_paths(discovery.all_holo_paths), key=lambda path: str(path).lower())
        ],
        visited_dirs=discovery.visited_dirs,
        visited_entries=discovery.visited_entries,
        truncated=discovery.truncated,
        errors=discovery.errors,
    )


def _discover(root: Path, options: ScanOptions) -> Discovery:
    discovery = Discovery(root=root)
    queue = deque([(root, 0)])

    while queue and not discovery.truncated:
        current_dir, depth = queue.popleft()
        discovery.visited_dirs += 1

        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    discovery.visited_entries += 1
                    if discovery.visited_entries >= options.max_entries:
                        discovery.truncated = True
                        break

                    name = entry.name
                    entry_path = Path(entry.path)

                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError as exc:
                        discovery.errors.append(f"Unable to access: {entry_path} ({exc})")
                        continue

                    if is_dir:
                        stage = _stage_from_dir_name(name)
                        if stage:
                            acquisition_id = name[: -len(STAGE_SUFFIXES[stage])]
                            if not holo_filter_allows(acquisition_id, options.holo_filter_ids):
                                continue
                            discovery.stage_dirs[(acquisition_id, stage)] = entry_path
                            if entry_path.parent.name == acquisition_id:
                                discovery.acquisition_dirs.setdefault(acquisition_id, entry_path.parent)
                            continue

                        if name in options.skip_dirs:
                            continue

                        if depth < options.max_depth:
                            queue.append((entry_path, depth + 1))

                    elif is_file and name.lower().endswith(".holo"):
                        discovery.all_holo_paths.append(entry_path)
                        if not holo_filter_allows(entry_path.stem, options.holo_filter_ids):
                            continue
                        discovery.holo_by_id[entry_path.stem] = entry_path
                        sibling_dir = entry_path.with_suffix("")
                        if sibling_dir.exists() and sibling_dir.is_dir():
                            discovery.acquisition_dirs.setdefault(entry_path.stem, sibling_dir)

        except OSError as exc:
            discovery.errors.append(f"Unable to read: {current_dir} ({exc})")

    return discovery


def _scan_holo_filter_entries(root: Path, options: ScanOptions) -> ScanResult:
    discovery = Discovery(root=root)
    entries = options.holo_filter_entries or ()
    discovery.visited_entries = len(entries)

    for entry in entries:
        acquisition_id = normalize_holo_filter_entry(entry)
        if acquisition_id:
            discovery.listed_ids.add(acquisition_id)

        holo_path = holo_filter_entry_path(entry, root)
        if holo_path is None:
            continue

        try:
            resolved_holo_path = holo_path.resolve()
        except OSError:
            resolved_holo_path = holo_path.absolute()

        if not resolved_holo_path.is_file():
            discovery.errors.append(f"Listed .holo file not found: {resolved_holo_path}")
            continue

        discovered_id = resolved_holo_path.stem
        discovery.listed_ids.add(discovered_id)
        discovery.all_holo_paths.append(resolved_holo_path)
        discovery.holo_by_id[discovered_id] = resolved_holo_path
        sibling_dir = resolved_holo_path.with_suffix("")
        if sibling_dir.exists() and sibling_dir.is_dir():
            discovery.acquisition_dirs.setdefault(discovered_id, sibling_dir)

    acquisition_ids = _candidate_ids(discovery, options)
    acquisitions = [
        _build_acquisition(acquisition_id, discovery, options)
        for acquisition_id in sorted(acquisition_ids)
    ]

    return ScanResult(
        root=str(root),
        acquisitions=acquisitions,
        all_holo_files=[
            FileRef.from_path(path, "holo")
            for path in sorted(_dedupe_paths(discovery.all_holo_paths), key=lambda path: str(path).lower())
        ],
        visited_dirs=0,
        visited_entries=discovery.visited_entries,
        truncated=False,
        errors=discovery.errors,
    )


def _stage_from_dir_name(name: str) -> Optional[str]:
    for stage, suffix in STAGE_SUFFIXES.items():
        if name.endswith(suffix) and len(name) > len(suffix):
            return stage
    return None


def _candidate_ids(discovery: Discovery, options: ScanOptions) -> Set[str]:
    ids = set(discovery.listed_ids)
    ids.update(discovery.holo_by_id)
    ids.update(discovery.acquisition_dirs)
    ids.update(acquisition_id for acquisition_id, _stage in discovery.stage_dirs)
    if options.holo_filter_ids is not None:
        ids &= options.holo_filter_ids
    return ids


def _build_acquisition(
    acquisition_id: str,
    discovery: Discovery,
    options: ScanOptions,
) -> AcquisitionResult:
    source_holo_path = discovery.holo_by_id.get(acquisition_id)
    acquisition_dir_path = _resolve_acquisition_dir(acquisition_id, discovery, source_holo_path)

    acquisition = AcquisitionResult(
        acquisition_id=acquisition_id,
        source_holo=FileRef.from_path(source_holo_path, "holo") if source_holo_path else None,
        acquisition_dir=FileRef.from_path(acquisition_dir_path, "directory") if acquisition_dir_path else None,
    )

    for stage in STAGE_ORDER:
        stage_dir = _resolve_stage_dir(acquisition_id, stage, discovery, acquisition_dir_path)
        acquisition.stages[stage] = _inspect_stage(
            acquisition_id=acquisition_id,
            stage=stage,
            stage_dir=stage_dir,
            acquisition_dir=acquisition_dir_path,
            options=options,
        )

    acquisition.root_preview_files = _find_root_previews(acquisition_id, source_holo_path, acquisition_dir_path)
    _apply_pipeline_consistency(acquisition)
    acquisition.status = _global_status(acquisition)
    return acquisition


def _resolve_acquisition_dir(
    acquisition_id: str,
    discovery: Discovery,
    source_holo_path: Optional[Path],
) -> Optional[Path]:
    if acquisition_id in discovery.acquisition_dirs:
        return discovery.acquisition_dirs[acquisition_id]

    if source_holo_path:
        sibling = source_holo_path.with_suffix("")
        if sibling.exists() and sibling.is_dir():
            return sibling

    for (candidate_id, _stage), stage_path in discovery.stage_dirs.items():
        if candidate_id == acquisition_id and stage_path.parent.name == acquisition_id:
            return stage_path.parent

    return None


def _resolve_stage_dir(
    acquisition_id: str,
    stage: str,
    discovery: Discovery,
    acquisition_dir: Optional[Path],
) -> Optional[Path]:
    stage_dir = discovery.stage_dirs.get((acquisition_id, stage))
    if stage_dir:
        return stage_dir

    if acquisition_dir:
        candidate = acquisition_dir / f"{acquisition_id}{STAGE_SUFFIXES[stage]}"
        if candidate.exists() and candidate.is_dir():
            return candidate

    return None


def _inspect_stage(
    acquisition_id: str,
    stage: str,
    stage_dir: Optional[Path],
    acquisition_dir: Optional[Path],
    options: ScanOptions,
) -> StageResult:
    result = StageResult(code=stage, label=STAGE_LABELS[stage])

    if stage_dir:
        result.stage_dir = FileRef.from_path(stage_dir, "directory")

    h5_paths = _stage_h5_paths(acquisition_id, stage, stage_dir)
    result.h5_files = [FileRef.from_path(path, "h5") for path in h5_paths]

    params_paths = _stage_param_paths(acquisition_id, stage, stage_dir, acquisition_dir)
    result.params_files = [FileRef.from_path(path, "params") for path in params_paths]

    version_paths = _stage_version_paths(stage_dir)
    result.version_files = [FileRef.from_path(path, "version") for path in version_paths]
    if options.read_versions:
        result.versions = _read_version_files(version_paths, options.max_text_bytes)

    preview_paths = _stage_preview_paths(stage_dir, options.preview_limit_per_stage)
    result.preview_files = [FileRef.from_path(path, "preview") for path in preview_paths]

    result.status = _stage_status(acquisition_id, stage, result)
    return result


def _stage_h5_paths(acquisition_id: str, stage: str, stage_dir: Optional[Path]) -> List[Path]:
    if not stage_dir:
        return []

    candidates: List[Path] = []
    if stage == "ae":
        candidates.extend(_direct_files(stage_dir, {".h5"}))
        candidates.extend(_direct_files(stage_dir / "h5", {".h5"}))
    else:
        candidates.extend(_direct_files(stage_dir / "h5", {".h5"}))

    expected = _expected_h5_name(acquisition_id, stage)
    return _sort_preferred(candidates, expected)


def _stage_param_paths(
    acquisition_id: str,
    stage: str,
    stage_dir: Optional[Path],
    acquisition_dir: Optional[Path],
) -> List[Path]:
    paths: List[Path] = []

    if acquisition_dir and stage == "hd":
        paths.extend(_existing_files([acquisition_dir / f"{acquisition_id}_input_HD_params.json"]))

    if acquisition_dir and stage == "ef":
        paths.extend(_direct_files(acquisition_dir / "eyeflow" / "json", PARAM_SUFFIXES))

    if stage_dir:
        paths.extend(_direct_files(stage_dir, PARAM_SUFFIXES))
        paths.extend(_direct_files(stage_dir / "config", PARAM_SUFFIXES))
        if stage == "hd":
            paths.extend(_direct_files(stage_dir / "json", PARAM_SUFFIXES))
        if stage == "ef":
            paths.extend(_direct_files(stage_dir / "json", PARAM_SUFFIXES))

    return _dedupe_paths(paths)


def _stage_version_paths(stage_dir: Optional[Path]) -> List[Path]:
    if not stage_dir:
        return []
    return _direct_files(stage_dir, TEXT_SUFFIXES)


def _stage_preview_paths(stage_dir: Optional[Path], limit: int) -> List[Path]:
    if not stage_dir:
        return []

    paths: List[Path] = []
    paths.extend(_direct_files(stage_dir / "png", PREVIEW_SUFFIXES, limit=limit))
    paths.extend(_direct_files(stage_dir / "avi", PREVIEW_SUFFIXES, limit=limit))
    paths.extend(_direct_files(stage_dir, PREVIEW_SUFFIXES, limit=limit))
    remaining = limit - len(_dedupe_paths(paths))
    if remaining > 0:
        paths.extend(
            _limited_walk_files(
                stage_dir / "output",
                PREVIEW_SUFFIXES,
                max_depth=4,
                limit=remaining,
                max_entries=2_000,
            )
        )
    return _dedupe_paths(paths)[:limit]


def _find_root_previews(
    acquisition_id: str,
    source_holo_path: Optional[Path],
    acquisition_dir: Optional[Path],
) -> List[FileRef]:
    search_dirs = []
    if source_holo_path:
        search_dirs.append(source_holo_path.parent)
    if acquisition_dir:
        search_dirs.append(acquisition_dir.parent)

    refs: List[FileRef] = []
    seen: Set[Path] = set()
    for directory in search_dirs:
        for path in _direct_files(directory, PREVIEW_SUFFIXES, limit=100):
            if acquisition_id in path.stem and path not in seen:
                seen.add(path)
                refs.append(FileRef.from_path(path, "preview"))
    return refs


def _stage_status(acquisition_id: str, stage: str, result: StageResult) -> str:
    started = bool(
        result.stage_dir
        or result.h5_files
        or result.params_files
        or result.version_files
        or result.preview_files
    )
    if not started:
        return "not_started"

    non_empty_h5 = [file for file in result.h5_files if file.size is not None and file.size > 0]
    if not non_empty_h5:
        result.notes.append("No usable .h5 file was detected for this stage.")
        return "partial"

    expected_name = _expected_h5_name(acquisition_id, stage)
    if any(file.name == expected_name for file in non_empty_h5):
        return "complete"

    result.notes.append(f"A .h5 file is present, but the expected name is {expected_name}.")
    return "warning"


def _expected_h5_name(acquisition_id: str, stage: str) -> str:
    if stage == "hd":
        return f"{acquisition_id}_HD_output.h5"
    return f"{acquisition_id}{STAGE_SUFFIXES[stage]}.h5"


def _apply_pipeline_consistency(acquisition: AcquisitionResult) -> None:
    if not acquisition.source_holo:
        acquisition.warnings.append("Source .holo file was not detected.")

    if not acquisition.acquisition_dir:
        acquisition.warnings.append("Acquisition folder was not detected.")

    for stage in STAGE_ORDER:
        result = acquisition.stages[stage]
        for file_ref in result.h5_files:
            if file_ref.size == 0:
                message = f"{result.label}: empty file detected ({file_ref.name})."
                result.notes.append(message)
                acquisition.errors.append(message)
                result.status = "error"


def _global_status(acquisition: AcquisitionResult) -> str:
    stage_statuses = [acquisition.stages[stage].status for stage in STAGE_ORDER]

    if acquisition.errors or any(status == "error" for status in stage_statuses):
        return "error"
    if acquisition.warnings or any(status == "warning" for status in stage_statuses):
        return "warning"
    if all(status == "complete" for status in stage_statuses):
        return "complete"
    if any(status in {"complete", "partial"} for status in stage_statuses):
        return "partial"
    return "not_started"


def _direct_files(directory: Path, suffixes: Set[str], limit: Optional[int] = None) -> List[Path]:
    if not directory.exists() or not directory.is_dir():
        return []

    paths: List[Path] = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if limit is not None and len(paths) >= limit:
                    break
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                path = Path(entry.path)
                if path.suffix.lower() in suffixes:
                    paths.append(path)
    except OSError:
        return []

    return sorted(paths, key=lambda path: path.name.lower())


def _limited_walk_files(
    root: Path,
    suffixes: Set[str],
    max_depth: int,
    limit: int,
    max_entries: int,
) -> List[Path]:
    if limit <= 0 or not root.exists() or not root.is_dir():
        return []

    paths: List[Path] = []
    visited_entries = 0
    queue = deque([(root, 0)])

    while queue and len(paths) < limit and visited_entries < max_entries:
        directory, depth = queue.popleft()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited_entries += 1
                    if visited_entries >= max_entries or len(paths) >= limit:
                        break

                    entry_path = Path(entry.path)
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if depth < max_depth and entry.name not in DEFAULT_SKIP_DIRS:
                                queue.append((entry_path, depth + 1))
                        elif entry.is_file(follow_symlinks=False) and entry_path.suffix.lower() in suffixes:
                            paths.append(entry_path)
                    except OSError:
                        continue
        except OSError:
            continue

    return sorted(paths, key=lambda path: str(path).lower())


def _existing_files(paths: Iterable[Path]) -> List[Path]:
    existing = []
    for path in paths:
        if path.exists() and path.is_file():
            existing.append(path)
    return existing


def _sort_preferred(paths: Sequence[Path], preferred_name: str) -> List[Path]:
    deduped = _dedupe_paths(paths)
    return sorted(
        deduped,
        key=lambda path: (path.name != preferred_name, path.name.lower()),
    )


def _dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    deduped: List[Path] = []
    seen: Set[Path] = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def _read_version_files(paths: Sequence[Path], max_bytes: int) -> Dict[str, str]:
    versions: Dict[str, str] = {}
    for path in paths:
        try:
            with path.open("rb") as handle:
                content = handle.read(max_bytes)
            text = content.decode("utf-8", errors="replace").strip()
            versions[path.name] = text
        except OSError as exc:
            versions[path.name] = f"Unable to read: {exc}"
    return versions
