from __future__ import annotations

import importlib
import sys


def test_scan_entrypoint_does_not_import_processing_modules() -> None:
    for module_name in (
        "doppler_managing.app_core",
        "doppler_managing.app_scan",
        "doppler_managing.processing",
        "doppler_managing.ui.processing",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("doppler_managing.app_scan")

    assert "doppler_managing.processing" not in sys.modules
    assert "doppler_managing.ui.processing" not in sys.modules


def test_scan_root_drop_helper_is_optional_when_component_is_not_registered(monkeypatch) -> None:
    from doppler_managing import app_core

    def broken_helper(**_kwargs) -> None:
        raise ValueError("Component 'scan_root_drop_helper' is not registered")

    monkeypatch.setattr(app_core, "_SCAN_ROOT_DROP_HELPER", broken_helper)

    app_core._render_scan_root_drop_helper()
