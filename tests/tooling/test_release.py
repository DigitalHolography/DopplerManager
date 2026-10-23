import json
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath

from doppler_manager.runtime import bootstrap
from doppler_manager.runtime.manifest import selected_generation
from doppler_manager.tooling import release


def test_frozen_runtime_compacts_paths_and_preserves_shared_imports(monkeypatch, tmp_path):
    generation = tmp_path / "source"
    package = "packages/" + "a" * 24
    other = "packages/" + "b" * 24
    for relative in (package, other, "python/3.13.14"):
        (generation / relative).mkdir(parents=True)
    (generation / "python/3.13.14/python.exe").write_bytes(b"python")
    (generation / package / "shared_probe.py").write_text("value = 42\n")
    (generation / other / "shared_probe.py").write_text("value = 99\n")
    long_name = (
        "torch/include/ATen/native/transformers/cuda/mem_eff_attention/"
        "iterators/predicated_tile_access_iterator_residual_last.h"
    )
    header = generation / package / long_name
    header.parent.mkdir(parents=True)
    header.write_bytes(b"header retained")
    apps = {
        name: {"python": "python/3.13.14/python.exe", "paths": paths}
        for name, paths in {
            "manager": ["unused"], "first": [package, other], "second": [package],
        }.items()
    }
    (generation / "runtime.json").write_text(json.dumps({"apps": apps}))
    (generation / "dependency-plan.json").write_text(json.dumps({"id": "c" * 24}))
    shutil.copy2(bootstrap.__file__, generation / "bootstrap.py")
    monkeypatch.setattr(release, "validate", lambda *_args, **_kwargs: None)

    container = release.stage_runtimes(generation, tmp_path / "output")
    moved = tmp_path / "relocated"
    container.rename(moved)
    root = selected_generation(moved)
    data = json.loads((root / "runtime.json").read_text())
    assert set(data["apps"]) == {"first", "second"}
    assert data["apps"]["first"]["paths"] == ["p/0", "p/1"]
    assert data["apps"]["second"]["paths"] == ["p/0"]
    assert (root / "p/0" / long_name).read_bytes() == b"header retained"
    assert (generation / package / "shared_probe.py").is_file()
    for app in data["apps"]:
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(root / "bootstrap.py"), app,
             "-c", "import shared_probe; assert shared_probe.value == 42"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
    install = PureWindowsPath("C:/Users/a-longer-username/AppData/Local/Programs/DopplerManager/1.7.3")
    for path in moved.rglob("*"):
        assert len(str(install / "_internal/processing_runtimes" / path.relative_to(moved))) < 248
