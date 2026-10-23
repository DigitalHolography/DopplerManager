import os
import subprocess
import sys
from pathlib import Path


def test_application_imports_do_not_load_build_tooling():
    source = Path(__file__).resolve().parents[2] / "src"
    command = """
import sys
import doppler_manager.launcher
import doppler_manager.app
from doppler_manager.runtime.manifest import invocation, selected_generation
assert not any(name == 'doppler_manager.tooling' or name.startswith('doppler_manager.tooling.') for name in sys.modules)
"""
    subprocess.run([sys.executable, "-c", command],
                   env={**os.environ, "PYTHONPATH": str(source)}, check=True,
                   capture_output=True, text=True)
