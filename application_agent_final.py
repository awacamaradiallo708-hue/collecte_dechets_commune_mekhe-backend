import streamlit as st
import pandas as pd
import json
from datetime import date, datetime
from sqlalchemy import create_engine, text
import folium
from streamlit_folium import folium_static

# ==================== CONNEXION BASE NEON.TECH ====================
DATABASE_URL = "postgresql://neondb_owner:npg_43LqPNrhlzWo@ep-misty-mode-al5c7s4f-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

@st.cache_resource
def init_connection():
    try:
        return create_engine(DATABASE_URL, pool_pre_ping=True)
    except Exception as e:
        st.error(f"❌ Erreur connexion base: {e}")
        return None

engine = init_connection()

# ==================== CONFIGURATION & STYLE ====================
st.set_page_config(page_title="Collecte Déchets - Mékhé", layout="wide")

st.markdown("""
    <style>
    .main-header { background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%); padding: 1rem; border-radius: 10px; color: white; text-align: center; margin-bottom: 1rem; }
    .stButton button { width: 100%; padding: 12px; font-weight: bold; border-radius: 10px; }
    .status-attente { background-color: #fff3e0; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid #fbc02d; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# ==================== INITIALISATION SESSION ====================
# On initialise TOUTES les variables pour qu'elles ne disparaissent pas
if 'points' not in st.session_state: st.session_state.points = []
if 'horaires' not in st.session_state: st.session_state.horaires = {}
if 'action_en_attente' not in st.session_state: st.session_state.action_en_attente = None
if 'agent_nom' not in st.session_state: st.session_state.agent_nom = ""
if 'quartier' not in st.session_state: st.session_state.quartier = "HLM"
if 'equipe' not in st.session_state: st.session_state.equipe = "Équipe A"
if 'tracteur' not in st.session_state: st.session_state.tracteur = "TAFE"
if 'num_parc' not in st.session_state: st.session_state.num_parc = ""
if 'volume1' not in st.session_state: st.session_state.volume1 = 0.0

# ==================== COMPOSANT GPS AMÉLIORÉ ====================
def get_gps_component():
    return """
    <div id="gps_info" style="background: #e3f2fd; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 8px; font-size: 14px; font-weight: bold;">
        📡 Prêt pour capture
    </div>
    <button onclick="captureGPS()" style="background: #2196F3; color: white; padding: 15px; border: none; border-radius: 8px; width: 100%; cursor: pointer; font-weight: bold;">
        📍 OBTENIR MA POSITION GPS
    </button>
    <script>
    function captureGPS() {
        const info = document.getElementById('gps_info');
        info.innerHTML = "⌛ Recherche satellite...";
        navigator.geolocation.getCurrentPosition(function(pos) {
            const now = new Date();
            const heure = now.getHours().toString().padStart(2,'0') + ":" + now.getMinutes().toString().padStart(2,'0') + ":" + now.getSeconds().toString().padStart(2,'0');
            const data = JSON.stringify({
                lat: pos.coords.latitude,
                lon: pos.coords.longitude,
                heure: heure,
                ts: Date.now() // Forcer le changement pour Streamlit
            });
            const inputs = parent.document.querySelectorAll('input');
            for (let input of inputs) {
                if (input.getAttribute('aria-label') === 'gps_data_receiver') {
                    input.value = data;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    break;
                }
            }
            info.innerHTML = "✅ Capturé à " + heure;
        }, (err) => { info.innerHTML = "❌ Erreur GPS"; }, {enableHighAccuracy: true});
    }
    </script>
    """

# Récepteur invisible
gps_input = st.text_input("gps_receiver", key="gps_receiver", label_visibility="collapsed", aria_label="gps_data_receiver")

# LOGIQUE D'ENREGISTREMENT (Se déclenche dès que gps_input change)
if gps_input:
    try:
        gps_data = json.loads(gps_input)
        if st.session_state.action_en_attente:
            tag = st.session_state.action_en_attente
            h_gps = gps_data['heure']
            
            # Sauvegarde ferme dans le session_state
            st.session_state.horaires[tag] = h_gps
            st.session_state.points.append({
                "type": tag,
                "titre": tag.upper(),
                "heure": h_gps,
                "lat": gps_data['lat'],
                "lon": gps_data['lon']
            })
            
            st.session_state.action_en_attente = None # On vide l'attente
            st.success(f"✅ Action {tag.upper()} enregistrée à {h_gps} !")
            st.rerun()
    except:
        pass

# ==================== INTERFACE UTILISATEUR ====================
st.markdown('<div class="main-header"><h1>Commune de Mékhé : Suivi Collecte</h1></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("📋 Configuration")
    st.session_state.agent_nom = st.text_input("👤 Nom Agent", st.session_state.agent_nom)
    st.session_state.quartier = st.selectbox("📍 Quartier", ["HLM", "NDIOP", "LEBOU EST", "NGAYE DIAGNE", "MAMBARA", "NGAYE DJITTE", "LEBOU OUEST"], index=0)
    st.session_state.equipe = st.selectbox("👥 Équipe", ["Équipe A", "Équipe B", "Équipe C"], index=0)
    st.session_state.tracteur = st.selectbox("🚜 Tracteur", ["TAFE", "New Holland", "Massey Ferguson"], index=0)
    st.session_state.num_parc = st.text_input("🔢 N° Parc", st.session_state.num_parc)
    st.markdown("---")
    st.components.v1.html(get_gps_component(), height=160)

if not st.session_state.agent_nom:
    st.warning("👈 Entrez votre nom dans le menu à gauche.")
    st.stop()

# Bannière d'instruction
if st.session_state.action_en_attente:
    st.markdown(f'<div class="status-attente">📢 Action <b>{st.session_state.action_en_attente.upper()}</b> sélectionnée.<br>Cliquez maintenant sur le bouton bleu GPS à gauche.</div>', unsafe_allow_html=True)

# BOUTONS
st.subheader("🎤 Enregistrement des étapes")
cols = st.columns(5)
btns = ["depart", "debut1", "fin1", "vidage1", "retour"]
labels = ["🚀 DÉPART", "🗑️ DÉBUT C1", "🏁 FIN C1", "🚛 VIDAGE 1", "🏠 RETOUR"]

for i, b in enumerate(btns):
    with cols[i]:
        if st.button(labels[i]):
            st.session_state.action_en_attente = b
            st.rerun()

st.markdown("---")

# CARTE ET RÉCAP
c_map, c_info = st.columns([2, 1])

with c_map:
    st.subheader("🗺️ Carte")
    if st.session_state.points:
        m = folium.Map(location=[st.session_state.points[-1]['lat'], st.session_state.points[-1]['lon']], zoom_start=15)
        for p in st.session_state.points:
            folium.Marker([p['lat'], p['lon']], popup=f"{p['titre']} ({p['heure']})").add_to(m)
        folium_static(m)
    else:
        st.info("Aucun point GPS capturé pour l'instant.")

with c_info:
    st.subheader("📦 Volume & Validation")
    st.session_state.volume1 = st.number_input("Volume C1 (m³)", 0.0, 20.0, st.session_state.volume1)
    
    if st.button("✅ TERMINER LA TOURNÉE", type="primary"):
        if "depart" not in st.session_state.horaires:
            st.error("❌ Erreur : Vous n'avez pas enregistré le DÉPART.")
        elif not st.session_state.points:
            st.error("❌ Erreur : Aucun point GPS n'a été capturé.")
        else:
            st.success("Tournée terminée ! Enregistrement en cours...")
            # Ici votre code SQL d'insertion...
            st.balloons()

# Récapitulatif visuel pour vérifier
with st.expander("📝 Historique de la session (Vérification)"):
    st.write(st.session_state.points)
