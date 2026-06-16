from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st

from doppler_managing.models import AcquisitionResult, FileRef, STAGE_LABELS, STAGE_ORDER
from doppler_managing.ui.formatting import format_size, format_timestamp


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
VIDEO_SUFFIXES = {".avi", ".mp4", ".mov", ".m4v"}


def media_by_stage(acquisition: AcquisitionResult) -> Dict[str, List[FileRef]]:
    groups: Dict[str, List[FileRef]] = {"Acquisition": list(acquisition.root_preview_files)}
    for stage in STAGE_ORDER:
        groups[STAGE_LABELS[stage]] = list(acquisition.stages[stage].preview_files)
    return groups


def render_media_preview(acquisition: AcquisitionResult) -> None:
    groups = media_by_stage(acquisition)
    if not any(groups.values()):
        st.info("No PNG/JPG/AVI/MP4 media preview was detected in indexed locations.")
        return

    nav_col, content_col = st.columns([0.72, 5.6], vertical_alignment="top")
    stage_label = _render_media_toolbar(nav_col, acquisition, list(groups.keys()))
    with content_col:
        _render_stage_media(acquisition, stage_label, groups[stage_label])


def _render_media_toolbar(container, acquisition: AcquisitionResult, options: list[str]) -> str:
    key = f"media-stage-{acquisition.acquisition_id}"
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]

    with container.container(border=True, key=f"media-stage-{acquisition.acquisition_id}-toolbar"):
        for option in options:
            selected = st.session_state[key] == option
            st.button(
                _media_toolbar_label(option),
                key=f"{key}-{option}",
                help=option,
                type="primary" if selected else "secondary",
                width="stretch",
                on_click=_select_media_stage,
                args=(key, option),
            )
    return str(st.session_state[key])


def _media_toolbar_label(stage_label: str) -> str:
    if stage_label == "Acquisition":
        return "Raw"
    for stage, label in STAGE_LABELS.items():
        if label == stage_label:
            return stage.upper()
    return stage_label


def _select_media_stage(key: str, stage_label: str) -> None:
    st.session_state[key] = stage_label


def _render_stage_media(acquisition: AcquisitionResult, stage_label: str, files: List[FileRef]) -> None:
    if not files:
        st.info(f"No media files indexed for {stage_label}.")
        return

    base_dir = _stage_base_dir(acquisition, stage_label)
    folder_options = _folder_options(files, base_dir)
    filter_cols = st.columns([1.4, 0.9, 1.7])
    selected_folder = filter_cols[0].selectbox(
        "Folder",
        ["All folders", *folder_options],
        key=f"media-folder-{acquisition.acquisition_id}-{stage_label}",
    )
    selected_type = filter_cols[1].selectbox(
        "Type",
        ["All", "Images", "Videos"],
        key=f"media-type-{acquisition.acquisition_id}-{stage_label}",
    )
    search = filter_cols[2].text_input(
        "Search media",
        value="",
        key=f"media-search-{acquisition.acquisition_id}-{stage_label}",
    )

    filtered = _filter_media(files, base_dir, selected_folder, selected_type, search)
    st.caption(f"{len(filtered)} of {len(files)} media files shown")
    if not filtered:
        st.warning("No media file matches the active filters.")
        return

    selected = st.selectbox(
        "Preview file",
        filtered,
        format_func=lambda file_ref: _media_label(file_ref, base_dir),
        key=f"media-select-{acquisition.acquisition_id}-{stage_label}",
    )
    _render_media_meta(selected)
    _render_media_file(selected)


def _render_media_file(file_ref: FileRef) -> None:
    path = Path(file_ref.path)
    suffix = path.suffix.lower()

    if suffix in IMAGE_SUFFIXES:
        st.image(str(path), width="stretch")
        return

    if suffix in {".mp4", ".mov", ".m4v"}:
        st.video(str(path))
        return

    if suffix == ".avi":
        with st.spinner("Preparing browser-compatible MP4 preview from AVI..."):
            mp4_path, error = prepare_browser_video(path)
        if mp4_path:
            st.video(str(mp4_path))
            st.caption("AVI files are converted to cached MP4 previews for reliable browser playback.")
        else:
            st.warning("AVI playback requires conversion. Automatic conversion failed on this machine.")
            if error:
                st.code(error, language="text")
        return

    st.info("This media type is indexed but not previewable in the browser.")


def _render_media_meta(file_ref: FileRef) -> None:
    cols = st.columns([1, 1, 3])
    cols[0].caption(f"Size: {format_size(file_ref.size)}")
    cols[1].caption(f"Modified: {format_timestamp(file_ref.modified_ts)}")
    cols[2].caption(file_ref.path)


def _stage_base_dir(acquisition: AcquisitionResult, stage_label: str) -> Optional[Path]:
    if stage_label == "Acquisition":
        if acquisition.acquisition_dir:
            return Path(acquisition.acquisition_dir.path).parent
        if acquisition.source_holo:
            return Path(acquisition.source_holo.path).parent
        return None

    for stage in STAGE_ORDER:
        result = acquisition.stages[stage]
        if STAGE_LABELS[stage] == stage_label and result.stage_dir:
            return Path(result.stage_dir.path)
    return None


def _folder_options(files: List[FileRef], base_dir: Optional[Path]) -> List[str]:
    folders = {_folder_label(file_ref, base_dir) for file_ref in files}
    return sorted(folders, key=lambda value: (value != "Stage root", value.lower()))


def _filter_media(
    files: List[FileRef],
    base_dir: Optional[Path],
    selected_folder: str,
    selected_type: str,
    search: str,
) -> List[FileRef]:
    filtered = list(files)
    if selected_folder != "All folders":
        filtered = [file_ref for file_ref in filtered if _folder_label(file_ref, base_dir) == selected_folder]

    if selected_type == "Images":
        filtered = [file_ref for file_ref in filtered if Path(file_ref.path).suffix.lower() in IMAGE_SUFFIXES]
    elif selected_type == "Videos":
        filtered = [file_ref for file_ref in filtered if Path(file_ref.path).suffix.lower() in VIDEO_SUFFIXES]

    if search:
        normalized_search = search.lower()
        filtered = [
            file_ref
            for file_ref in filtered
            if normalized_search in file_ref.name.lower()
            or normalized_search in _folder_label(file_ref, base_dir).lower()
        ]

    return sorted(filtered, key=lambda file_ref: (_folder_label(file_ref, base_dir).lower(), file_ref.name.lower()))


def _media_label(file_ref: FileRef, base_dir: Optional[Path]) -> str:
    return f"{_folder_label(file_ref, base_dir)} / {file_ref.name}"


def _folder_label(file_ref: FileRef, base_dir: Optional[Path]) -> str:
    parent = Path(file_ref.path).parent
    if base_dir is not None:
        try:
            relative = parent.relative_to(base_dir)
            if str(relative) == ".":
                return "Stage root"
            return str(relative).replace("\\", "/")
        except ValueError:
            pass
    return parent.name or "Stage root"


def prepare_browser_video(source: Path) -> Tuple[Optional[Path], Optional[str]]:
    cache_path = _video_cache_path(source)
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path, None

    ffmpeg = _ffmpeg_executable()
    if not ffmpeg:
        return None, "No ffmpeg executable is available."

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        "scale=1280:-2:force_original_aspect_ratio=decrease",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "24",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(cache_path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)

    if completed.returncode != 0:
        cache_path.unlink(missing_ok=True)
        return None, completed.stderr.strip() or "ffmpeg returned a non-zero exit code."

    return cache_path, None


def _video_cache_path(source: Path) -> Path:
    try:
        stat = source.stat()
        fingerprint = f"{source.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        fingerprint = str(source)
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
    return _video_cache_dir() / f"{digest}.mp4"


def _video_cache_dir() -> Path:
    return _user_cache_root() / "video_previews"


def _user_cache_root() -> Path:
    base = os.getenv("LOCALAPPDATA")
    if base:
        return Path(base) / "DopplerManager" / ".doppler_cache"
    return Path(tempfile.gettempdir()) / "DopplerManager" / ".doppler_cache"


def _ffmpeg_executable() -> Optional[str]:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")
