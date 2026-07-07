from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProcessingJob:
    acquisition_id: str
    stage: str
    command: tuple[str, ...]
    cwd: Path
    description: str
    ef_temp_root: Optional[Path] = None
    ef_destination: Optional[Path] = None
    ae_temp_root: Optional[Path] = None
    ae_destination: Optional[Path] = None
    stage_destination: Optional[Path] = None


@dataclass(frozen=True)
class JobResult:
    job: ProcessingJob
    returncode: int

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0

