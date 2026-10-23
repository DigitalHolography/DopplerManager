"""Runtime import and CLI probes; all evidence is written outside the runtime."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import ProxyHandler, build_opener

from doppler_manager.runtime.manifest import invocation

def runtime_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    from doppler_manager.runtime.apps import RUNTIMES
    env.pop("DM_PROCESSING_RUNTIME_ROOT", None)
    env.pop("DM_PROCESSING_LOG", None)
    for runtime in RUNTIMES.values():
        env.pop(runtime.environment_variable, None)
        env.pop(f"DM_{runtime.project_name.upper()}_COMMAND", None)
    # Configs, model caches and logs from validation must not overwrite a running app's.
    env.update(APPDATA=str(root / "roaming"), LOCALAPPDATA=str(root / "local"),
               MPLCONFIGDIR=str(root / "matplotlib"), HF_HOME=str(root / "huggingface"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    for key in ("APPDATA", "LOCALAPPDATA", "MPLCONFIGDIR", "HF_HOME"):
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    return env


IMPORTS = {
    "manager": "import streamlit, h5py, pandas; import doppler_manager.app",
    "holodoppler": "import holodoppler.cli",
    "dopplerview": "import dopplerview.cli",
    "eyeflow": "from launcher import cli_main; import eye_flow",
    "angioeye": "from launcher import cli_main; import angio_eye",
}


def validate_http(command: list[str], *, output: Path, timeout: float = 60) -> dict:
    """Exercise the frozen server, rather than only importing its dependencies."""
    output.mkdir(parents=True, exist_ok=True)
    env = runtime_env(output / "appdata")
    state = Path(env["LOCALAPPDATA"]) / "DopplerManager/server_state.json"
    # Each probe owns its state, logs and process; never reuse a developer server.
    state.unlink(missing_ok=True)
    opener = build_opener(ProxyHandler({}))
    with (output / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [*command, "--no-browser"], env=env, cwd=output, stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + timeout
            detail = "Server state was not written"
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Frozen server exited with {process.returncode}; see {output}")
                try:
                    url = json.loads(state.read_text(encoding="utf-8"))["url"]
                    with opener.open(urljoin(url, "/_stcore/health"), timeout=1) as response:
                        if response.status == 200 and response.read().strip() == b"ok":
                            break
                except (OSError, URLError, ValueError, KeyError) as exc:
                    detail = str(exc)
                time.sleep(0.1)
            else:
                raise RuntimeError(f"Frozen server did not answer HTTP requests: {detail}; see {output}")
            with opener.open(url, timeout=5) as response:
                html = response.read().decode("utf-8")
            assets = re.findall(r'src=["\']([^"\']+\.js(?:\?[^"\']*)?)["\']', html)
            if not assets:
                raise RuntimeError("Frozen server did not serve the Streamlit frontend")
            for asset in assets:
                with opener.open(urljoin(url + "/", asset), timeout=5) as response:
                    if not response.read():
                        raise RuntimeError(f"Empty frontend asset: {asset}")
            record = {"app": "manager", "check": "http", "url": url, "assets": assets, "returncode": 0}
            (output / "validation.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            return record
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def validate(root: Path, *, output: Path, frozen_exe: Path | None = None) -> list[dict]:
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Validation output must be outside the runtime directory")
    manifest = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    env = runtime_env(output / "appdata")
    evidence = []
    from doppler_manager.runtime.apps import RUNTIMES
    launchers = {v.project_name: v.launcher_args for v in RUNTIMES.values()}
    for app in manifest["apps"]:
        commands = [invocation(root, app, ("-c", IMPORTS[app] + "; print('IMPORT_OK')"))]
        if app in launchers:
            commands.append(invocation(root, app, (*launchers[app], "--help")))
        if frozen_exe and app in launchers:
            stage = next(k for k, v in RUNTIMES.items() if v.project_name == app)
            commands.append((str(frozen_exe), "--dm-processing-cli", stage, "--help"))
        for command in commands:
            result = subprocess.run(command, env=env, cwd=root, capture_output=True,
                                    text=True, errors="replace", timeout=180,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            record = {"app": app, "command": list(command), "returncode": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr}
            evidence.append(record)
            if result.returncode:
                (output / "validation.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
                raise RuntimeError(f"Runtime validation failed for {app}: {result.stderr or result.stdout}")
    (output / "validation.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return evidence
