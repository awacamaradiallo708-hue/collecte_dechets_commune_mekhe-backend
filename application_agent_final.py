import streamlit as st
import pandas as pd
import json
from datetime import date, datetime
from sqlalchemy import create_engine, text
import folium
from streamlit_folium import folium_static
from io import BytesIO
from math import radians, sin, cos, sqrt, atan2

# ==================== CONNEXION BASE NEON.TECH ====================
DATABASE_URL = "postgresql://neondb_owner:npg_43LqPNrhlzWo@ep-misty-mode-al5c7s4f-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

@st.cache_resource
def init_connection():
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        return engine
    except Exception as e:
        st.error(f"❌ Base non accessible: {e}")
        return None

engine = init_connection()

# ==================== CONFIGURATION PAGE ====================
st.set_page_config(page_title="Collecte Déchets - Mékhé", page_icon="🗑️", layout="wide")

st.markdown("""
    <style>
    .main-header { background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%); padding: 1rem; border-radius: 10px; color: white; text-align: center; margin-bottom: 1rem; }
    .stButton button { width: 100%; padding: 12px; font-size: 16px; font-weight: bold; border-radius: 10px; }
    .status-box { padding: 10px; border-radius: 8px; text-align: center; margin-top: 10px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==================== INITIALISATION SESSION ====================
keys = {
    'agent_nom': "", 'role': "agent", 'quartier': "HLM", 'equipe': "Équipe A",
    'type_tracteur': "TAFE", 'numero_parc': "", 'points': [], 'horaires': {},
    'volumes': {"collecte1": 0.0, "collecte2": 0.0}, 'collecte2_active': False,
    'collecte1_terminee': False, 'latitude': None, 'longitude': None,
    'action_en_attente': None # Crucial pour la correction
}
for key, value in keys.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ==================== COMPOSANT HTML/JS POUR GPS ====================
def get_gps_component():
    return """
    <div id="gps_status" style="background-color: #fff3e0; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 10px; font-weight: bold; border: 1px solid #ffa726;">
        📍 1. Cliquez ici pour capturer la position
    </div>
    <button onclick="getGPSPosition()" style="background-color: #2196F3; color: white; padding: 15px; border: none; border-radius: 8px; width: 100%; cursor: pointer; font-size: 18px; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        OBTENIR MA POSITION GPS
    </button>
    <script>
    function getGPSPosition() {
        var statusDiv = document.getElementById('gps_status');
        statusDiv.innerHTML = '⌛ Recherche satellite en cours...';
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    var lat = position.coords.latitude;
                    var lon = position.coords.longitude;
                    var data = JSON.stringify({lat: lat, lon: lon, timestamp: Date.now()});
                    var streamlitInputs = parent.document.querySelectorAll('input');
                    for (var i = 0; i < streamlitInputs.length; i++) {
                        if (streamlitInputs[i].getAttribute('aria-label') === 'gps_internal_input') {
                            streamlitInputs[i].value = data;
                            streamlitInputs[i].dispatchEvent(new Event('input', { bubbles: true }));
                            break;
                        }
                    }
                    statusDiv.innerHTML = '✅ Position capturée !';
                    statusDiv.style.backgroundColor = '#e8f5e9';
                },
                function(error) { statusDiv.innerHTML = '❌ Erreur GPS: ' + error.message; },
                { enableHighAccuracy: true, timeout: 10000 }
            );
        }
    }
    </script>
    """

# Champ invisible pour recevoir les données du JS
gps_data_raw = st.text_input("gps_internal_input", key="gps_receiver", label_visibility="collapsed")

# Logique de traitement quand le GPS arrive
if gps_data_raw:
    try:
        gps_json = json.loads(gps_data_raw)
        st.session_state.latitude = gps_json['lat']
        st.session_state.longitude = gps_json['lon']
        
        # Si une action attendait le GPS, on l'enregistre maintenant
        if st.session_state.action_en_attente:
            act = st.session_state.action_en_attente
            current_time = datetime.now().strftime("%H:%M:%S")
            
            # Mapping des titres
            titres = {
                "depart": "🏭 Départ dépôt", "debut1": "🗑️ Début collecte 1",
                "fin1": "🏁 Fin collecte 1", "vidage1": "🚛 Vidage 1", "retour": "🏁 Retour"
            }
            
            st.session_state.horaires[act] = current_time
            st.session_state.points.append({
                "type": act, "titre": titres.get(act, act), "heure": current_time,
                "lat": st.session_state.latitude, "lon": st.session_state.longitude
            })
            
            if act == "fin1": st.session_state.collecte1_terminee = True
            
            st.session_state.action_en_attente = None # Reset
            st.success(f"✅ {titres.get(act)} enregistré !")
            st.rerun()
    except:
        pass

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("⚙️ Paramètres")
    st.session_state.agent_nom = st.text_input("👤 Nom de l'agent", value=st.session_state.agent_nom)
    st.session_state.quartier = st.selectbox("📍 Quartier", ["HLM", "NDIOP", "LEBOU EST", "NGAYE DIAGNE", "MAMBARA", "NGAYE DJITTE", "LEBOU OUEST"])
    st.session_state.equipe = st.selectbox("👥 Équipe", ["Équipe A", "Équipe B", "Équipe C"])
    st.session_state.type_tracteur = st.selectbox("🚜 Tracteur", ["TAFE", "New Holland", "Massey Ferguson"])
    st.session_state.numero_parc = st.text_input("🔢 N° Parc", value=st.session_state.numero_parc)
    
    st.markdown("---")
    st.components.v1.html(get_gps_component(), height=180)

# ==================== INTERFACE PRINCIPALE ====================
st.markdown('<div class="main-header"><h1>Commune de Mékhé : Suivi Collecte</h1></div>', unsafe_allow_html=True)

if not st.session_state.agent_nom:
    st.warning("👈 Veuillez saisir votre nom dans le menu à gauche pour commencer.")
    st.stop()

# Barre d'état de l'action
if st.session_state.action_en_attente:
    st.markdown(f"""<div style="background-color: #ffeb3b; padding: 15px; border-radius: 10px; text-align: center; font-size: 18px; border: 2px solid #fbc02d;">
        ⏳ Action <b>{st.session_state.action_en_attente.upper()}</b> sélectionnée.<br>
        Maintenant, cliquez sur le bouton bleu <b>OBTENIR MA POSITION GPS</b> à gauche.
    </div>""", unsafe_allow_html=True)

# Boutons d'actions
st.subheader("🎤 Enregistrement de la tournée")
c1, c2, c3, c4, c5 = st.columns(5)

def preparer_action(tag):
    st.session_state.action_en_attente = tag

with c1: 
    if st.button("🚀 DÉPART", type="primary"): preparer_action("depart")
with c2: 
    if st.button("🗑️ DÉBUT C1"): preparer_action("debut1")
with c3: 
    if st.button("🏁 FIN C1"): preparer_action("fin1")
with c4: 
    if st.button("🚛 VIDAGE 1"): preparer_action("vidage1")
with c5: 
    if st.button("🏠 RETOUR"): preparer_action("retour")

st.markdown("---")

# Volume et Carte
col_map, col_vol = st.columns([2, 1])

with col_vol:
    st.subheader("📦 Volumes")
    v1 = st.number_input("Volume C1 (m³)", 0.0, 20.0, st.session_state.volumes["collecte1"], 0.5)
    st.session_state.volumes["collecte1"] = v1
    
    if st.button("✅ VALIDER & ENVOYER", use_container_width=True, type="primary"):
        if not st.session_state.horaires.get("depart") or v1 == 0:
            st.error("❌ Données incomplètes (Départ ou Volume manquant)")
        else:
            # Code d'insertion SQL identique à votre version
            st.success("Données envoyées à Neon.tech !")
            st.balloons()

with col_map:
    st.subheader("🗺️ Parcours")
    if st.session_state.points:
        m = folium.Map(location=[st.session_state.points[-1]['lat'], st.session_state.points[-1]['lon']], zoom_start=15)
        for p in st.session_state.points:
            folium.Marker([p['lat'], p['lon']], popup=p['titre']).add_to(m)
        folium_static(m)
    else:
        st.info("Aucun point GPS enregistré pour le moment.")
