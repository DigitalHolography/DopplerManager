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
| HD    | HoloDoppler | Raw `<id>.holo` acquisition and settings JSON | `<id>_HD/h5/<id>_HD_output.h5`, JSON files, version TXT, previews |
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
| `warning`     | The stage needs review: unexpected `.h5` name, missing source, or incomplete upstream dependency |
| `error`       | A blocking issue was detected, especially an empty `.h5` file                             |
| `unknown`     | The state could not be determined                                                         |

The global status is derived from stage statuses, warnings, and errors. A downstream output found while its upstream stage is not complete is marked as `warning`.

## User Interface

The Streamlit application provides three main tabs:

- `Acquisition Index`: filter by acquisition name, global status, missing HD, missing DV, or missing AE; view HD/DV/EF/AE statuses, warnings, errors, `.holo` presence, and acquisition folder presence.
- `Acquisition Details`: select a filtered acquisition, view status badges, and inspect `Parameters`, `Versions`, and `Media Preview` tabs.
- `Processing`: select acquisitions and stages to run or rerun, choose HoloDoppler settings, choose EyeFlow/AngioEye pipelines, follow real-time logs, and refresh the scan automatically after processing.

The scan bar accepts a typed or pasted path, a folder selected with `Browse`, and dropped paths when the browser provides a usable local path. Scan options control maximum depth, maximum inspected entries, indexed media per stage, version-file reading, and an optional `.txt` filter list. When a filter list is uploaded, each non-empty line is treated as a `.holo` filename, full path, or acquisition ID, and only matching acquisitions are scanned. By default, no filter is applied.

## Media Preview

Media files are grouped by acquisition and tool. Filters let users choose a subfolder, file type, and filename search query.

The scanner indexes previews found in `png/`, `avi/`, the stage-folder root, and, with a bounded walk, `output/`.

Supported formats:

- Images: `.png`, `.jpg`, `.jpeg`
- Browser-native videos: `.mp4`, `.mov`, `.m4v`
- `.avi` videos: automatic cached MP4 conversion through `imageio-ffmpeg`, with a fallback to system `ffmpeg` when available

Generated MP4 files for AVI previews are stored in `.doppler_cache/video_previews/`.

## Exports

The `Acquisition Index` tab exposes two exports:

- Filtered CSV: `doppler_pipeline_scan.csv`
- Full scan JSON: `doppler_pipeline_scan.json`

## Installation

The project targets Python 3.13 or newer.

Minimal installation for running the interface:

```bash
uv sync
```

Installation with processing tools:

```bash
uv sync --extra processing
```

The `processing` extra installs upstream dependencies from GitHub:

- `HoloDopplerPython`
- `DopplerView`
- `EyeFlowPython`
- `AngioEye`
- `onnxruntime`

## Run the Application

```bash
uv run streamlit run src/doppler_managing/app.py
```

On first launch, select a NAS or local root folder and click `Scan`.

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

Default commands:

```text
python -c "from holodoppler.cli import main; raise SystemExit(main())"
python -m dopplerview.cli
python -m doppler_managing._external_cli_runner eyeflow
python -m doppler_managing._external_cli_runner angioeye
```

Commands can be overridden with local executable paths:

- `DM_HOLODOPPLER_COMMAND`
- `DM_DOPPLERVIEW_COMMAND`
- `DM_EYEFLOW_COMMAND`
- `DM_ANGIOEYE_COMMAND`

HoloDoppler settings can be preconfigured with:

- `DM_HOLODOPPLER_SETTINGS`: path to a JSON file
- `DM_HOLODOPPLER_SETTINGS_DIR`: path to a folder containing JSON files

Settings discovery also checks `processing_defaults/holodoppler/`, `parameters/`, `HoloDopplerPython/parameters/`, and matching folders under the scanned root. When multiple files are available, the application prefers a JSON file containing `temporal_transformation`, which is required by the current HoloDoppler CLI.

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
src/doppler_managing/
  app.py                       Streamlit entry point
  models.py                    Scan data models
  scanner.py                   Acquisition and status detection
  processing.py                Job construction and execution
  _external_cli_runner.py       EyeFlow/AngioEye wrappers
  _eyeflow_runtime_limits.py    EyeFlow runtime compatibility and limits
  ui/
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
