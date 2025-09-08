import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sqlite3

import src.FileFinder.FileFinderClass as FileFinderClass

# --- Page Configuration ---
st.set_page_config(page_title="Render Explorer", layout="wide")

# --- Database Connection Management (Recommended way) ---
DB_FILE = "renders.db"

@st.cache_resource
def get_db_connection(db_path):
    return sqlite3.connect(db_path, check_same_thread=False)

conn = get_db_connection(DB_FILE)

ff = FileFinderClass.FileFinder(conn)

ff.CreateDB()

# --- Helper Functions ---
def load_data(query):
    try:
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement des données: {e}")
        return pd.DataFrame()

# --- Sidebar ---
st.sidebar.title("Actions")
scan_path = st.sidebar.text_input("Folder to scan", "Y:\\")

if st.sidebar.button("Start directory scan"):
    if Path(scan_path).is_dir():
        st.sidebar.info("The scan may take a long time. Please wait.")
        with st.spinner(f"Scanning in progress in {scan_path}..."):
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
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS raw_files")
    cursor.execute("DROP TABLE IF EXISTS ef_data")
    cursor.execute("DROP TABLE IF EXISTS hd_data")
    conn.commit()
    ff.CreateDB()
    st.sidebar.success("Base de données effacée.")
    st.rerun()

# --- Main UI ---
st.title("EyeFlowDB")

main_df = load_data("SELECT id, hd_folder, measure_tag, version_text FROM hd_data")

if main_df.empty:
    st.warning("The database is empty. Please start a scan.")
else:
    # --- Filtering ---
    st.header("Data Filtering")

    unique_tags = main_df['measure_tag'].unique()
    selected_tags = st.multiselect("Filter by 'measure_tag'", options=unique_tags, default=list(unique_tags))

    unique_versions = main_df['version_text'].dropna().unique()
    selected_versions = st.multiselect("Filter by 'version_text'", options=unique_versions, default=list(unique_versions))
    
    if not selected_tags or not selected_versions:
        filtered_df = pd.DataFrame() # DataFrame empty if a filter is empty
    else:
        filtered_df = main_df[main_df['measure_tag'].isin(selected_tags) & main_df['version_text'].isin(selected_versions)]

    st.header("Found Renders")
    st.dataframe(filtered_df, width='stretch')

    st.markdown("---")

    # --- Detail View ---
    st.header("Render Details")

    folder_options = filtered_df['hd_folder'].tolist()
    
    if not folder_options:
        st.info("No render found with the current filters.")
    else:
        selected_folder = st.selectbox("Select an HD folder to view details", options=folder_options)

        if selected_folder:
            hd_id = main_df.loc[main_df['hd_folder'] == selected_folder, 'id'].iloc[0]

            st.subheader("Render Parameters")
            params_df = load_data(f"SELECT rendering_parameters FROM hd_data WHERE id = {hd_id}")
            if not params_df.empty and params_df.iloc[0, 0]:
                try:
                    params_json = json.loads(params_df.iloc[0, 0])
                    st.json(params_json)
                except (json.JSONDecodeError, TypeError):
                    st.warning("Impossible to display render parameters (invalid JSON).")
                    st.text(params_df.iloc[0, 0])
            else:
                st.info("No render parameters found.")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("RAW Files (.raw, .h5)")
                raw_files_df = load_data(f"SELECT path, size_MB FROM raw_files WHERE hd_id = {hd_id}")
                st.dataframe(raw_files_df, width='stretch', hide_index=True)

            with col2:
                st.subheader("Eyeflow Folders (_EF_)")
                ef_data_df = load_data(f"SELECT ef_folder, version_text FROM ef_data WHERE hd_id = {hd_id}")
                st.dataframe(ef_data_df, width='stretch', hide_index=True)
