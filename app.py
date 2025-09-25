import streamlit as st
import pandas as pd
import multiprocessing

from src.FileFinder.FileFinderClass import FileFinder
from src.Database.DBClass import DB
from src.Utils.ParamsLoader import ConfigManager
from src.Utils.TeeHandler import Tee

from src.ui.sidebar import render_sidebar
from src.ui.holo_view import render_holo_section
from src.ui.hd_view import render_hd_section
from src.ui.ef_view import render_ef_section


@st.cache_resource
def initialize_database(db_path):
    """
    Connects to the database, instantiates the FileFinder,
    and ensures tables are created. This runs only once.
    """
    ff_instance = FileFinder(DB(db_path))
    ff_instance.CreateDB()
    return ff_instance


@st.cache_data
def load_data(query, _ff: FileFinder):
    """
    Loads data from the database using the provided SQL query.
    Caches the result to avoid redundant database calls.
    """
    # try:
    #     df = pd.read_sql_query(query, _conn)
    #     return df
    # except Exception as e:
    #     st.error(f"Error while loading data: {e}")
    #     return pd.DataFrame()

    return pd.read_sql_query(query, _ff.DB.SQLconnect)


def main():
    """
    Main function to run the Streamlit app.
    Acts as a conductor, calling rendering functions in order.
    """
    # --- Page Configuration ---
    st.set_page_config(page_title="DopplerManager", layout="wide")

    # --- Initialization ---
    DB_FILE = ConfigManager.get("DB.DB_PATH", "renders.db")

    if "db_initialized" not in st.session_state:
        with st.spinner("Initializing database connection..."):
            initialize_database(DB_FILE)
        st.session_state.db_initialized = True
        st.toast("Database initialized.")

    ff = initialize_database(DB_FILE)

    # --- UI Rendering ---
    render_sidebar(ff)

    st.title("DopplerManager")

    # --- Data Loading ---
    query = """
        SELECT
            h_data.path AS holo_file,
            h_data.tag AS measure_tag,
            h_data.created_at AS holo_created_at,
            hd.path AS hd_folder,
            hd.render_number as hd_render_number,
            hd.version AS hd_version,
            ef.path AS ef_folder,
            ef.render_number AS ef_render_number,
            ef.version AS ef_version
        FROM
            holo_data AS h_data
        LEFT JOIN
            hd_render AS hd ON h_data.id = hd.holo_id
        LEFT JOIN
            ef_render AS ef ON hd.id = ef.hd_id
    """
    combined_df = load_data(query, ff)

    if combined_df.empty:
        st.warning("The database is empty. Please start a scan.")
        return

    filtered_by_holo = render_holo_section(combined_df)
    st.markdown("---")
    filtered_by_hd = render_hd_section(filtered_by_holo)
    st.markdown("---")
    render_ef_section(filtered_by_hd)


if __name__ == "__main__":
    import os
    import sys
    import datetime
    from pathlib import Path

    if sys.version_info < (3, 13):
        print("You are using a Python version before 3.13!")
        print("This could result in failure to load")
        print(f"Current version {sys.version}")
        sys.exit(1)

    # For Windows compatibility in multiprocessing
    multiprocessing.freeze_support()

    LOG_FILE_PATH = Path(ConfigManager.get("LOG.LOG_PATH") or "logs")

    LOG_FILE_PATH = (
        LOG_FILE_PATH / f"log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    # Ensure the log directory exists
    log_dir = os.path.dirname(LOG_FILE_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    with Tee(LOG_FILE_PATH):
        main()
