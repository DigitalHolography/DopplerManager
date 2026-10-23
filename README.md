# Doppler Manager

Doppler Manager is a Streamlit application for tracking Doppler acquisitions stored on a NAS or a local drive. It scans a folder tree, checks the processing pipeline state, exposes parameters and tool versions, previews media, exports the acquisition index, and can run or rerun selected processing stages.

The application is an operational MVP. During scans, it does not load large `.holo` or `.h5` files into memory. It indexes paths, sizes, modification dates, small text/JSON files, and preview media.

## Supported Pipeline

The supported processing chain is:

```text
.holo -> HoloDoppler -> HD .h5 -> DopplerView -> DV .h5 -> EyeFlow -> EF .h5 -> AngioEye -> AE .h5
```

| Stage | Tool        | Expected inputs                            | Recognized outputs                                               |
| ----- | ----------- | ------------------------------------------ | ---------------------------------------------------------------- |
| HD    | HoloDoppler | Raw `<id>.holo` acquisition and settings JSON | `<id>_HD/h5/<id>_HD_output.h5`, JSON files, H5 app versions, previews |
| DV    | DopplerView | Acquisition with an available HD output    | `<id>_DV/h5/<id>_DV.h5`, config JSON, outputs under `output/`    |
| EF    | EyeFlow     | Acquisition with available HD and DV outputs | `<id>_EF/h5/<id>_EF.h5`, JSON files, previews                    |
| AE    | AngioEye    | EF `.h5` file                              | `<id>_AE/h5/<id>_AE.h5`                                         |

## Recognized Layout

The scanner can recognize an acquisition from a `.holo` file, an acquisition folder, or stage folders suffixed with `_HD`, `_DV`, `_EF`, or `_AE`.

Typical structure:

```text
root/
  251031_ALA_L_1.holo
  251031_ALA_L_1/
    251031_ALA_L_1_input_HD_params.json
    251031_ALA_L_1_HD/
      h5/
        251031_ALA_L_1_HD_output.h5
      json/
      png/
      avi/
      version_holodoppler.txt
      git_version.txt
      info_holodoppler.txt
    251031_ALA_L_1_DV/
      h5/
        251031_ALA_L_1_DV.h5
      config/
        DV_params.json
      output/
    251031_ALA_L_1_EF/
      h5/
        251031_ALA_L_1_EF.h5
      png/
    251031_ALA_L_1_AE/
      h5/
        251031_ALA_L_1_AE.h5
```

When present, `software_pipeline_validation/` is used as the local validation dataset and proposed as the default scan root.

## Status Model

Each acquisition has a global status and one status per stage:

| Status        | Meaning                                                                                   |
| ------------- | ----------------------------------------------------------------------------------------- |
| `not_started` | No artifact was recognized for the stage                                                  |
| `partial`     | The stage exists, but no usable `.h5` file was found                                      |
| `complete`    | The expected `.h5` file exists and is not empty                                           |
| `warning`     | The stage needs review: unexpected `.h5` name or missing source |
| `error`       | A blocking issue was detected, especially an empty `.h5` file                             |
| `unknown`     | The state could not be determined                                                         |

The global status is derived from stage statuses, warnings, and errors.

## User Interface

The Streamlit application provides three main tabs:

- `Acquisition Index`: filter by acquisition name, global status, missing HD, missing DV, or missing AE; view HD/DV/EF/AE statuses, warnings, errors, `.holo` presence, and acquisition folder presence.
- `Acquisition Details`: select a filtered acquisition, view status badges, and inspect `Parameters`, `Versions`, and `Media Preview` tabs.
- `Processing`: select acquisitions and stages to run or rerun, choose HoloDoppler settings, choose EyeFlow/AngioEye pipelines, follow real-time logs, and refresh the scan automatically after processing.

The scan bar accepts a typed or pasted path, a folder selected with `Browse`, and dropped paths when the browser provides a usable local path. Scan options control maximum depth, maximum inspected entries, indexed media per stage, and H5 app-version reading. The `Versions` detail tab reads the JSON dictionary stored at `/app_versions/` in each H5 and displays the complete dictionary, including upstream versions recorded by downstream applications. A stale upstream version is shown as a warning on the downstream stage, never as an error. Legacy text version files remain available in the detail view when present. The `Input filter` expander accepts an optional `.txt` filter list. When a filter list is uploaded, each non-empty line is treated as a `.holo` filename, full path, or acquisition ID, and only matching acquisitions are scanned. By default, no filter is applied.

## Media Preview

Media files are grouped by acquisition and tool. Filters let users choose a subfolder, file type, and filename search query.

The scanner indexes previews found in `png/`, `avi/`, the stage-folder root, and, with a bounded walk, `output/`.

Supported formats:

- Images: `.png`, `.jpg`, `.jpeg`
- Browser-native videos: `.mp4`, `.mov`, `.m4v`
- `.avi` videos: automatic cached MP4 conversion through `imageio-ffmpeg`, with a fallback to system `ffmpeg` when available

Generated MP4 files for AVI previews are stored in `%LOCALAPPDATA%\DopplerManager\.doppler_cache\video_previews\` on Windows, or in the system temp folder when `LOCALAPPDATA` is unavailable.

## Exports

The `Acquisition Index` tab exposes one scan-list export:

- `doppler_manager_scan_lists.zip`

The ZIP contains five text files:

- `missing_HD.txt`
- `missing_DV.txt`
- `missing_EF.txt`
- `missing_AE.txt`
- `all_scan_paths.txt`

The stage-specific files contain the `.holo` paths, limited to the active dashboard filters, for acquisitions where the corresponding stage is not already `complete`. `all_scan_paths.txt` contains every `.holo` path observed during the filesystem scan, without applying the dashboard filters or optional `.holo` filter list.

## Installation

The project targets Python 3.13 or newer.

Minimal installation for running the interface:

```bash
uv sync
```

Installation with processing tools:

```bash
uv run sync
```

Synchronization consumes `dependencies/windows-x86_64/runtime-lock.json` and its generated uv
projects and lockfiles. The graph covers DopplerManager, HoloDoppler, DopplerView,
EyeFlow, and AngioEye. The resolver selects the fewest supported Python versions;
identical package artifacts are installed once and exposed only to their app
profiles. Different versions and each app's top-level modules remain isolated.
The graph records sources, hashes, dependency edges, app ownership and Python
assignments. DopplerManager's frozen interpreter is accounted for separately.

```powershell
# Inspect or create a plan without changing processing environments:
uv run sync --plan-only
# Deliberately refresh upstream commits and dependency locks:
uv run sync --refresh --plan-only
# Install exactly the recorded plan:
uv run sync --locked
```

Inputs live in `[tool.doppler_manager.processing_runtimes]` and
`[tool.doppler_manager.dependency_plan]` in `pyproject.toml`. The initial Python
candidate preference is 3.13, then 3.14, then 3.12. HoloDoppler's Python and package
requirements come from its upstream metadata. Resolution errors
caused by network or build failures are not treated as version incompatibility.
Ordinary sync does not silently refresh a stale plan: refresh and review its
lock changes first. Commit the runtime lock and selected app project/lock files together. Candidate
resolutions and Python downloads stay in `.cache/doppler-manager/`.

Complete portable Python installations and shared package directories are stored
in immutable `processing_runtimes/generations/<id>/` directories. A validated
`current.json` pointer selects the generation for new jobs. Existing generations
and legacy `<app>/.venv` environments are retained for running jobs. Automatic
cleanup is deliberately disabled. Do not edit shared package directories.

To sync while the manager's development executable is in use, avoid uv's attempt
to reinstall that executable and invoke the module directly:

```powershell
.venv\Scripts\python.exe -m doppler_manager.tooling.sync --locked
```

On Windows, `.\scripts\sync_processing.ps1` also invokes that module. Successful
sync restores AE, EF and HD files in `processing_defaults/` from locked upstream
commits, even when the runtime generation is unchanged. For an isolated build or
test, supply `--environment-root <directory>` and `--defaults-output <directory>`.

## Run the Application

```bash
uv run dopplermanager
```

The development command stops any recorded Doppler Manager server before starting
the full application with Streamlit file watching enabled.
Running `streamlit run` directly bypasses this lifecycle check.
After graph synchronization, the development launcher delegates to the locked
manager profile while loading this checkout's source, so file watching still
works. The uv project environment serves as the tool host; the five app profiles
use the graph's selected dependencies and interpreters.

On first launch, select a NAS or local root folder and click `Scan`.

## Build the Windows Installer

The runtime/tooling boundary and lock layout are documented in
[Dependency tooling architecture](docs/dependency-tooling-architecture.md).

The release includes the acquisition scan views, the `Processing` tab, and all
four isolated processing runtimes.

Prerequisites on the Windows build machine:

- `uv`
- Inno Setup 6

Build the installer:

```powershell
.\scripts\build_installer.ps1
```

To override the release version:

```powershell
.\scripts\build_installer.ps1 -Version 1.7.3
```

The script consumes the committed dependency plan, generates a PyInstaller spec,
and stages a new isolated build under `build/release-<id>/`. It packages the
validated result with Inno Setup and creates:

```text
dist\installer\DopplerManager-<version>-setup.exe
```

The installer uses Inno Setup and installs the application under:

```text
%LOCALAPPDATA%\Programs\DopplerManager\<version>\
```

The packaged entry point is `src\doppler_manager\app.py`, which renders:

- `Acquisition Index`
- `Acquisition Details`
- `Processing`

Builds never overwrite the development runtimes. They retain generated specs,
validation results and the graph with the staged payload. The external processing
payload bypasses PyInstaller's manager binary analysis and includes complete
Python installations. All app imports and processing CLI help commands must pass
after relocation, including dispatch through the frozen executable, before Inno
Setup runs. Python need not be installed on the destination machine.

Pushing a tag `v<version>` also builds and uploads this installer through the Windows release workflow:

```powershell
git tag v1.7.3
git push origin v1.7.3
```

If the installed executable does not open a browser on another PC, check the diagnostic log:

```text
%APPDATA%\DopplerManager\logs\DopplerManager.log
```

This main log records application events and processing summaries. Full processing
output is saved in the `Holodoppler`, `DopplerView`, `EyeFlow`, and `AngioEye`
subfolders of the same logs directory. For example, DopplerView runs on `test.holo`
write to `%APPDATA%\DopplerManager\logs\DopplerView\test.log`.
Repeated runs append timestamped sections with a unique run ID, command, working
directory, output, errors, and exit status. These files retain all emitted log
lines independently of the UI's rolling log. Existing logs in LocalAppData are
left in place; new logs use Roaming AppData. Runtime state and preview caches
remain in LocalAppData because they are specific to this computer.

The installer also creates Start Menu shortcuts named:

- `Doppler Manager diagnostic log`
- `Stop Doppler Manager`

Launching the app again while it is already running reopens the existing local Streamlit server instead of starting another copy.

## Run Processing

In the `Processing` tab:

1. Select one or more acquisitions.
2. Select the stages to run in `Run or rerun`.
3. Enable `Only missing or needs review` to skip stages that are already `complete`.
4. If HD is selected, choose a HoloDoppler settings JSON file.
5. If EF or AE is selected, choose at least one pipeline.
6. Click `Run Processing`.

The application always enforces this execution order:

```text
HD -> DV -> EF -> AE
```

Before rerunning a stage, the application deletes only the expected result folder for the selected acquisition and stage, for example `<id>/<id>_EF`. After execution, it automatically scans again and keeps the latest logs in the interface.

Default commands select the active generation's complete Python installation and
run its bootstrap with `-I -S`. The bootstrap exposes only that app's package paths
before invoking `holodoppler.cli`, `dopplerview.cli`, or the isolated EyeFlow and
AngioEye `launcher` modules. Legacy `.venv` environments remain a fallback until
a generation has been synchronized.

Commands can be overridden with local executable paths:

- `DM_HOLODOPPLER_COMMAND`
- `DM_DOPPLERVIEW_COMMAND`
- `DM_EYEFLOW_COMMAND`
- `DM_ANGIOEYE_COMMAND`

The isolated interpreters can also be overridden when a runtime is installed
elsewhere:

- `DM_HOLODOPPLER_PYTHON`
- `DM_DOPPLERVIEW_PYTHON`
- `DM_EYEFLOW_PYTHON`
- `DM_ANGIOEYE_PYTHON`
- `DM_PROCESSING_RUNTIME_ROOT`: root containing `holodoppler/`, `dopplerview/`, `eyeflow/`, and `angioeye/`

HoloDoppler settings can be preconfigured with:

- `DM_HOLODOPPLER_SETTINGS`: path to a JSON or YAML file
- `DM_HOLODOPPLER_SETTINGS_DIR`: path to a folder containing JSON or YAML files

Settings discovery checks the installed HoloDoppler package, bundled defaults,
the scanned root's `parameters/` folder, and the explicit environment overrides
above. When available, `default_parameters_debug.json` is selected by default.
Only settings containing `temporal_transformation`, which is required by the
current HoloDoppler CLI, are preferred.

## EF and AE Pipelines

The default settings included in `processing_defaults/` define which pipelines are visible and which ones are selected by default.

EyeFlow:

- `waveform_shape_metrics` is selected by default.
- `dual_input_tutorial` is available but not selected by default.

AngioEye:

- `waveform_shape_metrics` is selected by default.
- `Windkessel_RC`, `lowrank_pulsatility_metrics`, `modal_analysis`, `waveform_harmonic_organization`, and `waveform_harmonic_organization_SVD` are available but not selected by default.

Temporary pipeline-selection files are generated under `.doppler_cache/processing/`.

## Tests

```bash
uv run pytest
```

## Code Structure

```text
processing_runtimes/             Isolated runtime support and environments
src/doppler_manager/
  app.py                       Streamlit entry point
  launcher.py                  Streamlit server lifecycle and release launcher
  models.py                    Scan data models
  processing/                  Job construction, external app calls, and execution
    apps/                      External app command builders
      holodoppler.py           HoloDoppler command builder
      dopplerview.py           DopplerView command builder
      eyeflow.py               EyeFlow command builder
      angioeye.py              AngioEye command builder
    config/                    Defaults, settings, and pipeline selection
    core/                      Job models, paths, commands, and orchestration
    execution/                 Subprocess runner and output installation
  runtime/                     App definitions, manifests, bootstrap and process isolation
  tooling/                     Dependency, sync, validation and release tools
  _external_cli_runner.py       Isolated processing runtime dispatcher
  scan/
    cache.py                   Streamlit scan cache bridge
    core.py                    Acquisition and status detection
    filters.py                 .holo filter list parsing
    options.py                 Scan options and defaults
  ui/
    scan.py                     Scan bar, filter upload, and scan messages
    dashboard.py                Index, filters, and exports
    detail.py                   Parameters, versions, and acquisition details
    media.py                    Image/video previews
    processing.py               Processing tab
    theme.py                    Streamlit styles
```

Other useful folders:

- `.streamlit/config.toml`: Streamlit dark theme
- `processing_defaults/`: short copies of upstream settings used by the app
- `software_pipeline_validation/`: local validation dataset
- `.doppler_cache/`: video-preview cache and temporary processing files
- `tests/`: unit tests for scanner, processing, and CLI wrappers

### Runtime validation

Use the shared validator instead of creating one-off scripts:

```powershell
.venv\Scripts\python.exe -m doppler_manager.tooling.validation --runtime-root <runtimes> --output build/validation/<run>
.venv\Scripts\python.exe -m doppler_manager.tooling.validation --runtime-root <frozen-app> --output build/validation/<run> --frozen --relocate
```

Reports and temporary app data are written only to the output directory.
`--relocate` makes a disposable copy; it never renames the supplied runtime.
These checks validate startup and CLI dispatch, not full acquisition processing.
