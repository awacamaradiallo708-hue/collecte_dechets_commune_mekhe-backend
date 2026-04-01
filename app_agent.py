import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, time
from sqlalchemy import create_engine, text
import os
from io import BytesIO

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="Agent Collecte - Mékhé",
    page_icon="🗑️",
    layout="wide"
)

# Style CSS pour l'accessibilité (Gros boutons et textes)
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%);
        padding: 1.5rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 1.5rem;
    }
    .stButton button {
        width: 100%; padding: 20px !important; font-size: 20px !important;
        font-weight: bold !important; border-radius: 15px !important; margin: 10px 0 !important;
    }
    .collecte-card {
        background: #e8f5e9; padding: 1.5rem; border-radius: 15px;
        margin-bottom: 1.2rem; border-left: 8px solid #4CAF50;
    }
    label { font-size: 20px !important; font-weight: bold !important; }
    input { font-size: 18px !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ TERMINAL AGENT - MÉKHÉ</h1><p>Saisie simplifiée avec suivi GPS</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BD ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ ERREUR : DATABASE_URL non configurée dans les Secrets.")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS DE DONNÉES ====================
def get_options(table):
    with engine.connect() as conn:
        res = conn.execute(text(f"SELECT id, nom FROM {table} WHERE actif = true ORDER BY nom")).fetchall()
        return {r[1]: r[0] for r in res}

def enregistrer_point_gps(tournee_id, type_p, desc, lat, lon, num_c):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description, collecte_numero)
                VALUES (:tid, :h, :type, :lat, :lon, :desc, :num)
            """), {"tid": tournee_id, "h": datetime.now(), "type": type_p, "lat": lat, "lon": lon, "desc": desc, "num": num_c})
        return True
    except Exception as e:
        st.error(f"Erreur GPS : {e}")
        return False

#Position par défaut (Mékhé)
def get_position():
    return {"lat": 15.1150, "lon": -16.6350}

# ==================== ÉTAT DE LA SESSION ====================
if 'points_gps' not in st.session_state: st.session_state.points_gps = []
if 'collecte1_ok' not in st.session_state: st.session_state.collecte1_ok = False
if 'collecte2_ok' not in st.session_state: st.session_state.collecte2_ok = False
if 'vol1' not in st.session_state: st.session_state.vol1 = 0.0
if 'vol2' not in st.session_state: st.session_state.vol2 = 0.0

# ==================== FORMULAIRE PRINCIPAL ====================
with st.sidebar:
    st.header("👤 Paramètres")
    agent = st.text_input("NOM DE L'AGENT", placeholder="Ex: Moussa")
    
    quartiers = get_options("quartiers")
    equipes = get_options("equipes")
    
    q_nom = st.selectbox("🏘️ QUARTIER", list(quartiers.keys()))
    e_nom = st.selectbox("👥 ÉQUIPE", list(equipes.keys()))
    dist = st.number_input("📏 DISTANCE (km)", min_value=0.0, value=25.0)

# -------------------- COLLECTE 1 --------------------
st.markdown('<div class="collecte-card">🚛 <strong>PREMIER TOUR (C1)</strong></div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    h_dep = st.text_input("⏰ Heure Départ Dépôt", value="07:00")
    h_deb1 = st.text_input("⏰ Heure Début Collecte 1", value="07:30")
with col2:
    h_fin1 = st.text_input("⏰ Heure Fin Collecte 1", value="09:30")
    v1 = st.number_input("📦 Volume C1 (m³)", min_value=0.0, step=0.5, key="v1_input")

if st.button("📍 Enregistrer Position C1"):
    pos = get_position()
    st.session_state.points_gps.append({"type": "collecte", "lat": pos["lat"], "lon": pos["lon"], "num": 1, "desc": "Point de collecte C1"})
    st.success("✅ Position enregistrée !")

if st.button("✅ VALIDER COLLECTE 1"):
    st.session_state.vol1 = v1
    st.session_state.collecte1_ok = True
    st.toast("Collecte 1 validée")

# -------------------- COLLECTE 2 --------------------
st.markdown('<div class="collecte-card" style="border-left-color: #FF9800;">🚛 <strong>DEUXIÈME TOUR (C2)</strong></div>', unsafe_allow_html=True)

col3, col4 = st.columns(2)
with col3:
    h_deb2 = st.text_input("⏰ Heure Début Collecte 2", value="11:00")
    h_fin2 = st.text_input("⏰ Heure Fin Collecte 2", value="13:00")
with col4:
    h_ret = st.text_input("⏰ Heure Retour Dépôt", value="15:00")
    v2 = st.number_input("📦 Volume C2 (m³)", min_value=0.0, step=0.5, key="v2_input")

if st.button("📍 Enregistrer Position C2"):
    pos = get_position()
    st.session_state.points_gps.append({"type": "collecte", "lat": pos["lat"], "lon": pos["lon"], "num": 2, "desc": "Point de collecte C2"})
    st.success("✅ Position enregistrée !")

# -------------------- ENREGISTREMENT FINAL --------------------
st.divider()

if st.button("💾 ENREGISTRER LA TOURNÉE COMPLÈTE", type="primary"):
    if not agent:
        st.error("⚠️ Veuillez saisir le nom de l'agent.")
    else:
        try:
            with engine.begin() as conn:
                # 1. Insertion Tournée
                res = conn.execute(text("""
                    INSERT INTO tournees (
                        date_tournee, quartier_id, equipe_id, agent_nom, 
                        volume_collecte1, volume_collecte2, volume_m3,
                        heure_depot_depart, heure_retour_depot, distance_parcourue_km, statut
                    ) VALUES (
                        :d, :qid, :eid, :agent, :v1, :v2, :vtot, :hdep, :hret, :dist, 'termine'
                    ) RETURNING id
                """), {
                    "d": date.today(), "qid": quartiers[q_nom], "eid": equipes[e_nom],
                    "agent": agent, "v1": st.session_state.vol1, "v2": v2,
                    "vtot": st.session_state.vol1 + v2, "hdep": h_dep, "hret": h_ret, "dist": dist
                })
                new_id = res.fetchone()[0]

                # 2. Insertion Points GPS
                for p in st.session_state.points_gps:
                    conn.execute(text("""
                        INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description, collecte_numero)
                        VALUES (:tid, :h, :type, :lat, :lon, :desc, :num)
                    """), {"tid": new_id, "h": datetime.now(), "type": p["type"], "lat": p["lat"], "lon": p["lon"], "desc": p["desc"], "num": p["num"]})
            
            st.balloons()
            st.success(f"✅ Tournée n°{new_id} enregistrée avec succès !")
            # Reset
            st.session_state.points_gps = []
            st.session_state.collecte1_ok = False
        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement : {e}")

# Affichage du trajet actuel
if st.session_state.points_gps:
    st.subheader("🗺️ Aperçu du trajet")
    df_map = pd.DataFrame(st.session_state.points_gps)
    st.map(df_map)
