"""Keep the frozen manager's native library search out of external Pythons."""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from threading import RLock


_SPAWN_LOCK = RLock()


@contextmanager
def external_library_search():
    if os.name != "nt" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes
    kernel = ctypes.windll.kernel32
    with _SPAWN_LOCK:
        length = kernel.GetDllDirectoryW(0, None)
        previous = ctypes.create_unicode_buffer(length + 1)
        kernel.GetDllDirectoryW(len(previous), previous)
        kernel.SetDllDirectoryW(None)
        try:
            yield
        finally:
            kernel.SetDllDirectoryW(previous.value or None)


def run_external(command, *, capture_output=False, timeout=None, check=False, **kwargs):
    # Catalog discovery and CLI delegation also run from the windowed manager.
    # Without this flag, Windows allocates a console for the external Python.
    kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Restore the parent search path immediately after process creation, before
    # waiting for the child, so Streamlit threads retain their normal libraries.
    with external_library_search():
        process = subprocess.Popen(command, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        process.kill()
        process.communicate()
        raise
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check:
        result.check_returncode()
    return result
