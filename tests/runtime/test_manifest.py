import json
import subprocess
import sys
from pathlib import Path

import pytest

from doppler_manager.runtime.manifest import selected_generation


def test_generation_pointer_never_accepts_unvalidated_or_external_paths(tmp_path):
    (tmp_path / "current.json").write_text(json.dumps({"generation": "../outside"}))
    with pytest.raises(RuntimeError, match="Invalid"):
        selected_generation(tmp_path)
    (tmp_path / "current.json").write_text(json.dumps({"generation": "generations/new"}))
    with pytest.raises(RuntimeError, match="Incomplete"):
        selected_generation(tmp_path)


