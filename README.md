# FetchDopplerDB
A Tool to find files

## Tools
This folder contains tools with unit features for easy access and portability

| Name              | Description           |
| ----------------- | --------------------- |
| DopplerBatchTool  | Helps to find and batch list data to be processed |

### DopplerBatchTool

The Tool can simply be build with this command inside the `DopplerBatchTool` folder:
```sh
pyinstaller DopplerBatchTool.spec
```

**It Requires PyInstaller (can be installed with pip)**

Full command here:
```sh
pyinstaller --clean --onefile --windowed --icon="DopplerBatchTool_logo.ico" --add-data "icon.ico;." -n "DopplerBatchTool" main.py
```

