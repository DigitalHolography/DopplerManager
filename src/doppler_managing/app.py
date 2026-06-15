from __future__ import annotations

from doppler_managing.app_core import main as _main
from doppler_managing.ui.processing import render_processing_tab


def main() -> None:
    _main(processing_renderer=render_processing_tab)


if __name__ == "__main__":
    main()
