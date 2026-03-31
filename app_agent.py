import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, time
from sqlalchemy import create_engine, text
import os
from io import BytesIO
from streamlit_js_eval import get_geolocation  # Extension pour le GPS réel

st.set_page_config(
    page_title="Agent Collecte - Mékhé",
    page_icon="🗑️",
    layout="wide"
)

# ==================== STYLE CSS ====================
st.markdown("""
    <style>
    .main-header { background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%); padding: 1.5rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 1.5rem; }
    .main-header h1 { font-size: 32px !important; }
    .stButton button { width: 100%; padding: 18px !important; font-size: 20px !important; font-weight: bold !important; border-radius: 15px !important; margin: 8px 0 !important; }
    .collecte-card { background: #e8f5e9; padding: 1.2rem; border-radius: 15px; margin-bottom: 1.2rem; border-left: 5px solid #4CAF50; }
    .collecte2-card { background: #fff8e7; padding: 1.2rem; border-radius: 15px; margin-bottom: 1.2rem; border-left: 5px solid #FF9800; }
    h4 { font-size: 24px !important; }
    label { font-size: 18px !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ AGENT DE COLLECTE - MÉKHÉ</h1><p>Suivi GPS en temps réel | Rapport Automatique</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BDD ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ ERREUR : Connexion Base de données manquante.")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTION GPS RÉEL ====================
def capturer_position():
    """Tente de récupérer les coordonnées GPS de l'appareil"""
    loc = get_geolocation()
    if loc and 'coords' in loc:
        return {
            "lat": loc['coords']['latitude'],
            "lon": loc['coords']['longitude']
        }
    return None

def enregistrer_etape(type_point, desc, collecte_num):
    """Fonction unique pour capturer le GPS et mettre en session"""
    pos = capturer_position()
    if pos:
        point = {
            "type": type_point,
            "lat": pos["lat"],
            "lon": pos["lon"],
            "collecte": collecte_num,
            "description": desc,
            "heure": datetime.now().strftime("%H:%M:%S")
        }
        st.session_state.points_gps.append(point)
        st.success(f"✅ Point capturé : {pos['lat']:.5f}, {pos['lon']:.5f}")
        return True
    else:
        st.error("❌ GPS introuvable. Activez la localisation et autorisez l'application.")
        return False

# ==================== FONCTIONS BDD ====================
def get_data(table):
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT id, nom FROM {table} WHERE actif = true ORDER BY nom")).fetchall()
        return [(r[0], r[1]) for r in result]

# ==================== INITIALISATION SESSION ====================
for key in ['points_gps', 'volume1', 'volume2', 'c1_valide', 'c2_valide', 'agent_nom']:
    if key not in st.session_state:
        if 'volume' in key: st.session_state[key] = 0.0
        elif 'valide' in key: st.session_state[key] = False
        elif 'points' in key: st.session_state[key] = []
        else: st.session_state[key] = ""

# ==================== INTERFACE ====================
with st.sidebar:
    st.header("👤 AGENT")
    st.session_state.agent_nom = st.text_input("VOTRE NOM", value=st.session_state.agent_nom)
    st.markdown("---")
    st.write(f"📍 Points capturés : {len(st.session_state.points_gps)}")

col1, col2 = st.columns(2)
with col1:
    date_t = st.date_input("📅 DATE", value=date.today())
    quartiers = get_data("quartiers")
    quartier_choisi = st.selectbox("🏘️ QUARTIER", [q[1] for q in quartiers])
with col2:
    dist_km = st.number_input("📏 KM COMPTEUR", min_value=0.0)
    equipes = get_data("equipes")
    equipe_choisie = st.selectbox("👥 ÉQUIPE", [e[1] for e in équipes])

# -------------------- COLLECTE 1 --------------------
st.markdown('<div class="collecte-card">🚛 COLLECTE N°1</div>', unsafe_allow_html=True)
if not st.session_state.c1_valide:
    c1_1, c1_2 = st.columns(2)
    with c1_1:
        if st.button("🏭 DÉPART DÉPÔT"): enregistrer_etape("depart_depot", "Départ Mékhé", 1)
        if st.button("🗑️ DÉBUT RAMASSAGE"): enregistrer_etape("debut_collecte", "Début C1", 1)
    with c1_2:
        if st.button("🏁 FIN RAMASSAGE"): enregistrer_etape("fin_collecte", "Fin C1", 1)
        if st.button("🏭 ARRIVÉE DÉCHARGE"): enregistrer_etape("arrivee_decharge", "Arrivée décharge 1", 1)
    
    vol1 = st.number_input("📦 VOLUME C1 (m³)", min_value=0.0, key="v1")
    if st.button("✅ VALIDER C1"):
        if vol1 > 0:
            st.session_state.volume1 = vol1
            st.session_state.c1_valide = True
            st.rerun()
else:
    st.success(f"✅ Collecte 1 terminée ({st.session_state.volume1} m³)")

# -------------------- COLLECTE 2 --------------------
if st.session_state.c1_valide:
    st.markdown('<div class="collecte2-card">🚛 COLLECTE N°2</div>', unsafe_allow_html=True)
    if not st.session_state.c2_valide:
        c2_1, c2_2 = st.columns(2)
        with c2_1:
            if st.button("🗑️ DÉBUT C2"): enregistrer_etape("debut_collecte", "Début C2", 2)
        with c2_2:
            if st.button("🏁 FIN C2"): enregistrer_etape("fin_collecte", "Fin C2", 2)
            if st.button("🏭 RETOUR DÉPÔT"): enregistrer_etape("retour_depot", "Fin de journée", 2)
        
        vol2 = st.number_input("📦 VOLUME C2 (m³)", min_value=0.0, key="v2")
        if st.button("💾 CLÔTURER LA TOURNÉE"):
            st.session_state.volume2 = vol2
            st.session_state.c2_valide = True
            # Logique d'insertion SQL ici (identique à votre code précédent)
            st.balloons()
            st.rerun()

# ==================== CARTE ET TRAJET ====================
if st.session_state.points_gps:
    st.markdown("### 🗺️ ITINÉRAIRE RÉEL")
    df = pd.DataFrame(st.session_state.points_gps)
    
    fig = px.scatter_mapbox(df, lat="lat", lon="lon", color="collecte", 
                            hover_name="description", zoom=13, height=500)
    
    if len(df) > 1:
        fig.add_trace(go.Scattermapbox(lat=df["lat"], lon=df["lon"], mode='lines', name='Trajet'))
    
    fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

# ==================== EXPORT ====================
if st.session_state.c2_valide:
    st.download_button("📥 Télécharger Rapport CSV", 
                       data=pd.DataFrame(st.session_state.points_gps).to_csv(), 
                       file_name=f"collecte_mekhe_{date_t}.csv")
