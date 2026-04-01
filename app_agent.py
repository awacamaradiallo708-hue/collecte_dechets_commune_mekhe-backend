# app_mobile_agent.py
import streamlit as st
import pandas as pd
import datetime
import psycopg2
from sqlalchemy import create_engine
import plotly.express as px
import requests

# =============================
# CONFIGURATION BASE DE DONNÉES
# =============================
DATABASE_URL = "postgresql://neondb_owner:npg_3TrNZSFg8Xfh@ep-flat-sun-aly40lkm.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)

# =============================
# FONCTION DE RÉCUPÉRATION GPS
# =============================
def get_location():
    try:
        # Pour mobile Streamlit, on peut récupérer la localisation via le navigateur
        location = st.experimental_get_query_params().get("location", ["0,0"])[0].split(",")
        lat = float(location[0])
        lon = float(location[1])
        return lat, lon
    except:
        return 0.0, 0.0

# =============================
# INTERFACE PRINCIPALE
# =============================
st.set_page_config(page_title="Agent Collecte Mékhé", layout="wide")
st.title("📍 Suivi et Collecte en Temps Réel - Commune de Mékhé")

# -----------------------------
# Sélection du quartier et équipe
# -----------------------------
quartiers_df = pd.read_sql("SELECT * FROM quartiers WHERE actif=true", engine)
equipes_df = pd.read_sql("SELECT * FROM equipes WHERE actif=true", engine)

quartier = st.selectbox("Sélectionnez le quartier", quartiers_df['nom'])
equipe = st.selectbox("Sélectionnez l'équipe", equipes_df['nom'])
agent_nom = st.text_input("Nom de l'agent")

# -----------------------------
# Saisie des horaires et volumes
# -----------------------------
st.subheader("🕒 Horaires")
heure_depot_depart = st.time_input("Heure départ dépôt", datetime.time(7,0))
heure_debut_collecte1 = st.time_input("Heure début collecte 1", datetime.time(7,30))
heure_fin_collecte1 = st.time_input("Heure fin collecte 1", datetime.time(8,30))
heure_depart_decharge1 = st.time_input("Heure départ décharge 1", datetime.time(8,45))
heure_arrivee_decharge1 = st.time_input("Heure arrivée décharge 1", datetime.time(9,0))
heure_sortie_decharge1 = st.time_input("Heure sortie décharge 1", datetime.time(9,15))
heure_debut_collecte2 = st.time_input("Heure début collecte 2", datetime.time(9,30))
heure_fin_collecte2 = st.time_input("Heure fin collecte 2", datetime.time(10,30))
heure_depart_decharge2 = st.time_input("Heure départ décharge 2", datetime.time(10,45))
heure_arrivee_decharge2 = st.time_input("Heure arrivée décharge 2", datetime.time(11,0))
heure_sortie_decharge2 = st.time_input("Heure sortie décharge 2", datetime.time(11,15))
heure_retour_depot = st.time_input("Heure retour dépôt", datetime.time(12,0))

st.subheader("📦 Volumes collectés (m3)")
volume_collecte1 = st.number_input("Volume collecte 1", min_value=0.0, step=0.1)
volume_collecte2 = st.number_input("Volume collecte 2", min_value=0.0, step=0.1)
volume_m3 = volume_collecte1 + volume_collecte2

observations = st.text_area("Observations / remarques")

# -----------------------------
# Bouton d'enregistrement
# -----------------------------
if st.button("💾 Enregistrer la tournée"):
    lat, lon = get_location()
    
    # Récupération IDs quartier et équipe
    quartier_id = quartiers_df.loc[quartiers_df['nom']==quartier, 'id'].values[0]
    equipe_id = equipes_df.loc[equipes_df['nom']==equipe, 'id'].values[0]
    
    # Insertion tournée
    query_insert = f"""
        INSERT INTO tournees (
            date_tournee, quartier_id, equipe_id, agent_nom,
            volume_collecte1, volume_collecte2, volume_m3,
            heure_depot_depart, heure_debut_collecte1, heure_fin_collecte1,
            heure_depart_decharge1, heure_arrivee_decharge1, heure_sortie_decharge1,
            heure_debut_collecte2, heure_fin_collecte2,
            heure_depart_decharge2, heure_arrivee_decharge2, heure_sortie_decharge2,
            heure_retour_depot, observations
        ) VALUES (
            CURRENT_DATE, {quartier_id}, {equipe_id}, '{agent_nom}',
            {volume_collecte1}, {volume_collecte2}, {volume_m3},
            '{heure_depot_depart}', '{heure_debut_collecte1}', '{heure_fin_collecte1}',
            '{heure_depart_decharge1}', '{heure_arrivee_decharge1}', '{heure_sortie_decharge1}',
            '{heure_debut_collecte2}', '{heure_fin_collecte2}',
            '{heure_depart_decharge2}', '{heure_arrivee_decharge2}', '{heure_sortie_decharge2}',
            '{heure_retour_depot}', '{observations}'
        ) RETURNING id;
    """
    with engine.begin() as conn:
        result = conn.execute(query_insert)
        tournee_id = result.fetchone()[0]
        st.success(f"Tournée enregistrée avec succès ! ID={tournee_id}")
        
        # Enregistrement point GPS initial
        conn.execute(f"""
            INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, collecte_numero)
            VALUES ({tournee_id}, NOW(), 'départ_dépôt', {lat}, {lon}, 0)
        """)

# -----------------------------
# Affichage carte interactive
# -----------------------------
st.subheader("🗺️ Carte des collectes")
points_df = pd.read_sql("SELECT * FROM points_arret ORDER BY created_at DESC LIMIT 500", engine)
if not points_df.empty:
    fig = px.scatter_mapbox(
        points_df,
        lat="latitude",
        lon="longitude",
        color="type_point",
        hover_name="type_point",
        hover_data=["heure","collecte_numero"],
        zoom=13,
        height=500
    )
    fig.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Pas encore de points GPS enregistrés.")
