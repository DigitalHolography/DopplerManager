from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .release_defaults import sync_processing_defaults


APP_NAME = "DopplerManager"
LOG_FILE_NAME = "DopplerManager.log"
STATE_FILE_NAME = "server_state.json"
PORT_HOST = "127.0.0.1"
PORT_START = 8501
PORT_END = 8599
FINGERPRINT_FORMAT = "doppler-manager-v1"
PROCESSING_CLI_SENTINEL = "--dm-processing-cli"


class _HashWriter(Protocol):
    def update(self, data: bytes) -> object: ...


def main() -> None:
    log_path = _log_path()
    _configure_stdio(log_path)
    _log(log_path, "Launcher started.")
    if PROCESSING_CLI_SENTINEL in sys.argv:
        raise SystemExit(_run_processing_cli_from_argv())
    try:
        if "--stop" in sys.argv:
            _stop_running_server(log_path)
            return
        _run(log_path)
    except SystemExit as exc:
        if exc.code not in (None, 0):
            _log(log_path, f"Streamlit exited with code {exc.code}.")
            _show_startup_error(log_path)
        raise
    except Exception:  # noqa: BLE001
        _log(log_path, traceback.format_exc())
        _show_startup_error(log_path)
        raise


def launch() -> None:
    log_path = _log_path()
    _log(log_path, "Development launcher started.")
    _stop_recorded_server(log_path)
    synced_defaults = sync_processing_defaults()
    _log(log_path, f"Synced {len(synced_defaults)} processing default files.")
    _run(
        log_path,
        app_module="doppler_manager.app",
        file_watcher_type="auto",
    )


def _run_processing_cli_from_argv() -> int:
    sentinel_index = sys.argv.index(PROCESSING_CLI_SENTINEL)
    args = sys.argv[sentinel_index + 1 :]
    if not args:
        print("Expected processing stage after --dm-processing-cli.", file=sys.stderr)
        return 2

    stage = args[0].lower()
    tool_args = args[1:]
    if stage == "hd":
        from holodoppler.cli import main as holodoppler_main

        sys.argv = ["holodoppler", *tool_args]
        return int(holodoppler_main())
    if stage == "dv":
        import runpy

        sys.argv = ["dopplerview", *tool_args]
        runpy.run_module("dopplerview.cli", run_name="__main__")
        return 0
    if stage in {"ef", "ae"}:
        from doppler_manager import _external_cli_runner

        tool = "eyeflow" if stage == "ef" else "angioeye"
        return _external_cli_runner.main([tool, *tool_args])

    print(f"Unknown processing stage: {stage}", file=sys.stderr)
    return 2


def _run(
    log_path: Path,
    *,
    app_module: str = "doppler_manager.app",
    file_watcher_type: str = "none",
) -> None:
    fingerprint = _application_fingerprint()
    _reuse_running_server_if_available(log_path, fingerprint)
    _verify_app_importable(log_path, app_module)

    from streamlit.web import cli as streamlit_cli

    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")

    app_script = f"from {app_module} import main\n\nmain()\n"
    script_path = _runtime_script_path()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    if not script_path.exists() or script_path.read_text(encoding="utf-8") != app_script:
        script_path.write_text(app_script, encoding="utf-8")

    port = _available_port()
    url = f"http://{PORT_HOST}:{port}"
    _log(log_path, f"Starting Streamlit on {url}.")
    _write_server_state(port=port, url=url, fingerprint=fingerprint, log_path=log_path)
    _open_browser_when_ready(url, PORT_HOST, port, log_path)

    sys.argv = [
        "streamlit",
        "run",
        str(script_path),
        "--server.headless=true",
        f"--server.address={PORT_HOST}",
        f"--server.port={port}",
        f"--server.fileWatcherType={file_watcher_type}",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    try:
        raise SystemExit(streamlit_cli.main())
    finally:
        _clear_server_state(log_path)


def _runtime_script_path() -> Path:
    return _runtime_dir() / "streamlit_app.py"


def _log_path() -> Path:
    path = _runtime_dir() / "logs" / LOG_FILE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return _runtime_dir() / STATE_FILE_NAME


def _runtime_dir() -> Path:
    base = os.getenv("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path(tempfile.gettempdir()) / APP_NAME


def _verify_app_importable(log_path: Path, module_name: str) -> None:
    try:
        importlib.import_module(module_name)
    except Exception:  # noqa: BLE001
        _log(log_path, f"App import preflight failed for {module_name}.")
        raise


def _reuse_running_server_if_available(log_path: Path, fingerprint: str) -> None:
    state = _read_server_state(log_path)
    if not state:
        return

    port = int(state.get("port") or 0)
    url = str(state.get("url") or "")
    pid = int(state.get("pid") or 0)
    server_fingerprint = str(state.get("fingerprint") or "")
    if port <= 0 or not url:
        return

    if _can_connect(PORT_HOST, port):
        if server_fingerprint == fingerprint:
            _log(log_path, f"Existing server detected at {url} (pid {pid}).")
            _open_browser(url, log_path)
            raise SystemExit(0)

        reason = "missing" if not server_fingerprint else "different"
        _log(
            log_path,
            f"Existing server fingerprint is {reason}; replacing pid {pid}.",
        )
        if pid > 0 and _pid_is_running(pid):
            _terminate_process_tree(pid, log_path)
            _wait_for_port_to_close(PORT_HOST, port)
        _clear_server_state(log_path)
        return

    if pid and not _pid_is_running(pid):
        _log(log_path, f"Removing stale server state for pid {pid}.")
        _clear_server_state(log_path)


def _read_server_state(log_path: Path) -> dict[str, object] | None:
    path = _state_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log(log_path, f"Unable to read server state: {exc}")
        return None


def _write_server_state(
    *,
    port: int,
    url: str,
    fingerprint: str,
    log_path: Path,
) -> None:
    payload = {
        "pid": os.getpid(),
        "port": port,
        "url": url,
        "fingerprint": fingerprint,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        _state_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        _log(log_path, f"Unable to write server state: {exc}")


def _clear_server_state(log_path: Path) -> None:
    try:
        _state_path().unlink(missing_ok=True)
    except OSError as exc:
        _log(log_path, f"Unable to clear server state: {exc}")


def _application_fingerprint() -> str:
    hasher = hashlib.sha256()
    hasher.update(FINGERPRINT_FORMAT.encode("utf-8"))
    hasher.update(b"\0")

    if getattr(sys, "frozen", False):
        _update_hash_from_file(hasher, Path(sys.executable))
    else:
        package_dir = Path(__file__).resolve().parent
        for path in sorted(package_dir.rglob("*.py")):
            hasher.update(path.relative_to(package_dir).as_posix().encode("utf-8"))
            hasher.update(b"\0")
            _update_hash_from_file(hasher, path)

    return hasher.hexdigest()


def _update_hash_from_file(hasher: _HashWriter, path: Path) -> None:
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)


def _stop_running_server(log_path: Path) -> None:
    if _stop_recorded_server(log_path):
        _show_message("Doppler Manager", "Doppler Manager server was stopped.")
    else:
        _show_message("Doppler Manager", "No running Doppler Manager server was found.")


def _stop_recorded_server(log_path: Path) -> bool:
    state = _read_server_state(log_path)
    if not state:
        _log(log_path, "No running server state found.")
        return False

    pid = int(state.get("pid") or 0)
    if pid <= 0 or not _pid_is_running(pid):
        _clear_server_state(log_path)
        return False

    _log(log_path, f"Stopping server pid {pid}.")
    _terminate_process_tree(pid, log_path)
    port = int(state.get("port") or 0)
    if port > 0:
        _wait_for_port_to_close(PORT_HOST, port)
    _clear_server_state(log_path)
    return True


def _terminate_process_tree(pid: int, log_path: Path) -> None:
    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=15,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        _log(log_path, detail or f"Unable to stop server pid {pid}.")
        raise RuntimeError(f"Unable to stop server pid {pid}.")


def _wait_for_port_to_close(host: str, port: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not _can_connect(host, port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Server port {host}:{port} remained open after shutdown.")


def _pid_is_running(pid: int) -> bool:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0 and str(pid) in completed.stdout


def _available_port() -> int:
    for port in range(PORT_START, PORT_END + 1):
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((PORT_HOST, port)) != 0:
                return port
    raise RuntimeError(f"No available localhost port found between {PORT_START} and {PORT_END}.")


def _open_browser_when_ready(url: str, host: str, port: int, log_path: Path) -> None:
    def worker() -> None:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if _can_connect(host, port):
                _open_browser(url, log_path)
                return
            time.sleep(0.25)
        _log(log_path, f"Timed out waiting for Streamlit at {url}.")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def _can_connect(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _open_browser(url: str, log_path: Path) -> None:
    _log(log_path, f"Opening browser: {url}")
    try:
        if webbrowser.open(url, new=2):
            return
    except Exception as exc:  # noqa: BLE001
        _log(log_path, f"webbrowser.open failed: {exc}")

    if hasattr(os, "startfile"):
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return
        except OSError as exc:
            _log(log_path, f"os.startfile failed: {exc}")

    _log(log_path, f"Could not open browser automatically. Use this URL manually: {url}")


def _configure_stdio(log_path: Path) -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return

    stream = log_path.open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def _log(log_path: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        for line in message.rstrip().splitlines() or [""]:
            handle.write(f"[{timestamp}] {line}\n")


def _show_startup_error(log_path: Path) -> None:
    message = (
        "Doppler Manager could not start.\n\n"
        f"Diagnostic log:\n{log_path}"
    )
    _show_message("Doppler Manager", message, error=True, log_path=log_path)


def _show_message(
    title: str,
    message: str,
    *,
    error: bool = False,
    log_path: Path | None = None,
) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if error:
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        if log_path is not None:
            _log(log_path, message)


if __name__ == "__main__":
    main()
