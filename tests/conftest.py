import pytest


@pytest.fixture(autouse=True)
def isolate_application_logs(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    # A developer may have an active generation selected. Unit tests must not
    # delegate to it or read its server state when exercising the launcher.
    monkeypatch.setenv("DM_PROCESSING_RUNTIME_ROOT", str(tmp_path / "runtimes"))
    for app in ("HOLODOPPLER", "DOPPLERVIEW", "EYEFLOW", "ANGIOEYE"):
        monkeypatch.delenv(f"DM_{app}_PYTHON", raising=False)
        monkeypatch.delenv(f"DM_{app}_COMMAND", raising=False)
