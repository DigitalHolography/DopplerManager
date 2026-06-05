from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


STAGE_ORDER = ("hd", "dv", "ef", "ae")

STAGE_LABELS = {
    "hd": "Holodoppler",
    "dv": "DopplerView",
    "ef": "EyeFlow",
    "ae": "AngioEye",
}

STATUS_LABELS = {
    "not_started": "Not started",
    "partial": "Partial",
    "complete": "Complete",
    "warning": "Needs review",
    "error": "Error",
    "unknown": "Unknown",
}


@dataclass
class FileRef:
    path: str
    name: str
    size: Optional[int]
    modified_ts: Optional[float]
    kind: str

    @classmethod
    def from_path(cls, path: Path, kind: str) -> "FileRef":
        try:
            stat = path.stat()
            return cls(
                path=str(path),
                name=path.name,
                size=stat.st_size,
                modified_ts=stat.st_mtime,
                kind=kind,
            )
        except OSError:
            return cls(
                path=str(path),
                name=path.name,
                size=None,
                modified_ts=None,
                kind=kind,
            )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class StageResult:
    code: str
    label: str
    status: str = "not_started"
    stage_dir: Optional[FileRef] = None
    h5_files: List[FileRef] = field(default_factory=list)
    params_files: List[FileRef] = field(default_factory=list)
    version_files: List[FileRef] = field(default_factory=list)
    preview_files: List[FileRef] = field(default_factory=list)
    versions: Dict[str, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class AcquisitionResult:
    acquisition_id: str
    source_holo: Optional[FileRef] = None
    acquisition_dir: Optional[FileRef] = None
    stages: Dict[str, StageResult] = field(default_factory=dict)
    root_preview_files: List[FileRef] = field(default_factory=list)
    status: str = "unknown"
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    def to_row(self) -> Dict[str, object]:
        stage_warning_count = sum(
            len(stage.notes) + (1 if stage.status == "warning" else 0)
            for stage in self.stages.values()
        )
        stage_error_count = sum(1 for stage in self.stages.values() if stage.status == "error")
        row: Dict[str, object] = {
            "acquisition": self.acquisition_id,
            "status": self.status,
            "status_label": STATUS_LABELS.get(self.status, self.status),
            "source_holo": self.source_holo.path if self.source_holo else "",
            "acquisition_dir": self.acquisition_dir.path if self.acquisition_dir else "",
            "warnings": len(self.warnings) + stage_warning_count,
            "errors": len(self.errors) + stage_error_count,
        }
        for stage in STAGE_ORDER:
            result = self.stages.get(stage)
            row[f"{stage}_status"] = result.status if result else "unknown"
            row[f"{stage}_label"] = STATUS_LABELS.get(result.status, result.status) if result else "Unknown"
            row[f"{stage}_h5_count"] = len(result.h5_files) if result else 0
        return row


@dataclass
class ScanResult:
    root: str
    acquisitions: List[AcquisitionResult]
    visited_dirs: int = 0
    visited_entries: int = 0
    truncated: bool = False
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    def rows(self) -> List[Dict[str, object]]:
        return [acquisition.to_row() for acquisition in self.acquisitions]
