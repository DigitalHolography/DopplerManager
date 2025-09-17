import streamlit as st
import pandas as pd
from pathlib import Path

from src.FileFinder.FileFinderClass import FileFinder
from src.Database.DBClass import DB
from src.Utils.ParamsLoader import ConfigManager


@st.cache_resource
def initialize_database(db_path):
    """
    Connects to the database, instantiates the FileFinder,
    and ensures tables are created. This runs only once.
    """
    ff_instance = FileFinder(DB(db_path))
    ff_instance.CreateDB()
    return ff_instance.DB.SQLconnect, ff_instance


DB_FILE = ConfigManager.get("DB.DB_PATH", "renders.db")

# Use session state to run initialization notifications only once.
if "db_initialized" not in st.session_state:
    # The spinner shows a message while the code inside the "with" block runs.
    with st.spinner("Initializing database connection..."):
        initialize_database(DB_FILE)
    st.session_state.db_initialized = True

conn, ff = initialize_database(DB_FILE)
st.toast("Database initialized.", icon="✅")

@st.cache_data
def load_data(query):
    """
    Loads data from the database using the provided SQL query.
    Caches the result to avoid redundant database calls.
    """
    try:
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Error while loading data: {e}")
        return pd.DataFrame()


def launch_front():
    """
    Launches the frontend components of the Streamlit app.
    """
    # --- Page Configuration ---
    st.set_page_config(page_title="FetchDopplerDB", layout="wide")

    # --- Sidebar ---
    st.sidebar.title("Actions")
    scan_path = st.sidebar.text_input("Directory to scan", "Y:\\")

    if st.sidebar.button("Start directory scan"):
        if Path(scan_path).is_dir():
            st.sidebar.info("The scan may take a long time. Please wait.")
            with st.spinner(f"Scanning {scan_path}..."):
                ff.Findfiles(scan_path)
                st.sidebar.success("Scan completed successfully!")
                # Invalidate data caches to force reload
                st.cache_data.clear()
                st.rerun()  # Refresh the app to show new data
        else:
            st.sidebar.error("The specified path is not a valid directory.")

    st.sidebar.markdown("---")
    if st.sidebar.button("Clear database"):
        ff.ClearDB()
        st.sidebar.success("Database cleared.")
        st.rerun()

    # --- Main UI ---
    st.title("FetchDopplerDB")

    # Updated SQL query for the new database schema
    query = """
        SELECT
            hd.id,
            hd.path AS hd_folder,
            hd.tag AS measure_tag,
            hd.version AS hd_version,
            ef.path AS ef_folder,
            ef.version AS ef_version
        FROM
            hd_render AS hd
        LEFT JOIN
            ef_render AS ef ON hd.id = ef.hd_id
    """
    combined_df = load_data(query)

    if combined_df.empty:
        st.warning("The database is empty. Please start a scan.")
        return

    # --- HoloDoppler Filtering ---
    st.header("HoloDoppler Data")

    unique_tags = sorted(combined_df["measure_tag"].dropna().unique())
    selected_tags = st.multiselect("Filter by measure tag", options=unique_tags)

    unique_hd_versions = sorted(combined_df["hd_version"].dropna().unique())
    selected_hd_versions = st.multiselect(
        "Filter by HoloDoppler version", options=unique_hd_versions
    )

    filtered_df = combined_df.copy()

    # Apply HoloDoppler filters
    if selected_tags:
        filtered_df = filtered_df[filtered_df["measure_tag"].isin(selected_tags)]

    if selected_hd_versions:
        filtered_df = filtered_df[filtered_df["hd_version"].isin(selected_hd_versions)]

    total_hd_folders = combined_df["hd_folder"].nunique()
    shown_hd_folders = filtered_df["hd_folder"].nunique()
    hd_display_df = (
        filtered_df[["hd_folder", "measure_tag", "hd_version"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    st.markdown(
        f"**Showing {shown_hd_folders} of {total_hd_folders} HoloDoppler folders.**"
    )
    st.dataframe(hd_display_df, width='stretch')

    st.markdown("---")

    # --- EyeFlow Filtering ---
    st.header("EyeFlow Data")

    # The filtering pipeline continues: use the already-filtered dataframe (filtered_df)
    # as the basis for EyeFlow data.
    ef_base_df = filtered_df.dropna(subset=["ef_folder"])

    if not ef_base_df.empty:
        unique_ef_versions = sorted(ef_base_df["ef_version"].dropna().unique())
        selected_ef_versions = st.multiselect(
            "Filter by EyeFlow version", options=unique_ef_versions
        )
        ef_display_df = ef_base_df.copy()

        if selected_ef_versions:
            ef_display_df = ef_display_df[
                ef_display_df["ef_version"].isin(selected_ef_versions)
            ]

        total_ef_folders = ef_base_df["ef_folder"].nunique()
        shown_ef_folders = ef_display_df["ef_folder"].nunique()

        st.markdown(
            f"**Showing {shown_ef_folders} of {total_ef_folders} EyeFlow folders.**"
        )
        ef_display_columns = ["hd_folder", "ef_folder", "ef_version"]
        st.dataframe(
            ef_display_df[ef_display_columns].reset_index(drop=True),
            width='stretch',
        )
    else:
        st.info("No EyeFlow data matches the current HoloDoppler filters.")


if __name__ == "__main__":
    launch_front()