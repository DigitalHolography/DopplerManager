import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

import src.FileFinder.FileFinderClass as FileFinderClass
from src.Database.DBClass import DB
from src.Utils.ParamsLoader import ConfigManager

# ┌───────────────────────────────────┐
# │           BACKEND SETUP           │
# └───────────────────────────────────┘

@st.cache_resource
def initialize_database(db_path):
    """
    Connects to the database, instantiates the FileFinder, 
    and ensures tables are created. This runs only once.
    """
    #st.toast("Initializing database connection...")
    # conn = sqlite3.connect(db_path, check_same_thread=False)
    ff_instance = FileFinderClass.FileFinder(DB(db_path))
    ff_instance.CreateDB()
    return ff_instance.DBClass.SQLconnect, ff_instance

DB_FILE = ConfigManager.get("DB.DB_PATH")
conn, ff = initialize_database(DB_FILE)

# ┌───────────────────────────────────┐
# │           FRONTEND SETUP          │
# └───────────────────────────────────┘

# --- Helper Functions ---
def load_data(query):
    try:
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Error while loading data: {e}")
        return pd.DataFrame()

def launch_front():
    # --- Page Configuration ---
    st.set_page_config(page_title="Render Explorer", layout="wide")

    # --- Sidebar ---
    st.sidebar.title("Actions")
    scan_path = st.sidebar.text_input("Répertoire à scanner", "Y:\\")

    if st.sidebar.button("Lancer le scan du répertoire"):
        if Path(scan_path).is_dir():
            st.sidebar.info("Le scan peut prendre beaucoup de temps. Veuillez patienter.")
            with st.spinner(f"Scan en cours dans {scan_path}..."):
                try:
                    ff.Findfiles(scan_path)
                    st.sidebar.success("Scan terminé avec succès!")
                    # Invalider les caches de données pour forcer le rechargement
                    st.cache_data.clear()
                    st.rerun() # Rafraîchir l'application pour afficher les nouvelles données
                except Exception as e:
                    st.sidebar.error(f"Une erreur est survenue: {e}")
        else:
            st.sidebar.error("Le chemin spécifié n'est pas un répertoire valide.")

    st.sidebar.markdown("---")
    if st.sidebar.button("Effacer la base de données"):
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

    # Charger les données principales
    main_df = load_data("SELECT id, hd_folder, measure_tag, version_text FROM hd_data")

    if main_df.empty:
        st.warning("The database is empty. Please start a scan.")
    else:
        # --- Filtering ---
        st.header("Data Filtering")

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

        st.header("Found Renders")
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