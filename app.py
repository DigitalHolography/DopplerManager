import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sqlite3

# Assurez-vous que le chemin d'importation est correct
import src.FileFinder.FileFinderClass as FileFinderClass

# --- Page Configuration ---
st.set_page_config(page_title="Render Explorer", layout="wide")

# --- Database Connection Management (Recommended way) ---
DB_FILE = "renders.db"

@st.cache_resource
def get_db_connection(db_path):
    """Crée et met en cache la connexion à la base de données."""
    return sqlite3.connect(db_path, check_same_thread=False)

conn = get_db_connection(DB_FILE)

# --- Initialisation de la classe avec la connexion partagée ---
# La classe reçoit maintenant l'objet de connexion
ff = FileFinderClass.FileFinder(conn)

# Créer les tables si elles n'existent pas (ne fait rien si elles existent déjà)
ff.CreateDB()

# --- Helper Functions ---
def load_data(query):
    """Exécute une SQL query and returns a pandas DataFrame."""
    try:
        # On utilise directement la connexion partagée
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement des données: {e}")
        return pd.DataFrame()

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
    st.warning("La base de données est vide. Veuillez lancer un scan.")
else:
    # --- Filtering ---
    st.header("Filtrage des données")
    
    unique_tags = main_df['measure_tag'].unique()
    selected_tags = st.multiselect("Filtrer par 'measure_tag'", options=unique_tags, default=list(unique_tags))

    unique_versions = main_df['version_text'].dropna().unique()
    selected_versions = st.multiselect("Filtrer par 'version_text'", options=unique_versions, default=list(unique_versions))
    
    if not selected_tags or not selected_versions:
        filtered_df = pd.DataFrame() # DataFrame vide si un filtre est vide
    else:
        filtered_df = main_df[main_df['measure_tag'].isin(selected_tags) & main_df['version_text'].isin(selected_versions)]

    st.header("Rendus trouvés")
    st.dataframe(filtered_df, width='stretch')

    st.markdown("---")

    # --- Detail View ---
    st.header("Détails d'un rendu")
    
    folder_options = filtered_df['hd_folder'].tolist()
    
    if not folder_options:
        st.info("Aucun rendu à afficher avec les filtres actuels.")
    else:
        selected_folder = st.selectbox("Sélectionner un dossier HD pour voir les détails", options=folder_options)

        if selected_folder:
            hd_id = main_df.loc[main_df['hd_folder'] == selected_folder, 'id'].iloc[0]

            st.subheader("Paramètres de rendu")
            params_df = load_data(f"SELECT rendering_parameters FROM hd_data WHERE id = {hd_id}")
            if not params_df.empty and params_df.iloc[0, 0]:
                try:
                    params_json = json.loads(params_df.iloc[0, 0])
                    st.json(params_json)
                except (json.JSONDecodeError, TypeError):
                    st.warning("Impossible d'afficher les paramètres de rendu (JSON invalide).")
                    st.text(params_df.iloc[0, 0])
            else:
                st.info("Aucun paramètre de rendu trouvé.")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Fichiers RAW (.raw, .h5)")
                raw_files_df = load_data(f"SELECT path, size_MB FROM raw_files WHERE hd_id = {hd_id}")
                st.dataframe(raw_files_df, width='stretch', hide_index=True)

            with col2:
                st.subheader("Dossiers Eyeflow (_EF_)")
                ef_data_df = load_data(f"SELECT ef_folder, version_text FROM ef_data WHERE hd_id = {hd_id}")
                st.dataframe(ef_data_df, width='stretch', hide_index=True)
