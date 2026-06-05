from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from doppler_managing.models import FileRef, STATUS_LABELS


STATUS_COLORS = {
    "complete": "#4ade80",
    "warning": "#fbbf24",
    "partial": "#60a5fa",
    "error": "#fb7185",
    "not_started": "#94a3b8",
    "unknown": "#94a3b8",
}


def status_text(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def status_badge(label: str, status: str) -> str:
    color = STATUS_COLORS.get(status, STATUS_COLORS["unknown"])
    text = status_text(status)
    return (
        f'<div class="dm-badge" style="border-color:{color}; color:{color};">'
        f'<span>{label}</span><strong>{text}</strong></div>'
    )


def format_size(size: Optional[int]) -> str:
    if size is None:
        return "unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def format_timestamp(timestamp: Optional[float]) -> str:
    if timestamp is None:
        return "unknown"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def extension(file_ref: FileRef) -> str:
    return Path(file_ref.name).suffix.lower() or "(none)"


def file_record(stage: str, category: str, file_ref: FileRef, status: str = "") -> Dict[str, object]:
    return {
        "Stage": stage,
        "Category": category,
        "Name": file_ref.name,
        "Extension": extension(file_ref),
        "Size": format_size(file_ref.size),
        "Size bytes": file_ref.size if file_ref.size is not None else "",
        "Modified": format_timestamp(file_ref.modified_ts),
        "Status": status,
        "Path": file_ref.path,
    }
