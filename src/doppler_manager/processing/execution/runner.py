from __future__ import annotations

import codecs
import os
import shutil
import subprocess
import time
import traceback
from collections.abc import Callable, Sequence

from doppler_manager.logs import processing_log, processing_log_path
from doppler_manager.runtime.external_process import external_library_search
from doppler_manager.processing.core.constants import PROGRESS_LOG_PREFIX
from doppler_manager.processing.core.models import JobResult, ProcessingJob
from doppler_manager.processing.runtimes import runtime_environment

from .outputs import (
    install_angioeye_output,
    install_eyeflow_output,
    job_temp_root,
    prepare_processing_output,
)


def run_processing_jobs(
    jobs: Sequence[ProcessingJob],
    on_log: Callable[[str], None],
    on_job: Callable[[ProcessingJob], None] | None = None,
) -> list[JobResult]:
    results: list[JobResult] = []
    failed_acquisitions: set[str] = set()

    for job in jobs:
        if on_job is not None:
            on_job(job)
        with processing_log(
            job.stage, job.acquisition_id, job.command, job.cwd, on_log
        ) as emit:
            if job.acquisition_id in failed_acquisitions:
                emit(f"[SKIP] {job.description}: upstream stage failed.")
                continue

            emit(f"[START] {job.description}")
            try:
                prepare_processing_output(job, emit)
            except Exception as exc:  # noqa: BLE001
                result = JobResult(job=job, returncode=1)
                results.append(result)
                failed_acquisitions.add(job.acquisition_id)
                emit(f"[FAIL] Could not prepare {job.description}: {exc}\n{traceback.format_exc()}")
                continue

            emit(f"[CMD] {format_command(job.command)}")
            try:
                result = run_single_job(job, emit)
                if result.succeeded and job.stage == "ef":
                    install_eyeflow_output(job, emit)
                if result.succeeded and job.stage == "ae":
                    install_angioeye_output(job, emit)
            except Exception as exc:  # noqa: BLE001
                emit(f"[FAIL] Could not execute {job.description}: {exc}\n{traceback.format_exc()}")
                result = JobResult(job=job, returncode=1)
            results.append(result)

            if result.succeeded:
                emit(f"[OK] {job.description} exited with code {result.returncode}.")
            else:
                failed_acquisitions.add(job.acquisition_id)
                emit(f"[FAIL] {job.description} exited with code {result.returncode}.")

    return results


def format_command(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return " ".join(quote(arg) for arg in command)


def run_single_job(job: ProcessingJob, on_log: Callable[[str], None]) -> JobResult:
    temp_root = job_temp_root(job)
    if temp_root is not None:
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

    runtime_stage = "ae" if job.stage == "ae_postprocess" else job.stage
    env = runtime_environment(runtime_stage)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["DM_PROCESSING_LOG"] = str(
        processing_log_path(job.stage, job.acquisition_id, job.command)
    )

    try:
        with external_library_search():
            process = subprocess.Popen(
                list(job.command),
                cwd=str(job.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                bufsize=0,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except FileNotFoundError as exc:
        on_log(f"[FAIL] Could not launch {job.command[0]} (cwd={job.cwd}): {exc}")
        return JobResult(job=job, returncode=127)

    assert process.stdout is not None
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    buffer = ""
    pending_carriage_return = False
    current_line_is_progress = False

    def emit_buffer(*, progress: bool) -> None:
        nonlocal buffer
        text = buffer.strip()
        if text:
            prefix = PROGRESS_LOG_PREFIX if progress else ""
            on_log(f"{prefix}{text}")
        buffer = ""

    def handle_output_char(char: str) -> None:
        nonlocal buffer, pending_carriage_return, current_line_is_progress
        if pending_carriage_return:
            if char == "\n":
                emit_buffer(progress=current_line_is_progress)
                current_line_is_progress = False
                pending_carriage_return = False
                return
            if char == "\r":
                return
            emit_buffer(progress=True)
            current_line_is_progress = True
            pending_carriage_return = False

        if char == "\r":
            pending_carriage_return = True
        elif char == "\n":
            emit_buffer(progress=current_line_is_progress)
            current_line_is_progress = False
        else:
            buffer += char

    while True:
        chunk = process.stdout.read(1)
        if chunk == b"" and process.poll() is not None:
            break
        if chunk == b"":
            time.sleep(0.05)
            continue
        for char in decoder.decode(chunk):
            handle_output_char(char)

    for char in decoder.decode(b"", final=True):
        handle_output_char(char)

    trailing = buffer.strip()
    if trailing:
        prefix = PROGRESS_LOG_PREFIX if current_line_is_progress else ""
        on_log(f"{prefix}{trailing}")

    return JobResult(job=job, returncode=process.wait())


def quote(value: str) -> str:
    if not value or any(char.isspace() for char in value):
        return "'" + value.replace("'", "'\"'\"'") + "'"
    return value
