"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version finale avec :
- GPS réel à chaque clic
- Interface simple (boutons)
- Collecte 2 optionnelle
- Base Neon.tech
- Dashboard intégré
"""

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
    """Initialise la connexion à la base Neon.tech"""
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

# ==================== FONCTION GPS JAVASCRIPT ====================
def get_gps_button_js(button_id):
    """Génère le JavaScript pour obtenir la position GPS au moment du clic"""
    return f"""
    <div id="gps_status_{button_id}" style="margin-bottom: 5px; font-size: 12px; text-align: center;"></div>
    <button onclick="getPosition_{button_id}()" style="background-color: #2196F3; color: white; padding: 10px; border: none; border-radius: 8px; width: 100%; cursor: pointer; font-size: 14px;">
        📍 Obtenir position
    </button>
    <script>
    function getPosition_{button_id}() {{
        if (navigator.geolocation) {{
            var statusDiv = document.getElementById('gps_status_{button_id}');
            statusDiv.innerHTML = '🔍 Recherche GPS...';
            statusDiv.style.color = '#ff9800';
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    var lat = position.coords.latitude;
                    var lon = position.coords.longitude;
                    statusDiv.innerHTML = '✅ Position: ' + lat.toFixed(6) + ', ' + lon.toFixed(6);
                    statusDiv.style.color = '#4CAF50';
                    
                    const data = {{lat: lat, lon: lon}};
                    const event = new CustomEvent('streamlit:setComponentValue', {{
                        detail: {{value: JSON.stringify(data)}}
                    }});
                    window.dispatchEvent(event);
                }},
                function(error) {{
                    var statusDiv = document.getElementById('gps_status_{button_id}');
                    var errorMsg = '';
                    switch(error.code) {{
                        case error.PERMISSION_DENIED:
                            errorMsg = 'Permission refusée. Activez la localisation.';
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMsg = 'Position non disponible.';
                            break;
                        case error.TIMEOUT:
                            errorMsg = 'Délai dépassé. Réessayez.';
                            break;
                        default:
                            errorMsg = 'Erreur GPS';
                    }}
                    statusDiv.innerHTML = '❌ ' + errorMsg;
                    statusDiv.style.color = '#f44336';
                }},
                {{enableHighAccuracy: true, timeout: 10000}}
            );
        }} else {{
            document.getElementById('gps_status_{button_id}').innerHTML = '❌ GPS non supporté par ce navigateur';
            document.getElementById('gps_status_{button_id}').style.color = '#f44336';
        }}
    }}
    </script>
    """

# ==================== STYLE CSS ====================
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
    .dashboard-header {
        background: linear-gradient(135deg, #1565C0 0%, #0D47A1 100%);
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
    .action-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #2196F3;
    }
    .info-text {
        font-size: 12px;
        color: #666;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== INITIALISATION SESSION ====================
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'role' not in st.session_state:
    st.session_state.role = "agent"
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
if 'gps_temporaire' not in st.session_state:
    st.session_state.gps_temporaire = {"lat": None, "lon": None}

# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("### 🗑️ Commune de Mékhé")
    st.markdown("---")
    
    mode = st.radio("🔐 Mode", ["🧑‍🌾 Agent de terrain", "📊 Responsable / Dashboard"])
    
    if mode == "🧑‍🌾 Agent de terrain":
        st.session_state.role = "agent"
        st.markdown("---")
        st.session_state.agent_nom = st.text_input("✍️ Votre nom", placeholder="Ex: Alioune Diop")
    else:
        st.session_state.role = "dashboard"
    
    st.markdown("---")
    st.caption("📍 GPS temps réel à chaque clic")
    st.caption("📱 Autorisez la localisation dans votre navigateur")

# Champ caché pour recevoir les positions GPS
gps_receiver = st.text_input("", key="gps_receiver", label_visibility="collapsed", placeholder="")

if gps_receiver:
    try:
        gps_data = json.loads(gps_receiver)
        st.session_state.gps_temporaire["lat"] = gps_data["lat"]
        st.session_state.gps_temporaire["lon"] = gps_data["lon"]
    except:
        pass

# ==================== MODE AGENT ====================
if st.session_state.role == "agent":
    
    # En-tête
    st.markdown("""
    <div class="main-header">
        <h1>🗑️ Agent de Collecte - Mékhé</h1>
        <p>Pour chaque action : cliquez sur "Obtenir position" puis sur le bouton d'enregistrement</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Vérification du nom
    if not st.session_state.agent_nom:
        st.warning("⚠️ Veuillez entrer votre nom dans la barre latérale")
        st.stop()
    
    st.success(f"✅ Agent connecté : {st.session_state.agent_nom}")
    st.info("💡 **Conseil :** Activez la localisation sur votre téléphone et autorisez le navigateur à y accéder")
    
    st.markdown("---")
    
    # ==================== ACTION DÉPART ====================
    with st.container():
        st.markdown("### 🚀 1. DÉPART / DEMM")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.components.v1.html(get_gps_button_js("depart"), height=100)
        with col2:
            if st.button("✅ Enregistrer le DÉPART", key="btn_depart", use_container_width=True, type="primary"):
                if st.session_state.gps_temporaire["lat"] is None:
                    st.warning("⚠️ Cliquez d'abord sur 'Obtenir position'")
                else:
                    st.session_state.horaires["depart"] = datetime.now().strftime("%H:%M:%S")
                    st.session_state.points.append({
                        "type": "depart",
                        "titre": "🏭 Départ du dépôt",
                        "heure": st.session_state.horaires["depart"],
                        "lat": st.session_state.gps_temporaire["lat"],
                        "lon": st.session_state.gps_temporaire["lon"]
                    })
                    st.success(f"✅ Départ enregistré à {st.session_state.horaires['depart']}")
                    st.info(f"📍 Position: {st.session_state.gps_temporaire['lat']:.6f}, {st.session_state.gps_temporaire['lon']:.6f}")
                    st.session_state.gps_temporaire = {"lat": None, "lon": None}
                    st.balloons()
    
    st.markdown("---")
    
    # ==================== ACTION DÉBUT COLLECTE 1 ====================
    with st.container():
        st.markdown("### 🗑️ 2. DÉBUT COLLECTE 1 / TÀBB")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.components.v1.html(get_gps_button_js("collecte1"), height=100)
        with col2:
            if st.button("✅ Enregistrer DÉBUT COLLECTE 1", key="btn_collecte1", use_container_width=True):
                if st.session_state.gps_temporaire["lat"] is None:
                    st.warning("⚠️ Cliquez d'abord sur 'Obtenir position'")
                else:
                    st.session_state.horaires["debut_collecte1"] = datetime.now().strftime("%H:%M:%S")
                    st.session_state.points.append({
                        "type": "debut_collecte1",
                        "titre": "🗑️ Début collecte 1",
                        "heure": st.session_state.horaires["debut_collecte1"],
                        "lat": st.session_state.gps_temporaire["lat"],
                        "lon": st.session_state.gps_temporaire["lon"]
                    })
                    st.success(f"✅ Début collecte 1 à {st.session_state.horaires['debut_collecte1']}")
                    st.info(f"📍 Position: {st.session_state.gps_temporaire['lat']:.6f}, {st.session_state.gps_temporaire['lon']:.6f}")
                    st.session_state.gps_temporaire = {"lat": None, "lon": None}
    
    st.markdown("---")
    
    # ==================== ACTION FIN COLLECTE 1 ====================
    with st.container():
        st.markdown("### 🏁 3. FIN COLLECTE 1")
        if st.button("🏁 Enregistrer FIN COLLECTE 1", use_container_width=True):
            st.session_state.horaires["fin_collecte1"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.collecte1_terminee = True
            st.success(f"✅ Fin collecte 1 à {st.session_state.horaires['fin_collecte1']}")
    
    st.markdown("---")
    
    # ==================== ACTION VIDAGE DÉCHARGE ====================
    with st.container():
        st.markdown("### 🚛 4. VIDAGE DÉCHARGE / TÒGG")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.components.v1.html(get_gps_button_js("decharge"), height=100)
        with col2:
            if st.button("✅ Enregistrer VIDAGE", key="btn_decharge", use_container_width=True):
                if st.session_state.gps_temporaire["lat"] is None:
                    st.warning("⚠️ Cliquez d'abord sur 'Obtenir position'")
                else:
                    st.session_state.horaires["decharge"] = datetime.now().strftime("%H:%M:%S")
                    st.session_state.points.append({
                        "type": "decharge",
                        "titre": "🚛 Vidage à la décharge",
                        "heure": st.session_state.horaires["decharge"],
                        "lat": st.session_state.gps_temporaire["lat"],
                        "lon": st.session_state.gps_temporaire["lon"]
                    })
                    st.success(f"✅ Vidage à {st.session_state.horaires['decharge']}")
                    st.info(f"📍 Position décharge: {st.session_state.gps_temporaire['lat']:.6f}, {st.session_state.gps_temporaire['lon']:.6f}")
                    st.session_state.gps_temporaire = {"lat": None, "lon": None}
    
    st.markdown("---")
    
    # ==================== VOLUME COLLECTE 1 ====================
    st.markdown("### 📦 Volume collecte 1")
    v1 = st.number_input("Volume (m³)", 0.0, 20.0, st.session_state.volumes["collecte1"], 0.5, key="vol1")
    if v1 != st.session_state.volumes["collecte1"]:
        st.session_state.volumes["collecte1"] = v1
    
    if v1 > 0:
        taux = (v1 / 10) * 100
        st.progress(min(taux/100, 1.0))
        st.caption(f"📊 Taux de remplissage : {taux:.0f}% (remorque 10m³)")
    
    st.markdown("---")
    
    # ==================== COLLECTE 2 OPTIONNELLE ====================
    if st.session_state.collecte1_terminee and not st.session_state.collecte2_active:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ ACTIVER COLLECTE 2", use_container_width=True):
                st.session_state.collecte2_active = True
                st.success("✅ Collecte 2 activée")
        with col2:
            if st.button("⏭️ PASSER COLLECTE 2", use_container_width=True):
                st.session_state.collecte2_active = True
                st.info("Collecte 2 ignorée")
    
    if st.session_state.collecte2_active and "fin_collecte2" not in st.session_state.horaires:
        st.markdown("---")
        st.markdown("## 🚛 COLLECTE 2 (Optionnelle)")
        
        # DÉBUT COLLECTE 2
        with st.container():
            st.markdown("### 🗑️ DÉBUT COLLECTE 2")
            col1, col2 = st.columns([1, 2])
            with col1:
                st.components.v1.html(get_gps_button_js("collecte2"), height=100)
            with col2:
                if st.button("✅ Enregistrer DÉBUT COLLECTE 2", key="btn_collecte2", use_container_width=True):
                    if st.session_state.gps_temporaire["lat"] is None:
                        st.warning("⚠️ Cliquez d'abord sur 'Obtenir position'")
                    else:
                        st.session_state.horaires["debut_collecte2"] = datetime.now().strftime("%H:%M:%S")
                        st.session_state.points.append({
                            "type": "debut_collecte2",
                            "titre": "🗑️ Début collecte 2",
                            "heure": st.session_state.horaires["debut_collecte2"],
                            "lat": st.session_state.gps_temporaire["lat"],
                            "lon": st.session_state.gps_temporaire["lon"]
                        })
                        st.success(f"✅ Début collecte 2 à {st.session_state.horaires['debut_collecte2']}")
                        st.session_state.gps_temporaire = {"lat": None, "lon": None}
        
        # FIN COLLECTE 2
        if st.button("🏁 Enregistrer FIN COLLECTE 2", use_container_width=True):
            st.session_state.horaires["fin_collecte2"] = datetime.now().strftime("%H:%M:%S")
            st.success(f"✅ Fin collecte 2 à {st.session_state.horaires['fin_collecte2']}")
        
        # VIDAGE 2
        with st.container():
            st.markdown("### 🚛 SECOND VIDAGE")
            col1, col2 = st.columns([1, 2])
            with col1:
                st.components.v1.html(get_gps_button_js("decharge2"), height=100)
            with col2:
                if st.button("✅ Enregistrer SECOND VIDAGE", key="btn_decharge2", use_container_width=True):
                    if st.session_state.gps_temporaire["lat"] is None:
                        st.warning("⚠️ Cliquez d'abord sur 'Obtenir position'")
                    else:
                        st.session_state.horaires["decharge2"] = datetime.now().strftime("%H:%M:%S")
                        st.session_state.points.append({
                            "type": "decharge2",
                            "titre": "🚛 Second vidage",
                            "heure": st.session_state.horaires["decharge2"],
                            "lat": st.session_state.gps_temporaire["lat"],
                            "lon": st.session_state.gps_temporaire["lon"]
                        })
                        st.success(f"✅ Second vidage à {st.session_state.horaires['decharge2']}")
                        st.session_state.gps_temporaire = {"lat": None, "lon": None}
        
        # VOLUME COLLECTE 2
        v2 = st.number_input("📦 Volume collecte 2 (m³)", 0.0, 20.0, st.session_state.volumes["collecte2"], 0.5, key="vol2")
        if v2 != st.session_state.volumes["collecte2"]:
            st.session_state.volumes["collecte2"] = v2
        
        st.markdown("---")
    
    # ==================== ACTION RETOUR ====================
    with st.container():
        st.markdown("## 🏁 5. RETOUR AU DÉPÔT / FANAN")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.components.v1.html(get_gps_button_js("retour"), height=100)
        with col2:
            if st.button("✅ Enregistrer le RETOUR", key="btn_retour", use_container_width=True, type="primary"):
                if st.session_state.gps_temporaire["lat"] is None:
                    st.warning("⚠️ Cliquez d'abord sur 'Obtenir position'")
                else:
                    st.session_state.horaires["retour"] = datetime.now().strftime("%H:%M:%S")
                    st.session_state.points.append({
                        "type": "retour",
                        "titre": "🏁 Retour au dépôt",
                        "heure": st.session_state.horaires["retour"],
                        "lat": st.session_state.gps_temporaire["lat"],
                        "lon": st.session_state.gps_temporaire["lon"]
                    })
                    st.success(f"✅ Retour enregistré à {st.session_state.horaires['retour']}")
                    st.info(f"📍 Position retour: {st.session_state.gps_temporaire['lat']:.6f}, {st.session_state.gps_temporaire['lon']:.6f}")
                    st.session_state.gps_temporaire = {"lat": None, "lon": None}
    
    st.markdown("---")
    
    # ==================== RÉCAPITULATIF ====================
    with st.expander("📋 Voir le récapitulatif de la tournée"):
        if st.session_state.horaires:
            st.markdown("**Horaires enregistrés :**")
            horaire_df = pd.DataFrame(list(st.session_state.horaires.items()), columns=["Étape", "Heure"])
            st.dataframe(horaire_df, use_container_width=True)
        else:
            st.info("Aucun horaire enregistré pour le moment")
        
        if st.session_state.points:
            st.markdown("**Points GPS enregistrés :**")
            points_df = pd.DataFrame([(p["titre"], p["heure"], p["lat"], p["lon"]) for p in st.session_state.points], 
                                      columns=["Action", "Heure", "Latitude", "Longitude"])
            st.dataframe(points_df, use_container_width=True)
    
    # ==================== CARTE ====================
    if st.session_state.points:
        points_valides = [p for p in st.session_state.points if p["lat"]]
        if len(points_valides) >= 1:
            st.markdown("### 🗺️ Carte des points")
            
            center_lat = points_valides[0]["lat"]
            center_lon = points_valides[0]["lon"]
            m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
            
            couleurs = {
                "depart": "green",
                "debut_collecte1": "blue",
                "debut_collecte2": "purple",
                "decharge": "red",
                "decharge2": "darkred",
                "retour": "brown"
            }
            
            for p in points_valides:
                color = couleurs.get(p["type"], "gray")
                folium.Marker(
                    [p["lat"], p["lon"]],
                    popup=f"<b>{p['titre']}</b><br>{p['heure']}",
                    icon=folium.Icon(color=color)
                ).add_to(m)
            
            if len(points_valides) > 1:
                coords = [[p["lat"], p["lon"]] for p in points_valides]
                folium.PolyLine(coords, color="blue", weight=3, opacity=0.7).add_to(m)
            
            folium_static(m, width=800, height=400)
    
    # ==================== TERMINER ====================
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("✅ TERMINER LA TOURNÉE", type="primary", use_container_width=True):
            if not st.session_state.horaires.get("depart"):
                st.warning("⚠️ Veuillez enregistrer le départ")
            elif st.session_state.volumes["collecte1"] == 0:
                st.warning("⚠️ Veuillez entrer le volume de la collecte 1")
            else:
                total_volume = st.session_state.volumes["collecte1"] + st.session_state.volumes["collecte2"]
                
                st.balloons()
                st.success(f"""
                ✅ **TOURNÉE TERMINÉE AVEC SUCCÈS !**
                
                📊 **Récapitulatif final**
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                👤 **Agent :** {st.session_state.agent_nom}
                📦 **Volume total :** {total_volume} m³
                📍 **Points GPS :** {len(st.session_state.points)}
                🕐 **Départ :** {st.session_state.horaires.get('depart', 'N/A')}
                🕐 **Retour :** {st.session_state.horaires.get('retour', 'N/A')}
                """)
                
                # Enregistrement dans la base Neon.tech
                if engine:
                    try:
                        with engine.connect() as conn:
                            # S'assurer que les colonnes n'ont pas de contrainte NOT NULL
                            try:
                                conn.execute(text("ALTER TABLE tournees ALTER COLUMN quartier_id DROP NOT NULL;"))
                                conn.execute(text("ALTER TABLE tournees ALTER COLUMN equipe_id DROP NOT NULL;"))
                                conn.commit()
                            except:
                                pass
                            
                            # Insérer la tournée
                            result = conn.execute(text("""
                                INSERT INTO tournees (
                                    date_tournee, agent_nom, volume_collecte1, volume_collecte2,
                                    heure_depot_depart, heure_retour_depot,
                                    heure_debut_collecte1, heure_fin_collecte1,
                                    heure_arrivee_decharge1, statut
                                ) VALUES (
                                    :date, :agent, :vol1, :vol2,
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
                                "decharge1": st.session_state.horaires.get("decharge")
                            })
                            tournee_id = result.fetchone()[0]
                            
                            # Insérer les points GPS
                            for point in st.session_state.points:
                                if point["lat"] and point["lon"]:
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
                            st.success("✅ Données enregistrées dans la base Neon.tech !")
                    except Exception as e:
                        st.warning(f"⚠️ Base de données: {e}")
                
                # Proposer une nouvelle tournée
                if st.button("🔄 NOUVELLE TOURNÉE", use_container_width=True):
                    st.session_state.points = []
                    st.session_state.horaires = {}
                    st.session_state.volumes = {"collecte1": 0.0, "collecte2": 0.0}
                    st.session_state.collecte2_active = False
                    st.session_state.collecte1_terminee = False
                    st.session_state.gps_temporaire = {"lat": None, "lon": None}
                    st.rerun()

# ==================== MODE DASHBOARD ====================
else:
    st.markdown("""
    <div class="dashboard-header">
        <h1>📊 Tableau de bord - Collecte des déchets</h1>
        <p>Commune de Mékhé | Suivi des performances</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not engine:
        st.error("❌ Base de données non accessible")
        st.stop()
    
    try:
        # Chargement des données
        df_tournees = pd.read_sql("""
            SELECT id, date_tournee, agent_nom, volume_collecte1, volume_collecte2,
                   (volume_collecte1 + volume_collecte2) as volume_total,
                   heure_depot_depart, heure_retour_depot, statut
            FROM tournees 
            WHERE statut = 'termine'
            ORDER BY date_tournee DESC 
            LIMIT 100
        """, engine)
        
        df_points = pd.read_sql("""
            SELECT id, tournee_id, type_point, latitude, longitude, heure
            FROM points_arret 
            WHERE latitude IS NOT NULL 
            ORDER BY id DESC 
            LIMIT 500
        """, engine)
        
        if df_tournees.empty:
            st.info("📭 Aucune collecte enregistrée pour le moment")
            st.stop()
        
        # KPI
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📋 Collectes", len(df_tournees))
        with col2:
            total_volume = df_tournees["volume_total"].sum()
            st.metric("📦 Volume total", f"{total_volume:.1f} m³")
        with col3:
            st.metric("📍 Points GPS", len(df_points))
        with col4:
            dernier_agent = df_tournees.iloc[0]["agent_nom"] if not df_tournees.empty else "-"
            st.metric("👤 Dernier agent", dernier_agent)
        
        st.markdown("---")
        
        # Graphiques
        col1, col2 = st.columns(2)
        with col1:
            volume_par_jour = df_tournees.groupby("date_tournee")["volume_total"].sum().reset_index()
            st.subheader("📈 Volume par jour")
            st.line_chart(volume_par_jour.set_index("date_tournee"))
        
        with col2:
            volume_par_agent = df_tournees.groupby("agent_nom")["volume_total"].sum().reset_index()
            st.subheader("👥 Volume par agent")
            st.bar_chart(volume_par_agent.set_index("agent_nom"))
        
        st.markdown("---")
        
        # Carte des points GPS
        if not df_points.empty:
            st.subheader("🗺️ Carte des points GPS")
            points_map = df_points.dropna(subset=["latitude", "longitude"])
            if not points_map.empty:
                m = folium.Map(location=[points_map["latitude"].mean(), points_map["longitude"].mean()], zoom_start=13)
                for _, p in points_map.iterrows():
                    folium.Marker(
                        [p["latitude"], p["longitude"]],
                        popup=f"Tournée #{p['tournee_id']}<br>{p['type_point']}<br>{p['heure']}",
                        icon=folium.Icon(color="blue", icon="info-sign")
                    ).add_to(m)
                folium_static(m, width=800, height=400)
        
        st.markdown("---")
        
        # Tableau des collectes
        st.subheader("📋 Liste des collectes")
        st.dataframe(df_tournees[["date_tournee", "agent_nom", "volume_total", "heure_depot_depart", "heure_retour_depot"]], use_container_width=True)
        
        # Export Excel
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📥 EXPORTER EN EXCEL", type="primary", use_container_width=True):
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
        st.info(f"📭 Base de données en attente: {e}")

# ==================== CONSIGNES SÉCURITÉ ====================
with st.expander("🛡️ Consignes de sécurité / Làppu sécurité"):
    st.markdown("""
    ### ⚠️ RAPPEL QUOTIDIEN
    
    1. **Gestes et postures / Baal sa bànqaas** : Pliez les jambes pour soulever les charges
    2. **Protection / Jar gi ak noppal** : Portez toujours vos gants et votre masque
    3. **Ne montez pas sur le tracteur / Bul wàcc ci tracteur bu ngi faj**
    4. **Lors du vidage / Bul def ci diggante bu yendu remorque** : Éloignez-vous de la remorque
    5. **Circulation / Bul koom ci ndaw** : Ne restez pas au milieu de la route pour charger
    
    🔔 **En cas de problème, contactez immédiatement votre responsable**
    """)

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📍 GPS temps réel | {'Agent: ' + st.session_state.agent_nom if st.session_state.role == 'agent' else 'Dashboard'} | 🗑️ Commune de Mékhé")
