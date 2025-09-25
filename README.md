# DopplerManager

A Streamlit application to find, catalog, and browse HoloDoppler and EyeFlow render data.

## Prerequisites
-   **Windows 10/11**
-   **Python 3.13:** You can download Python from the official website: https://www.python.org/downloads/

---

## Setup Instructions

1.  **Download the latest release or clone the repository**

2.  **Create a virtual environment:**
    Open Command Prompt or PowerShell in the DopplerManager directory and run the following commands.
    ```bash
    python -m venv venv
    ```

3. **Activate the virtual environment:**
    ```bash
    venv\Scripts\activate
    ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
---

## Running the Application

1.  **Run the Streamlit app:**
    With your virtual environment activated, execute the following command in your terminal.
    ```bash
    streamlit run app.py
    ```

2.  **Access the application:**
    After running the command, the application should automatically open in a new tab in your default web browser. If it doesn't, you can access it at the local URL provided in the terminal (usually `http://localhost:8501` by default).

## Usage

1.  **Select a Directory:**
    Use the sidebar to select the root directory you wish to scan for render data. You can either paste the path into the text box or use the "Select Directory" button to open a folder selection dialog.

2.  **Update the Database:**
    Click the "Update database" button in the sidebar. The application will scan the selected directory and its subfolders for `.holo` files and their associated HoloDoppler (HD) and EyeFlow (EF) renders. The progress of the scan will be displayed in the sidebar.

3.  **Filter and Explore Data:**
    Once the database is populated, the main panel will display the data in three sections:
    *   **Holo Data:** Filter `.holo` files by creation date or by a specific "measure tag". You can also upload a `.txt` file containing a list of identifiers to filter the data.
    *   **HoloDoppler Data:** This section shows the HD renders associated with the filtered `.holo` files. You can further filter these by the HoloDoppler software version.
    *   **EyeFlow Data:** This section displays the EF renders associated with the filtered HD renders, with an option to filter by the EyeFlow version.

4.  **Export Data:**
    Each section has an expandable "Show/Export" area where you can view the filtered data in a table and export the file or folder paths to a `.txt` file.
