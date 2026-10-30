"""Exercise processing from a parent without Python stdio, as in a GUI build."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from doppler_manager.runtime import bootstrap
from doppler_manager.runtime.external_process import run_external


def test_windowless_processing_streams_utf8_stdout_and_stderr_live(tmp_path, monkeypatch):
    generation = tmp_path / "runtimes" / "generations" / "test"
    packages = generation / "packages"
    packages.mkdir(parents=True)
    shutil.copy2(bootstrap.__file__, generation / "bootstrap.py")
    (generation / "ready.json").write_text("{}")
    (generation.parent.parent / "current.json").write_text(json.dumps({"generation": "generations/test"}))
    (generation / "runtime.json").write_text(json.dumps({"apps": {"eyeflow": {
        "python": sys.executable, "paths": ["packages"],
    }}}))
    ack = tmp_path / "ack"
    (packages / "launcher.py").write_text(
        "import os, sys, time\nfrom pathlib import Path\n"
        "def cli_main():\n"
        "    print('ready café')\n"
        "    print('stderr message', file=sys.stderr)\n"
        "    deadline = time.monotonic() + 5\n"
        "    while not Path(os.environ['PROBE_ACK']).exists():\n"
        "        if time.monotonic() > deadline: return 3\n"
        "        time.sleep(0.02)\n"
        "    if sys.platform == 'win32':\n"
        "        import ctypes\n"
        "        if ctypes.windll.kernel32.GetConsoleWindow(): return 4\n"
        "    return 7\n",
        encoding="utf-8",
    )
    result_file = tmp_path / "result.json"
    probe = tmp_path / "probe.py"
    source = Path(__file__).resolve().parents[2] / "src"
    probe.write_text(
        "import json, os, sys, traceback\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(source)!r})\n"
        "from doppler_manager.processing.core.commands import command_prefix_for_stage\n"
        "from doppler_manager.processing.core.models import ProcessingJob\n"
        "from doppler_manager.processing.execution.runner import run_single_job\n"
        "sys.frozen = True\n"
        "try:\n"
        "    if os.name == 'nt': assert sys.stdout is None and sys.stderr is None\n"
        "    lines = []\n"
        "    def on_log(line):\n"
        "        lines.append(line)\n"
        "        if line == 'ready café': Path(os.environ['PROBE_ACK']).touch()\n"
        "    job = ProcessingJob('test', 'ef', command_prefix_for_stage('ef'), Path.cwd(), 'probe')\n"
        "    result = run_single_job(job, on_log)\n"
        "    payload = {'returncode': result.returncode, 'lines': lines}\n"
        "except BaseException:\n"
        "    payload = {'error': traceback.format_exc()}\n"
        f"Path({str(result_file)!r}).write_text(json.dumps(payload), encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DM_PROCESSING_RUNTIME_ROOT", str(generation.parent.parent))
    monkeypatch.setenv("PROBE_ACK", str(ack))
    python = Path(sys.executable)
    if os.name == "nt":
        python = python.with_name("pythonw.exe")
        assert python.is_file()
    subprocess.run(
        [str(python), str(probe)], cwd=tmp_path, check=True, timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert json.loads(result_file.read_text()) == {
        "returncode": 7, "lines": ["ready café", "stderr message"],
    }


def test_external_discovery_is_hidden_and_captures_both_streams():
    script = "import sys; print('catalog'); print('diagnostic', file=sys.stderr)"
    if os.name == "nt":
        script += "; import ctypes; assert not ctypes.windll.kernel32.GetConsoleWindow()"
    result = run_external([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "catalog"
    assert result.stderr.strip() == "diagnostic"
