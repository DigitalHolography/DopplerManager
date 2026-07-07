from __future__ import annotations

import importlib
import sys


def test_processing_cli_sentinel_dispatches_external_runner(monkeypatch) -> None:
    from doppler_manager import _external_cli_runner, launcher

    calls = []
    monkeypatch.setattr(
        _external_cli_runner,
        "main",
        lambda args: calls.append(args) or 7,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "DopplerManager.exe",
            launcher.PROCESSING_CLI_SENTINEL,
            "ef",
            "--data",
            "sample.holo",
        ],
    )

    assert launcher._run_processing_cli_from_argv() == 7
    assert calls == [["eyeflow", "--data", "sample.holo"]]


def test_app_entrypoint_imports_processing_modules() -> None:
    for module_name in (
        "doppler_manager.app",
        "doppler_manager.processing",
        "doppler_manager.ui.processing",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("doppler_manager.app")

    assert "doppler_manager.processing" in sys.modules
    assert "doppler_manager.ui.processing" in sys.modules


def test_scan_root_drop_helper_is_optional_when_component_is_not_registered(monkeypatch) -> None:
    from doppler_manager.ui import scan

    def broken_helper(**_kwargs) -> None:
        raise ValueError("Component 'scan_root_drop_helper' is not registered")

    monkeypatch.setattr(scan, "_SCAN_ROOT_DROP_HELPER", broken_helper)

    scan._render_scan_root_drop_helper()
