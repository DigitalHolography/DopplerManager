from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuntimeStage = Literal["hd", "dv", "ef", "ae"]


@dataclass(frozen=True)
class ProcessingRuntime:
    stage: RuntimeStage
    project_name: str
    environment_variable: str
    launcher_args: tuple[str, ...]


RUNTIMES: dict[RuntimeStage, ProcessingRuntime] = {
    "hd": ProcessingRuntime(
        stage="hd",
        project_name="holodoppler",
        environment_variable="DM_HOLODOPPLER_PYTHON",
        launcher_args=(
            "-c",
            "from holodoppler.cli import main; raise SystemExit(main())",
        ),
    ),
    "dv": ProcessingRuntime(
        stage="dv",
        project_name="dopplerview",
        environment_variable="DM_DOPPLERVIEW_PYTHON",
        launcher_args=("-m", "dopplerview.cli"),
    ),
    "ef": ProcessingRuntime(
        stage="ef",
        project_name="eyeflow",
        environment_variable="DM_EYEFLOW_PYTHON",
        launcher_args=(
            "-c",
            "from launcher import cli_main; raise SystemExit(cli_main())",
        ),
    ),
    "ae": ProcessingRuntime(
        stage="ae",
        project_name="angioeye",
        environment_variable="DM_ANGIOEYE_PYTHON",
        launcher_args=(
            "-c",
            "from launcher import cli_main; raise SystemExit(cli_main())",
        ),
    ),
}
