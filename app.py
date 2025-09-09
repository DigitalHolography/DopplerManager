import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

import src.FileFinder.FileFinderClass as FileFinderClass
from src.Database.DBClass import DB
from src.Utils.ParamsLoader import ConfigManager

@st.cache_resource
def initialize_database(db_path):
    """
    Connects to the database, instantiates the FileFinder, 
    and ensures tables are created. This runs only once.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    ff_instance = FileFinderClass.FileFinder(DB(SQLconnect=conn))
    ff_instance.CreateDB()
    return conn, ff_instance

DB_FILE = ConfigManager.get("DB.DB_PATH", "renders.db")

# Use session state to run initialization notifications only once.
if 'db_initialized' not in st.session_state:
    # The spinner shows a message while the code inside the "with" block runs.
    with st.spinner("Initializing database connection..."):
        initialize_database(DB_FILE)
    st.toast("Database ready!", icon="✅")
    st.session_state.db_initialized = True

conn, ff = initialize_database(DB_FILE)

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
    st.set_page_config(page_title="Render Explorer", layout="wide")

    # --- Sidebar ---
    st.sidebar.title("Actions")
    scan_path = st.sidebar.text_input("Directory to scan", "Y:\\")

    if st.sidebar.button("Start directory scan"):
        if Path(scan_path).is_dir():
            st.sidebar.info("The scan may take a long time. Please wait.")
            with st.spinner(f"Scanning {scan_path}..."):
                try:
                    ff.Findfiles(scan_path)
                    st.sidebar.success("Scan completed successfully!")
                    # Invalidate data caches to force reload
                    st.cache_data.clear()
                    st.rerun() # Refresh the app to show new data
                except Exception as e:
                    st.sidebar.error(f"An error occurred: {e}")
        else:
            st.sidebar.error("The specified path is not a valid directory.")

    st.sidebar.markdown("---")
    if st.sidebar.button("Clear database"):
        ff.ClearDB() # Single, clean method call
        st.sidebar.success("Database cleared.")
        st.rerun()

    # --- Main UI ---
    st.title("EyeFlowDB")

    main_df = load_data("SELECT id, hd_folder, measure_tag, version_text FROM hd_data")

    if main_df.empty:
        st.warning("The database is empty. Please start a scan.")
    else:
        # --- Filtering ---
        st.header("HoloDoppler Data")

        unique_tags = main_df['measure_tag'].unique()
        selected_tags = st.multiselect("Filter by measure tag", options=unique_tags, default=list(unique_tags))

        unique_versions = main_df['version_text'].dropna().unique()
        selected_versions = st.multiselect("Filter by HoloDoppler version", options=unique_versions, default=list(unique_versions))
        
        # Start with a copy of the full dataframe
        filtered_df = main_df.copy()

        # Apply filters only if selections are made in the multiselect widgets
        if selected_tags:
            filtered_df = filtered_df[filtered_df['measure_tag'].isin(selected_tags)]
        if selected_versions:
            filtered_df = filtered_df[filtered_df['version_text'].isin(selected_versions)]

        st.header("Found HoloDoppler folders")
        st.markdown(f"**Showing {len(filtered_df)} of {len(main_df)} folders.**")

        if filtered_df.empty:
            st.info("No HoloDoppler data matches the current filters.")
        else:
            st.dataframe(filtered_df.drop(columns=['id']), width='stretch')

        st.markdown("---")

        if not filtered_df.empty:
            st.header("EyeFlow Data")

            # Get the IDs of the filtered HD folders
            filtered_hd_ids = tuple(filtered_df['id'].tolist())

            # Load the corresponding EyeFlow data
            ef_df = load_data(f"SELECT hd_id, ef_folder, version_text FROM ef_data WHERE hd_id IN {filtered_hd_ids}")

            if not ef_df.empty:
                # --- EyeFlow Version Filtering ---
                unique_ef_versions = ef_df['version_text'].dropna().unique()
                selected_ef_versions = st.multiselect("Filter by EyeFlow version", options=unique_ef_versions, default=list(unique_ef_versions))

                filtered_ef_df = ef_df.copy()
                # Apply EF version filter only if a selection is made
                if selected_ef_versions:
                    filtered_ef_df = filtered_ef_df[filtered_ef_df['version_text'].isin(selected_ef_versions)]

                st.header("Found EyeFlow Folders")
                
                # Only merge and display if the filtered EF dataframe is not empty
                if not filtered_ef_df.empty:
                    # Join with hd_data to show the corresponding hd_folder
                    merged_ef_df = pd.merge(filtered_ef_df, main_df[['id', 'hd_folder']], left_on='hd_id', right_on='id', how='left')

                    # Hide the 'id' and 'hd_id' columns from the displayed dataframe
                    st.dataframe(merged_ef_df.drop(columns=['id', 'hd_id']), width='stretch')
                else:
                    st.info("No EyeFlow data matches the current filters.")

            else:
                st.info("No corresponding EyeFlow data found for the selected HoloDoppler filters.")

launch_front()