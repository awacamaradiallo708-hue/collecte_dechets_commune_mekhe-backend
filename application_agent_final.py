"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec GPS via composant HTML/JS personnalisé - CORRIGÉE v2.0
"""

import streamlit as st
import pandas as pd
import json
from datetime import date, datetime
from sqlalchemy import create_engine, text
import folium
from streamlit_folium import folium_static
from io import BytesIO
from math import radians, sin, cos, sqrt, atan2
import logging

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO)

# ==================== CONNEXION BASE NEON.TECH ====================
DATABASE_URL = "postgresql://neondb_owner:npg_43LqPNrhlzWo@ep-misty-mode-al5c7s4f-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

@st.cache_resource
def init_connection():
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.error(f"❌ Base non accessible: {e}")
        return None

engine = init_connection()

# ==================== CONFIGURATION PAGE ====================
st.set_page_config(
    page_title="Collecte Déchets - Mékhé",
    page_icon="🗑️",
    layout="wide"
)

# ==================== STYLE ====================
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
    }
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
        border-radius: 10px;
    }
    .gps-card {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
        border-left: 4px solid #2196F3;
    }
    .gps-button {
        background-color: #2196F3;
        color: white;
        padding: 10px;
        border: none;
        border-radius: 8px;
        width: 100%;
        cursor: pointer;
        font-size: 16px;
        font-weight: bold;
    }
    .step-indicator {
        background-color: #f5f5f5;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        border-left: 4px solid #4CAF50;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== INITIALISATION SESSION ====================
def init_session_state():
    """Initialiser tous les variables de session"""
    if 'agent_nom' not in st.session_state:
        st.session_state.agent_nom = ""
    if 'role' not in st.session_state:
        st.session_state.role = "agent"
    if 'quartier' not in st.session_state:
        st.session_state.quartier = "HLM"
    if 'equipe' not in st.session_state:
        st.session_state.equipe = "Équipe A"
    if 'type_tracteur' not in st.session_state:
        st.session_state.type_tracteur = "TAFE"
    if 'numero_parc' not in st.session_state:
        st.session_state.numero_parc = ""

    # Points et horaires
    if 'points' not in st.session_state:
        st.session_state.points = []
    if 'horaires' not in st.session_state:
        st.session_state.horaires = {}
    if 'volumes' not in st.session_state:
        st.session_state.volumes = {"collecte1": 0.0, "collecte2": 0.0}
    if 'collecte2_active' not in st.session_state:
        st.session_state.collecte2_active = False
    if 'collecte1_terminee' not in st.session_state:
        st.session_state.collecte1_terminee = False

    # Position GPS - IMPORTANT
    if 'latitude' not in st.session_state:
        st.session_state.latitude = None
    if 'longitude' not in st.session_state:
        st.session_state.longitude = None
    if 'gps_obtenu' not in st.session_state:
        st.session_state.gps_obtenu = False
    if 'gps_timestamp' not in st.session_state:
        st.session_state.gps_timestamp = None

# Initialiser la session
init_session_state()

# ==================== COMPOSANT HTML POUR GPS ====================
def get_gps_component():
    """Composant HTML/JavaScript optimisé pour obtenir la position GPS"""
    return """
    <div id="gps_container" style="padding: 0;">
        <div id="gps_status" style="background-color: #f0f0f0; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 10px; font-weight: bold;">
            ⚠️ Cliquez sur le bouton pour obtenir votre position
        </div>
        <button onclick="getGPSPosition()" style="background-color: #2196F3; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%; cursor: pointer; font-size: 16px; font-weight: bold; transition: background-color 0.3s;">
            📍 Obtenir ma position GPS
        </button>
        
        <input type="hidden" id="gps_data_input" />
    </div>
    
    <script>
    function getGPSPosition() {
        var statusDiv = document.getElementById('gps_status');
        var button = document.querySelector('button');
        
        statusDiv.innerHTML = '📍 Recherche GPS en cours...';
        statusDiv.style.backgroundColor = '#fff3e0';
        button.disabled = true;
        button.style.opacity = '0.6';
        
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    var lat = position.coords.latitude;
                    var lon = position.coords.longitude;
                    var accuracy = position.coords.accuracy;
                    
                    statusDiv.innerHTML = '✅ Position trouvée !<br>Lat: ' + lat.toFixed(6) + '<br>Lon: ' + lon.toFixed(6) + '<br>Précision: ±' + accuracy.toFixed(0) + 'm';
                    statusDiv.style.backgroundColor = '#e8f5e9';
                    button.style.opacity = '1';
                    button.disabled = false;
                    
                    var data = JSON.stringify({lat: lat, lon: lon, accuracy: accuracy, timestamp: new Date().getTime()});
                    
                    // Trouver et mettre à jour le champ Streamlit
                    try {
                        var inputs = parent.document.querySelectorAll('input[type="text"]');
                        for (var i = 0; i < inputs.length; i++) {
                            var input = inputs[i];
                            if (input && input.getAttribute && input.getAttribute('data-testid') && input.getAttribute('data-testid').includes('gps_receiver')) {
                                input.value = data;
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                                input.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    } catch(e) {
                        console.error('Erreur accès parent:', e);
                    }
                },
                function(error) {
                    var errorMsg = '';
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMsg = '❌ Permission refusée. Activez la localisation.';
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMsg = '❌ Position non disponible.';
                            break;
                        case error.TIMEOUT:
                            errorMsg = '❌ Délai dépassé. Réessayez.';
                            break;
                        default:
                            errorMsg = '❌ Erreur GPS inconnue';
                    }
                    statusDiv.innerHTML = errorMsg;
                    statusDiv.style.backgroundColor = '#ffebee';
                    button.style.opacity = '1';
                    button.disabled = false;
                },
                { 
                    enableHighAccuracy: true, 
                    timeout: 15000,
                    maximumAge: 0
                }
            );
        } else {
            statusDiv.innerHTML = '❌ GPS non supporté par ce navigateur';
            statusDiv.style.backgroundColor = '#ffebee';
            button.style.opacity = '1';
            button.disabled = false;
        }
    }
    </script>
    """

# ==================== TRAITEMENT GPS ====================
# Champ caché pour recevoir les données GPS
gps_receiver = st.text_input("", key="gps_receiver", label_visibility="collapsed")

if gps_receiver and not st.session_state.gps_obtenu:
    try:
        data = json.loads(gps_receiver)
        lat = data.get("lat")
        lon = data.get("lon")
        
        if lat is not None and lon is not None:
            st.session_state.latitude = lat
            st.session_state.longitude = lon
            st.session_state.gps_obtenu = True
            st.session_state.gps_timestamp = data.get("timestamp")
            st.rerun()  # Rerun pour rafraîchir immédiatement
    except Exception as e:
        st.error(f"Erreur parsing GPS: {e}")

# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("### 🗑️ Commune de Mékhé")
    st.markdown("---")
    
    mode = st.radio("🔐 Mode", ["🧑‍🌾 Agent de terrain", "📊 Responsable / Dashboard"])
    
    if mode == "🧑‍🌾 Agent de terrain":
        st.session_state.role = "agent"
        st.markdown("---")
        st.markdown("### 👤 Informations Agent")
        st.session_state.agent_nom = st.text_input("✍️ Votre nom", placeholder="Ex: Alioune Diop", value=st.session_state.agent_nom)
        
        st.markdown("---")
        st.markdown("### 📍 Informations tournée")
        st.session_state.quartier = st.selectbox("Quartier", 
            ["HLM", "NDIOP", "LEBOU EST", "NGAYE DIAGNE", "MAMBARA", "NGAYE DJITTE", "LEBOU OUEST"],
            index=0 if st.session_state.quartier == "HLM" else 1)
        
        st.session_state.equipe = st.selectbox("Équipe", 
            ["Équipe A", "Équipe B", "Équipe C", "Équipe D"],
            index=0 if st.session_state.equipe == "Équipe A" else 1)
        
        st.session_state.type_tracteur = st.selectbox("Type tracteur", 
            ["TAFE", "New Holland", "Massey Ferguson", "John Deere"],
            index=0 if st.session_state.type_tracteur == "TAFE" else 1)
        
        st.session_state.numero_parc = st.text_input("N° Parc", placeholder="Ex: TR-001", value=st.session_state.numero_parc)
        
        st.markdown("---")
        st.markdown("### 📡 Localisation GPS")
        
        # Afficher le composant GPS
        st.components.v1.html(get_gps_component(), height=160)
        
        # Affichage du statut GPS
        if st.session_state.gps_obtenu and st.session_state.latitude:
            st.markdown(f"""
            <div class="gps-card">
                ✅ <b>Position capturée</b><br>
                📍 Latitude: {st.session_state.latitude:.6f}<br>
                🧭 Longitude: {st.session_state.longitude:.6f}
            </div>
            """, unsafe_allow_html=True)
            st.success("✅ GPS Prêt - Vous pouvez continuer")
            
            if st.button("🔄 Recapturer position GPS"):
                st.session_state.gps_obtenu = False
                st.session_state.latitude = None
                st.session_state.longitude = None
                st.rerun()
        else:
            st.info("ℹ️ Cliquez sur 'Obtenir ma position GPS' pour commencer")
        
    else:
        st.session_state.role = "dashboard"
    
    st.markdown("---")
    st.caption("💡 Obtenez votre position GPS en premier lieu")

# ==================== MODE AGENT ====================
if st.session_state.role == "agent":
    
    st.markdown("""
    <div class="main-header">
        <h1>🗑️ Agent de Collecte - Mékhé</h1>
        <p>Remplissez le formulaire étape par étape</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Vérification du nom agent
    if not st.session_state.agent_nom:
        st.warning("⚠️ Veuillez entrer votre nom dans la barre latérale (menu de gauche)")
        st.stop()
    
    # Affichage des infos
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"👤 **Agent:** {st.session_state.agent_nom}")
    with col2:
        st.info(f"📍 **Quartier:** {st.session_state.quartier}")
    with col3:
        st.info(f"👥 **Équipe:** {st.session_state.equipe}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🚜 **Tracteur:** {st.session_state.type_tracteur}")
    with col2:
        st.info(f"🔢 **N° Parc:** {st.session_state.numero_parc or 'Non renseigné'}")
    
    st.markdown("---")
    
    # ==================== ÉTAPE 1: GPS ====================
    st.markdown("""
    <div class="step-indicator">
        <h3>✅ ÉTAPE 1: Localisation GPS</h3>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.gps_obtenu and st.session_state.latitude:
        st.success(f"""
        ✅ Position GPS capturée avec succès
        - Latitude: {st.session_state.latitude:.6f}
        - Longitude: {st.session_state.longitude:.6f}
        """)
        gps_ready = True
    else:
        st.error("❌ GPS non obtenu - Cliquez sur 'Obtenir ma position GPS' dans la barre latérale")
        gps_ready = False
        st.stop()
    
    st.markdown("---")
    
    # ==================== ÉTAPE 2: ACTIONS DE COLLECTE ====================
    st.markdown("""
    <div class="step-indicator">
        <h3>📋 ÉTAPE 2: Enregistrement des actions</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("🚀 DÉPART", use_container_width=True, type="primary"):
            if gps_ready:
                current_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.horaires["depart"] = current_time
                st.session_state.points.append({
                    "type": "depart",
                    "titre": "🏭 Départ du dépôt",
                    "heure": current_time,
                    "lat": st.session_state.latitude,
                    "lon": st.session_state.longitude
                })
                st.success(f"✅ DÉPART enregistré à {current_time}")
                st.balloons()
                st.rerun()
            else:
                st.error("❌ Capturez d'abord votre position GPS")
    
    with col2:
        if st.button("🗑️ DÉB. COL. 1", use_container_width=True):
            if gps_ready:
                current_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.horaires["debut_collecte1"] = current_time
                st.session_state.points.append({
                    "type": "debut_collecte1",
                    "titre": "🗑️ Début collecte 1",
                    "heure": current_time,
                    "lat": st.session_state.latitude,
                    "lon": st.session_state.longitude
                })
                st.success(f"✅ DÉBUT COLLECTE 1 à {current_time}")
                st.rerun()
            else:
                st.error("❌ Capturez d'abord votre position GPS")
    
    with col3:
        if st.button("🏁 FIN COL. 1", use_container_width=True):
            if gps_ready:
                current_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.horaires["fin_collecte1"] = current_time
                st.session_state.collecte1_terminee = True
                st.session_state.points.append({
                    "type": "fin_collecte1",
                    "titre": "🏁 Fin collecte 1",
                    "heure": current_time,
                    "lat": st.session_state.latitude,
                    "lon": st.session_state.longitude
                })
                st.success(f"✅ FIN COLLECTE 1 à {current_time}")
                st.rerun()
            else:
                st.error("❌ Capturez d'abord votre position GPS")
    
    with col4:
        if st.button("🚛 VIDAGE 1", use_container_width=True):
            if gps_ready:
                current_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.horaires["decharge1"] = current_time
                st.session_state.points.append({
                    "type": "decharge1",
                    "titre": "🚛 Vidage décharge 1",
                    "heure": current_time,
                    "lat": st.session_state.latitude,
                    "lon": st.session_state.longitude
                })
                st.success(f"✅ VIDAGE DÉCHARGE 1 à {current_time}")
                st.rerun()
            else:
                st.error("❌ Capturez d'abord votre position GPS")
    
    with col5:
        if st.button("🏁 RETOUR", use_container_width=True):
            if gps_ready:
                current_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.horaires["retour"] = current_time
                st.session_state.points.append({
                    "type": "retour",
                    "titre": "🏁 Retour au dépôt",
                    "heure": current_time,
                    "lat": st.session_state.latitude,
                    "lon": st.session_state.longitude
                })
                st.success(f"✅ RETOUR enregistré à {current_time}")
                st.rerun()
            else:
                st.error("❌ Capturez d'abord votre position GPS")
    
    st.markdown("---")
    
    # ==================== ÉTAPE 3: VOLUME COLLECTE 1 ====================
    st.markdown("""
    <div class="step-indicator">
        <h3>📦 ÉTAPE 3: Volume de la collecte 1</h3>
    </div>
    """, unsafe_allow_html=True)
    
    v1 = st.number_input("Volume collecte 1 (m³)", 0.0, 20.0, st.session_state.volumes["collecte1"], 0.5, key="vol1")
    if v1 != st.session_state.volumes["collecte1"]:
        st.session_state.volumes["collecte1"] = v1
    
    if v1 > 0:
        taux = (v1 / 10) * 100
        st.progress(min(taux/100, 1.0))
        st.caption(f"📊 Taux de remplissage : {taux:.0f}% (capacité remorque: 10m³)")
    
    st.markdown("---")
    
    # ==================== ÉTAPE 4: COLLECTE 2 OPTIONNELLE ====================
    if st.session_state.collecte1_terminee and not st.session_state.collecte2_active:
        st.markdown("""
        <div class="step-indicator">
            <h3>🚛 ÉTAPE 4: Collecte 2 (Optionnelle)</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ ACTIVER COLLECTE 2", use_container_width=True, type="primary"):
                st.session_state.collecte2_active = True
                st.success("✅ Collecte 2 activée")
                st.rerun()
        with col2:
            if st.button("⏭️ PASSER COLLECTE 2", use_container_width=True):
                st.session_state.collecte2_active = True
                st.info("Collecte 2 ignorée")
                st.rerun()
    
    if st.session_state.collecte2_active and "fin_collecte2" not in st.session_state.horaires:
        st.markdown("""
        <div class="step-indicator">
            <h3>🚛 Collecte 2 - Actions</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🗑️ DÉB. COL. 2", use_container_width=True):
                if gps_ready:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.horaires["debut_collecte2"] = current_time
                    st.session_state.points.append({
                        "type": "debut_collecte2",
                        "titre": "🗑️ Début collecte 2",
                        "heure": current_time,
                        "lat": st.session_state.latitude,
                        "lon": st.session_state.longitude
                    })
                    st.success(f"✅ DÉBUT COLLECTE 2 à {current_time}")
                    st.rerun()
        
        with col2:
            if st.button("🏁 FIN COL. 2", use_container_width=True):
                if gps_ready:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.horaires["fin_collecte2"] = current_time
                    st.session_state.points.append({
                        "type": "fin_collecte2",
                        "titre": "🏁 Fin collecte 2",
                        "heure": current_time,
                        "lat": st.session_state.latitude,
                        "lon": st.session_state.longitude
                    })
                    st.success(f"✅ FIN COLLECTE 2 à {current_time}")
                    st.rerun()
        
        with col3:
            if st.button("🚛 VIDAGE 2", use_container_width=True):
                if gps_ready:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.horaires["decharge2"] = current_time
                    st.session_state.points.append({
                        "type": "decharge2",
                        "titre": "🚛 Second vidage",
                        "heure": current_time,
                        "lat": st.session_state.latitude,
                        "lon": st.session_state.longitude
                    })
                    st.success(f"✅ SECOND VIDAGE à {current_time}")
                    st.rerun()
        
        st.markdown("### 📦 Volume collecte 2")
        v2 = st.number_input("Volume collecte 2 (m³)", 0.0, 20.0, st.session_state.volumes["collecte2"], 0.5, key="vol2")
        if v2 != st.session_state.volumes["collecte2"]:
            st.session_state.volumes["collecte2"] = v2
    
    st.markdown("---")
    
    # ==================== RÉCAPITULATIF ====================
    with st.expander("📋 Voir le récapitulatif de la tournée"):
        if st.session_state.horaires:
            st.markdown("**⏰ Horaires enregistrés :**")
            for key, value in st.session_state.horaires.items():
                st.write(f"- {key}: {value}")
        else:
            st.info("Aucun horaire enregistré")
        
        if st.session_state.points:
            st.markdown("**📍 Points GPS enregistrés :**")
            for p in st.session_state.points:
                st.write(f"- {p['titre']} à {p['heure']} → ({p['lat']:.6f}, {p['lon']:.6f})")
        else:
            st.info("Aucun point GPS enregistré")
        
        st.markdown("**📦 Volumes :**")
        st.write(f"- Collecte 1: {st.session_state.volumes['collecte1']} m³")
        st.write(f"- Collecte 2: {st.session_state.volumes['collecte2']} m³")
        st.write(f"- **Total: {st.session_state.volumes['collecte1'] + st.session_state.volumes['collecte2']} m³**")
    
    # ==================== CARTE ====================
    points_valides = [p for p in st.session_state.points if p.get("lat") and p.get("lon")]
    if len(points_valides) >= 1:
        st.markdown("### 🗺️ Carte des points GPS")
        
        center_lat = points_valides[0]["lat"]
        center_lon = points_valides[0]["lon"]
        m = folium.Map(location=[center_lat, center_lon], zoom_start=15)
        
        couleurs = {
            "depart": "green",
            "debut_collecte1": "blue",
            "fin_collecte1": "lightblue",
            "decharge1": "red",
            "debut_collecte2": "purple",
            "fin_collecte2": "lightpurple",
            "decharge2": "darkred",
            "retour": "brown"
        }
        
        for i, p in enumerate(points_valides):
            color = couleurs.get(p["type"], "gray")
            folium.Marker(
                [p["lat"], p["lon"]],
                popup=f"<b>{p['titre']}</b><br>{p['heure']}",
                icon=folium.Icon(color=color, prefix='fa'),
                tooltip=f"{i+1}. {p['titre']}"
            ).add_to(m)
        
        if len(points_valides) > 1:
            coords = [[p["lat"], p["lon"]] for p in points_valides]
            folium.PolyLine(coords, color="blue", weight=3, opacity=0.7).add_to(m)
            
            # Calculer distance
            distance_totale = 0
            for i in range(1, len(coords)):
                R = 6371
                lat1, lon1, lat2, lon2 = map(radians, [coords[i-1][0], coords[i-1][1], coords[i][0], coords[i][1]])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                distance_totale += R * c
            st.caption(f"📏 Distance totale parcourue : {distance_totale:.2f} km")
        
        folium_static(m, width=1000, height=500)
    
    # ==================== TERMINER ====================
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("✅ TERMINER LA TOURNÉE", type="primary", use_container_width=True, key="finish_button"):
            # Validation
            errors = []
            if not st.session_state.horaires.get("depart"):
                errors.append("❌ Veuillez enregistrer le DÉPART")
            if st.session_state.volumes["collecte1"] == 0:
                errors.append("❌ Veuillez entrer le volume de la collecte 1")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                total_volume = st.session_state.volumes["collecte1"] + st.session_state.volumes["collecte2"]
                
                st.balloons()
                st.success(f"""
                ✅ **TOURNÉE TERMINÉE AVEC SUCCÈS !**
                
                📊 **Récapitulatif final**
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                👤 **Agent :** {st.session_state.agent_nom}
                📍 **Quartier :** {st.session_state.quartier}
                👥 **Équipe :** {st.session_state.equipe}
                🚜 **Tracteur :** {st.session_state.type_tracteur} {st.session_state.numero_parc}
                📦 **Volume total :** {total_volume} m³
                📍 **Points GPS :** {len(st.session_state.points)}
                """)
                
                # Enregistrement dans la base
                if engine:
                    try:
                        with engine.connect() as conn:
                            try:
                                conn.execute(text("ALTER TABLE tournees ALTER COLUMN quartier_id DROP NOT NULL;"))
                                conn.execute(text("ALTER TABLE tournees ALTER COLUMN equipe_id DROP NOT NULL;"))
                            except:
                                pass
                            
                            result = conn.execute(text("""
                                INSERT INTO tournees (
                                    date_tournee, agent_nom, quartier_id, equipe_id,
                                    volume_collecte1, volume_collecte2,
                                    heure_depot_depart, heure_retour_depot,
                                    heure_debut_collecte1, heure_fin_collecte1,
                                    heure_arrivee_decharge1, statut
                                ) VALUES (
                                    :date, :agent, 1, 1,
                                    :vol1, :vol2,
                                    :depart, :retour, :debut1, :fin1, :decharge1, 'termine'
                                ) RETURNING id
                            """), {
                                "date": date.today(),
                                "agent": st.session_state.agent_nom,
                                "vol1": st.session_state.volumes["collecte1"],
                                "vol2": st.session_state.volumes["collecte2"],
                                "depart": st.session_state.horaires.get("depart"),
                                "retour": st.session_state.horaires.get("retour"),
                                "debut1": st.session_state.horaires.get("debut_collecte1"),
                                "fin1": st.session_state.horaires.get("fin_collecte1"),
                                "decharge1": st.session_state.horaires.get("decharge1")
                            })
                            tournee_id = result.fetchone()[0]
                            
                            for point in st.session_state.points:
                                if point.get("lat") and point.get("lon"):
                                    conn.execute(text("""
                                        INSERT INTO points_arret (tournee_id, type_point, latitude, longitude, heure)
                                        VALUES (:tid, :type, :lat, :lon, :heure)
                                    """), {
                                        "tid": tournee_id,
                                        "type": point["type"],
                                        "lat": point["lat"],
                                        "lon": point["lon"],
                                        "heure": point["heure"]
                                    })
                            conn.commit()
                            st.success("✅ Données enregistrées dans la base de données !")
                    except Exception as e:
                        st.warning(f"⚠️ Erreur base de données: {e}")
                
                st.markdown("---")
                if st.button("🔄 NOUVELLE TOURNÉE", use_container_width=True, type="primary"):
                    st.session_state.points = []
                    st.session_state.horaires = {}
                    st.session_state.volumes = {"collecte1": 0.0, "collecte2": 0.0}
                    st.session_state.collecte2_active = False
                    st.session_state.collecte1_terminee = False
                    st.session_state.gps_obtenu = False
                    st.session_state.latitude = None
                    st.session_state.longitude = None
                    st.rerun()

# ==================== MODE DASHBOARD ====================
else:
    st.markdown("""
    <div class="main-header">
        <h1>📊 Tableau de bord - Collecte des déchets</h1>
        <p>Commune de Mékhé</p>
    </div>
    """, unsafe_allow_html=True)
    
    if engine:
        try:
            df_tournees = pd.read_sql("SELECT * FROM tournees ORDER BY date_tournee DESC LIMIT 100", engine)
            df_points = pd.read_sql("SELECT * FROM points_arret WHERE latitude IS NOT NULL ORDER BY id DESC LIMIT 500", engine)
            
            if df_tournees.empty:
                st.info("📭 Aucune collecte enregistrée")
            else:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📋 Collectes", len(df_tournees))
                with col2:
                    total_volume = (df_tournees["volume_collecte1"].fillna(0).sum() + 
                                  df_tournees["volume_collecte2"].fillna(0).sum())
                    st.metric("📦 Volume total", f"{total_volume:.1f} m³")
                with col3:
                    st.metric("📍 Points GPS", len(df_points))
                with col4:
                    st.metric("👤 Dernier agent", df_tournees.iloc[0]["agent_nom"] if not df_tournees.empty else "-")
                
                if not df_points.empty:
                    st.subheader("🗺️ Carte des points GPS")
                    points_map = df_points.dropna(subset=["latitude", "longitude"])
                    if not points_map.empty:
                        m = folium.Map(
                            location=[points_map["latitude"].mean(), points_map["longitude"].mean()], 
                            zoom_start=13
                        )
                        for _, p in points_map.iterrows():
                            folium.Marker(
                                [p["latitude"], p["longitude"]], 
                                popup=p["type_point"], 
                                icon=folium.Icon(color="blue")
                            ).add_to(m)
                        folium_static(m, width=1000, height=500)
                
                st.subheader("📋 Liste des collectes")
                st.dataframe(
                    df_tournees[["date_tournee", "agent_nom", "volume_collecte1", "volume_collecte2"]], 
                    use_container_width=True
                )
                
                if st.button("📥 EXPORTER EN EXCEL"):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_tournees.to_excel(writer, sheet_name="Collectes", index=False)
                        if not df_points.empty:
                            df_points.to_excel(writer, sheet_name="Points GPS", index=False)
                    st.download_button(
                        "📥 Télécharger", 
                        output.getvalue(), 
                        f"dashboard_mekhe_{date.today()}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        except Exception as e:
            st.info(f"📭 Base en attente: {e}")

# ==================== CONSIGNES SÉCURITÉ ====================
with st.expander("🛡️ Consignes de sécurité"):
    st.markdown("""
    1. **Gestes et postures** : Pliez les jambes pour soulever
    2. **Protection** : Portez gants et masque
    3. **Ne montez pas sur le tracteur**
    4. **Éloignez-vous lors du vidage**
    5. **Circulation** : Ne restez pas au milieu de la route
    """)

st.caption(f"📍 GPS via composant HTML | {'Agent: ' + st.session_state.agent_nom if st.session_state.role == 'agent' else 'Dashboard'} | 🗑️ Commune de Mékhé | ✅ v2.0 Optimisée")
