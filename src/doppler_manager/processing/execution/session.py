from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from threading import Lock, Thread
from typing import Optional

from doppler_manager.processing.core.constants import PROGRESS_LOG_PREFIX
from doppler_manager.processing.core.models import JobResult, ProcessingJob

from .runner import run_processing_jobs


PROCESSING_LOG_MANAGER_APP = "DopplerManager"
DEFAULT_LOG_LIMIT = 700


@dataclass(frozen=True)
class ProcessingRunSnapshot:
    """Thread-safe view of a processing run for the Streamlit UI."""

    status: str
    log_entries: tuple[dict[str, object], ...]
    results: tuple[JobResult, ...]
    error: Optional[str]


class ProcessingRun:
    """Execute one immutable processing request independently of Streamlit reruns.

    Streamlit may stop the script that started a run as soon as another widget is
    clicked.  The worker deliberately never touches Streamlit state; it owns the
    request and its logs until all jobs have finished.
    """

    def __init__(
        self,
        jobs: Sequence[ProcessingJob],
        *,
        selected_file_ids: Sequence[str],
        allowed_apps: Sequence[str],
        log_limit: int = DEFAULT_LOG_LIMIT,
    ) -> None:
        self.jobs = tuple(jobs)
        self.selected_file_ids = tuple(str(file_id) for file_id in selected_file_ids)
        self.allowed_apps = tuple(str(app) for app in allowed_apps)
        self._logs: deque[dict[str, object]] = deque(maxlen=log_limit)
        self._lock = Lock()
        self._status = "pending"
        self._results: tuple[JobResult, ...] = ()
        self._error: Optional[str] = None
        self._thread: Thread | None = None
        self._current_file_ids: tuple[str, ...] = ()
        self._current_app = PROCESSING_LOG_MANAGER_APP
        self._last_log_was_progress = False
        self._completion_claimed = False

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("Processing run has already been started.")
            self._thread = Thread(
                target=self._execute,
                name="doppler-manager-processing",
                daemon=True,
            )
            self._thread.start()

    def snapshot(self) -> ProcessingRunSnapshot:
        with self._lock:
            return ProcessingRunSnapshot(
                status=self._status,
                log_entries=tuple(
                    {
                        "line": str(entry["line"]),
                        "files": tuple(entry["files"]),
                        "app": str(entry["app"]),
                    }
                    for entry in self._logs
                ),
                results=self._results,
                error=self._error,
            )

    @property
    def is_running(self) -> bool:
        return self.snapshot().status in {"pending", "running"}

    def claim_completion(self) -> bool:
        """Claim finalization once, so periodic UI reruns cannot duplicate it."""

        with self._lock:
            if self._status not in {"finished", "failed"} or self._completion_claimed:
                return False
            self._completion_claimed = True
            return True

    def append_manager_log(self, line: str) -> None:
        """Add a UI-owned log entry after the worker has finished."""

        with self._lock:
            self._current_file_ids = ()
            self._current_app = PROCESSING_LOG_MANAGER_APP
            self._append_log_locked(line)

    def _execute(self) -> None:
        with self._lock:
            self._status = "running"

        try:
            results = run_processing_jobs(
                self.jobs,
                self._append_log,
                on_job=self._set_job_context,
            )
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"[FAIL] Processing worker stopped unexpectedly: {exc}")
            with self._lock:
                self._error = str(exc)
                self._status = "failed"
            return

        with self._lock:
            self._results = tuple(results)
            self._status = "finished"

    def _set_job_context(self, job: ProcessingJob) -> None:
        if job.acquisition_id == "__angioeye_postprocess__":
            file_ids = self.selected_file_ids
        else:
            file_ids = (job.acquisition_id,)

        with self._lock:
            self._current_file_ids = file_ids
            self._current_app = self._processing_app_label(job.stage)

    def _append_log(self, line: str) -> None:
        with self._lock:
            self._append_log_locked(line)

    def _append_log_locked(self, line: str) -> None:
        is_progress_update = line.startswith(PROGRESS_LOG_PREFIX)
        if is_progress_update:
            line = line[len(PROGRESS_LOG_PREFIX) :]

        if is_progress_update and self._last_log_was_progress and self._logs:
            self._logs[-1]["line"] = line
        else:
            self._logs.append(
                {
                    "line": line,
                    "files": self._current_file_ids,
                    "app": self._current_app,
                }
            )
        self._last_log_was_progress = is_progress_update

    @staticmethod
    def _processing_app_label(stage: str) -> str:
        labels = {
            "hd": "Holodoppler",
            "dv": "DopplerView",
            "ef": "EyeFlow",
            "ae": "AngioEye",
            "ae_postprocess": "AngioEye",
        }
        return labels.get(stage, stage)
