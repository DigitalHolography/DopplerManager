from pathlib import Path
from doppler_manager.tooling.dependencies.manifest import runtime_manifest


def test_runtime_manifest_uses_upstream_holodoppler_requirements() -> None:
    manifest = runtime_manifest(Path("pyproject.toml"))

    assert manifest["hd"].python_version is None
    assert manifest["hd"].requirements == (
        "holodoppler @ git+https://github.com/DigitalHolography/HoloDoppler.git@main",
    )
    assert manifest["dv"].python_version is None
    assert manifest["ef"].python_version is None
    assert manifest["ae"].python_version is None


