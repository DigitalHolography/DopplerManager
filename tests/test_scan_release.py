from __future__ import annotations

import importlib
import sys


def test_processing_cli_sentinel_dispatches_external_runner(monkeypatch) -> None:
    from doppler_manager import _external_cli_runner, launcher_scan

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
            launcher_scan.PROCESSING_CLI_SENTINEL,
            "ef",
            "--data",
            "sample.holo",
        ],
    )

    assert launcher_scan._run_processing_cli_from_argv() == 7
    assert calls == [["eyeflow", "--data", "sample.holo"]]


def test_scan_entrypoint_does_not_import_processing_modules() -> None:
    for module_name in (
        "doppler_manager.app_core",
        "doppler_manager.app_scan",
        "doppler_manager.processing",
        "doppler_manager.ui.processing",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("doppler_manager.app_scan")

    assert "doppler_manager.processing" not in sys.modules
    assert "doppler_manager.ui.processing" not in sys.modules


def test_scan_root_drop_helper_is_optional_when_component_is_not_registered(monkeypatch) -> None:
    from doppler_manager import app_core

    def broken_helper(**_kwargs) -> None:
        raise ValueError("Component 'scan_root_drop_helper' is not registered")

    monkeypatch.setattr(app_core, "_SCAN_ROOT_DROP_HELPER", broken_helper)

    app_core._render_scan_root_drop_helper()
