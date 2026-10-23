import pytest


@pytest.fixture(autouse=True)
def isolate_application_logs(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
