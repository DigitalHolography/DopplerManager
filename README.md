![Python](https://img.shields.io/badge/python-3.13-blue?style=for-the-badge&logo=Python&logoColor=%23FFD43B)

# DopplerManager

A Streamlit application to find, catalog, and browse HoloDoppler and EyeFlow render data.

## Prerequisites

- **Windows 11** (Windows 10 is deprecated, use it at your own risk)
- **Python 3.13:** You can download Python from the official website: https://www.python.org/downloads/

---

## Setup Instructions

**Download the latest release or clone the repository**

### Auto setup

**Double click on `DopplerManager.exe` from inside the root folder of the project**

### Manual setup

1.  **Create a virtual environment:**
    Open Command Prompt or PowerShell in the DopplerManager directory and run the following commands.

    ```bash
    python -m venv venv
    ```

2.  **Activate the virtual environment:**

    ```bash
    venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Compilation

Prerequisites:

- **Rust**: Using `rustc`/`cargo` is recommanded, you can install with `rustup` them at https://rust-lang.org/tools/install/

The Launcher `DopplerManager.exe` is written in **Rust** and can be recompiled on demand using its files located inside `src/Launcher` folder.

You can run the following inside the project root folder:

- **Using Windows CMD**

```cmd
cargo build --release --manifest-path .\src\Launcher\Cargo.toml && copy .\src\Launcher\target\release\DopplerManager.exe DopplerManager.exe
```

- **Using Windows PowerShell**

```ps
cargo build --release --manifest-path src\Launcher\Cargo.toml; if ($?) { copy-item -Path src\Launcher\target\release\DopplerManager.exe -Destination DopplerManager.exe }
```

---

## Running the Application

1.  **Run the Streamlit app:**
    With your virtual environment activated, execute the following command in your terminal.

    ```bash
    streamlit run app.py
    ```

2.  **Access the application:**
    After running the command, the application should automatically open in a new tab in your default web browser. If it doesn't, you can access it at the local URL provided in the terminal (usually http://localhost:8501 by default).

## Usage

1.  **Select a Directory:**
    Use the sidebar to select the root directory you wish to scan for render data. You can either paste the path into the text box or use the "Select Directory" button to open a folder selection dialog.

2.  **Update the Database:**
    Click the "Update database" button in the sidebar. The application will scan the selected directory and its subfolders for `.holo` files and their associated HoloDoppler (HD) and EyeFlow (EF) renders. The progress of the scan will be displayed in the sidebar.

3.  **Filter and Explore Data:**
    Once the database is populated, the main panel will display the data in three sections:

    - **Holo Data:** Filter `.holo` files by creation date or by a specific "measure tag". You can also upload a `.txt` file containing a list of identifiers to filter the data.
    - **HoloDoppler Data:** This section shows the HD renders associated with the filtered `.holo` files. You can further filter these by the HoloDoppler software version.
    - **EyeFlow Data:** This section displays the EF renders associated with the filtered HD renders, with an option to filter by the EyeFlow version.

4.  **Export Data:**
    Each section has an expandable "Show/Export" area where you can view the filtered data in a table and export the file or folder paths to a `.txt` file.
