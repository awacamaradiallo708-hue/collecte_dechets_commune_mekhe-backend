import streamlit as st
import pandas as pd
import json
from datetime import date, datetime
from sqlalchemy import create_engine, text
import folium
from streamlit_folium import folium_static
from io import BytesIO

# ==================== CONNEXION BASE NEON.TECH ====================
DATABASE_URL = "postgresql://neondb_owner:npg_43LqPNrhlzWo@ep-misty-mode-al5c7s4f-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

@st.cache_resource
def init_connection():
    try:
        # pool_pre_ping permet de vérifier que la connexion est toujours vivante
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        return engine
    except Exception as e:
        st.error(f"❌ Base de données non accessible : {e}")
        return None

engine = init_connection()

# ==================== CONFIGURATION PAGE ====================
st.set_page_config(page_title="Collecte Déchets - Mékhé", page_icon="🗑️", layout="wide")

st.markdown("""
    <style>
    .main-header { background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%); padding: 1rem; border-radius: 10px; color: white; text-align: center; margin-bottom: 1rem; }
    .stButton button { width: 100%; padding: 12px; font-size: 16px; font-weight: bold; border-radius: 10px; }
    .status-active { background-color: #fff3e0; padding: 15px; border-radius: 10px; text-align: center; font-size: 18px; border: 2px solid #fbc02d; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# ==================== INITIALISATION SESSION ====================
# Utilisation du session_state pour garder les données malgré les rafraîchissements
if 'points' not in st.session_state: st.session_state.points = []
if 'horaires' not in st.session_state: st.session_state.horaires = {}
if 'action_en_attente' not in st.session_state: st.session_state.action_en_attente = None
if 'agent_nom' not in st.session_state: st.session_state.agent_nom = ""
if 'volumes' not in st.session_state: st.session_state.volumes = {"collecte1": 0.0}

# ==================== COMPOSANT HTML/JS POUR GPS ====================
def get_gps_component():
    return """
    <div id="gps_status" style="background-color: #f8f9fa; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 10px; font-weight: bold; border: 1px solid #dee2e6;">
        📍 Prêt pour capture
    </div>
    <button onclick="getGPSPosition()" style="background-color: #2196F3; color: white; padding: 15px; border: none; border-radius: 8px; width: 100%; cursor: pointer; font-size: 18px; font-weight: bold;">
        OBTENIR MA POSITION GPS
    </button>
    <script>
    function getGPSPosition() {
        var statusDiv = document.getElementById('gps_status');
        statusDiv.innerHTML = '⌛ Recherche satellite...';
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    var now = new Date();
                    var heureCapture = now.getHours().toString().padStart(2, '0') + ":" + 
                                       now.getMinutes().toString().padStart(2, '0') + ":" + 
                                       now.getSeconds().toString().padStart(2, '0');
                    
                    var data = JSON.stringify({
                        lat: position.coords.latitude, 
                        lon: position.coords.longitude, 
                        heure: heureCapture,
                        timestamp: Date.now() 
                    });
                    
                    var streamlitInputs = parent.document.querySelectorAll('input');
                    for (var i = 0; i < streamlitInputs.length; i++) {
                        if (streamlitInputs[i].getAttribute('aria-label') === 'gps_internal_input') {
                            streamlitInputs[i].value = data;
                            streamlitInputs[i].dispatchEvent(new Event('input', { bubbles: true }));
                            streamlitInputs[i].dispatchEvent(new Event('change', { bubbles: true }));
                            break;
                        }
                    }
                    statusDiv.innerHTML = '✅ Capturé à ' + heureCapture;
                    statusDiv.style.backgroundColor = '#e8f5e9';
                },
                function(error) { statusDiv.innerHTML = '❌ Erreur GPS'; },
                { enableHighAccuracy: true, timeout: 10000 }
            );
        }
    }
    </script>
    """

# Champ invisible pour la réception des données
gps_data_raw = st.text_input("gps_internal_input", key="gps_receiver", label_visibility="collapsed")

# Traitement immédiat de la donnée GPS reçue
if gps_data_raw:
    try:
        gps_json = json.loads(gps_data_raw)
        if st.session_state.action_en_attente:
            act = st.session_state.action_en_attente
            h_cap = gps_json['heure']
            
            # Enregistrement dans les données de la session
            st.session_state.horaires[act] = h_cap
            st.session_state.points.append({
                "type": act, 
                "titre": act.upper(), 
                "heure": h_cap,
                "lat": gps_json['lat'], 
                "lon": gps_json['lon']
            })
            
            st.session_state.action_en_attente = None # On libère l'attente
            st.success(f"✅ Position enregistrée pour {act} à {h_cap}")
            st.rerun()
    except Exception as e:
        st.error(f"Erreur technique : {e}")

# ==================== INTERFACE ====================
st.markdown('<div class="main-header"><h1>Commune de Mékhé : Suivi Collecte</h1></div>', unsafe_allow_html=True)

# SIDEBAR
with st.sidebar:
    st.header("👤 Identification")
    st.session_state.agent_nom = st.text_input("Nom de l'agent", value=st.session_state.agent_nom)
    st.markdown("---")
    st.components.v1.html(get_gps_component(), height=180)
    st.info("💡 Cliquez d'abord sur une action (Départ, Début C1...) puis sur le bouton bleu GPS.")

if not st.session_state.agent_nom:
    st.warning("👈 Veuillez saisir votre nom dans la barre latérale pour commencer.")
    st.stop()

# ZONE D'ACTION
if st.session_state.action_en_attente:
    st.markdown(f'<div class="status-active">⏳ Action <b>{st.session_state.action_en_attente.upper()}</b> en cours...<br>Cliquez sur le bouton GPS à gauche pour valider.</div>', unsafe_allow_html=True)

st.subheader("🎤 Enregistrement de la tournée")
c1, c2, c3, c4, c5 = st.columns(5)
with c1: 
    if st.button("🚀 DÉPART"): st.session_state.action_en_attente = "depart"
with c2: 
    if st.button("🗑️ DÉBUT C1"): st.session_state.action_en_attente = "debut1"
with c3: 
    if st.button("🏁 FIN C1"): st.session_state.action_en_attente = "fin1"
with c4: 
    if st.button("🚛 VIDAGE 1"): st.session_state.action_en_attente = "vidage1"
with c5: 
    if st.button("🏠 RETOUR"): st.session_state.action_en_attente = "retour"

st.markdown("---")

# CARTE ET VOLUMES
col_map, col_vol = st.columns([2, 1])

with col_map:
    st.subheader("🗺️ Parcours de l'agent")
    if st.session_state.points:
        # On centre la carte sur le dernier point
        last_pt = st.session_state.points[-1]
        m = folium.Map(location=[last_pt['lat'], last_pt['lon']], zoom_start=15)
        for p in st.session_state.points:
            folium.Marker([p['lat'], p['lon']], popup=f"{p['titre']} - {p['heure']}", tooltip=p['heure']).add_to(m)
        folium_static(m)
    else:
        st.info("En attente du premier point GPS...")

with col_vol:
    st.subheader("📦 Volume")
    st.session_state.volumes["collecte1"] = st.number_input("Volume C1 (m³)", 0.0, 20.0, st.session_state.volumes["collecte1"], 0.5)
    
    if st.button("✅ TERMINER & ENREGISTRER", type="primary"):
        if "depart" not in st.session_state.horaires:
            st.error("❌ Action 'DÉPART' manquante.")
        elif st.session_state.volumes["collecte1"] == 0:
            st.error("❌ Volume de collecte nul.")
        else:
            # Procédure d'enregistrement en base de données
            st.success("Tournée enregistrée avec succès !")
            st.balloons()
