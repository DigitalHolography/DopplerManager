from __future__ import annotations

import contextlib
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


APP_SCRIPT = """\
from doppler_managing.app_scan import main

main()
"""
APP_NAME = "DopplerManager"
LOG_FILE_NAME = "DopplerManagerScan.log"
STATE_FILE_NAME = "server_state.json"
PORT_HOST = "127.0.0.1"
PORT_START = 8501
PORT_END = 8599


def main() -> None:
    log_path = _log_path()
    _configure_stdio(log_path)
    _log(log_path, "Launcher started.")
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


def _run(log_path: Path) -> None:
    _reuse_running_server_if_available(log_path)
    _verify_app_importable(log_path)

    from streamlit.web import cli as streamlit_cli

    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")

    script_path = _runtime_script_path()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    if not script_path.exists() or script_path.read_text(encoding="utf-8") != APP_SCRIPT:
        script_path.write_text(APP_SCRIPT, encoding="utf-8")

    port = _available_port()
    url = f"http://{PORT_HOST}:{port}"
    _log(log_path, f"Starting Streamlit on {url}.")
    _write_server_state(port=port, url=url, log_path=log_path)
    _open_browser_when_ready(url, PORT_HOST, port, log_path)

    sys.argv = [
        "streamlit",
        "run",
        str(script_path),
        "--server.headless=true",
        f"--server.address={PORT_HOST}",
        f"--server.port={port}",
        "--server.fileWatcherType=none",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    try:
        raise SystemExit(streamlit_cli.main())
    finally:
        _clear_server_state(log_path)


def _runtime_script_path() -> Path:
    return _runtime_dir() / "streamlit_scan_app.py"


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


def _verify_app_importable(log_path: Path) -> None:
    try:
        import doppler_managing.app_scan  # noqa: F401
    except Exception:  # noqa: BLE001
        _log(log_path, "App import preflight failed.")
        raise


def _reuse_running_server_if_available(log_path: Path) -> None:
    state = _read_server_state(log_path)
    if not state:
        return

    port = int(state.get("port") or 0)
    url = str(state.get("url") or "")
    pid = int(state.get("pid") or 0)
    if port <= 0 or not url:
        return

    if _can_connect(PORT_HOST, port):
        _log(log_path, f"Existing server detected at {url} (pid {pid}).")
        _open_browser(url, log_path)
        raise SystemExit(0)

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


def _write_server_state(*, port: int, url: str, log_path: Path) -> None:
    payload = {
        "pid": os.getpid(),
        "port": port,
        "url": url,
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


def _stop_running_server(log_path: Path) -> None:
    state = _read_server_state(log_path)
    if not state:
        _log(log_path, "No running server state found.")
        _show_message("Doppler Manager Scan", "No running Doppler Manager Scan server was found.")
        return

    pid = int(state.get("pid") or 0)
    if pid <= 0 or not _pid_is_running(pid):
        _clear_server_state(log_path)
        _show_message("Doppler Manager Scan", "No running Doppler Manager Scan server was found.")
        return

    command = ["taskkill", "/PID", str(pid), "/T", "/F"]
    _log(log_path, f"Stopping server pid {pid}.")
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=15,
    )
    _clear_server_state(log_path)
    if completed.returncode == 0:
        _show_message("Doppler Manager Scan", "Doppler Manager Scan server was stopped.")
    else:
        _log(log_path, completed.stderr.strip() or completed.stdout.strip())
        _show_startup_error(log_path)


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
        "Doppler Manager Scan could not start.\n\n"
        f"Diagnostic log:\n{log_path}"
    )
    _show_message("Doppler Manager Scan", message, error=True, log_path=log_path)


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
