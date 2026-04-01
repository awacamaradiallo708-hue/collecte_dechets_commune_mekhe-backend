import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import os

# ==================== CONFIGURATION ====================
st.set_page_config(page_title="Agent Collecte - Mékhé", page_icon="🚛")

# Connexion Base de Données
DATABASE_URL = st.secrets["DATABASE_URL"] if "DATABASE_URL" in st.secrets else os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Initialisation de la session
if 'tournee_id' not in st.session_state:
    st.session_state.tournee_id = None
if 'etape' not in st.session_state:
    st.session_state.etape = "depart"

def executer_query(query, params):
    with engine.begin() as conn:
        return conn.execute(text(query), params)

# ==================== INTERFACE AGENT ====================
st.title("📲 Terminal Agent - Mékhé")

# --- ÉTAPE 1 : DÉPART ---
if st.session_state.etape == "depart":
    st.subheader("🚀 Nouvelle Tournée")
    with st.form("form_depart"):
        agent = st.text_input("Nom de l'Agent")
        equipe = st.selectbox("Équipe", ["Équipe A", "Équipe B", "Équipe C"])
        quartier = st.selectbox("Quartier", ["Ngaye Diagne", "Ngaye Djité", "HLM", "Mbambara", "Lebou Est", "Lebou Ouest", "Ndiob"])
        
        if st.form_submit_button("Démarrer la tournée"):
            h_dep = datetime.now().strftime('%H:%M:%S')
            date_j = datetime.now().date()
            res = executer_query("""
                INSERT INTO tournees (agent_nom, equipe_nom, quartier_nom, date_tournee, heure_depart_depot, statut)
                VALUES (:agent, :equipe, :quartier, :date, :h_dep, 'en_cours')
                RETURNING id
            """, {"agent": agent, "equipe": equipe, "quartier": quartier, "date": date_j, "h_dep": h_dep})
            st.session_state.tournee_id = res.fetchone()[0]
            st.session_state.etape = "collecte"
            st.rerun()

# --- ÉTAPE 2 : COLLECTE (GPS + TEMPS) ---
elif st.session_state.etape == "collecte":
    st.info(f"Tournée n°{st.session_state.tournee_id} en cours...")
    
    col1, col2 = st.columns(2)
    lat = col1.number_input("Latitude", value=15.1100, format="%.6f")
    lon = col2.number_input("Longitude", value=-16.6200, format="%.6f")
    
    if st.button("📍 VALIDER POINT DE COLLECTE", use_container_width=True):
        h_passage = datetime.now().strftime('%H:%M:%S')
        executer_query("""
            INSERT INTO points_arret (tournee_id, latitude, longitude, type_point, heure_passage)
            VALUES (:t_id, :lat, :lon, 'collecte', :h_pass)
        """, {"t_id": st.session_state.tournee_id, "lat": lat, "lon": lon, "h_pass": h_passage})
        st.toast(f"Enregistré à {h_passage}")

    if st.button("🏁 Terminer la tournée", type="primary"):
        st.session_state.etape = "fin"
        st.rerun()

# --- ÉTAPE 3 : FIN ---
elif st.session_state.etape == "fin":
    st.subheader("📊 Clôture de la tournée")
    with st.form("form_fin"):
        vol = st.number_input("Volume total (m³)", min_value=0.0)
        dist = st.number_input("Distance (km)", min_value=0.0)
        if st.form_submit_button("Enregistrer et fermer"):
            h_arr = datetime.now().strftime('%H:%M:%S')
            executer_query("""
                UPDATE tournees SET volume_total_m3 = :v, distance_km = :d, 
                heure_arrivee_depot = :h, statut = 'termine' WHERE id = :id
            """, {"v": vol, "d": dist, "h": h_arr, "id": st.session_state.tournee_id})
            st.session_state.etape = "depart"
            st.session_state.tournee_id = None
            st.rerun()
