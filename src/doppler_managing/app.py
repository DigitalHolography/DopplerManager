from __future__ import annotations


def main() -> None:
    from doppler_managing.app_core import main as _main
    from doppler_managing.ui.processing import render_processing_tab

    _main(processing_renderer=render_processing_tab)


def launch() -> None:
    from doppler_managing import launcher_scan

    log_path = launcher_scan._log_path()
    launcher_scan._log(log_path, "Development launcher started.")
    launcher_scan._stop_recorded_server(log_path)
    launcher_scan._run(
        log_path,
        app_module="doppler_managing.app",
        file_watcher_type="auto",
    )


if __name__ == "__main__":
    main()
