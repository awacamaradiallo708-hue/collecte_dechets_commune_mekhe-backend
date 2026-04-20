"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version finale avec :
- GPS automatique à chaque clic (pas de bouton "Obtenir position" séparé)
- Choix du quartier, équipe, type de tracteur
- Collecte 2 optionnelle
- Base Neon.tech
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

# ==================== FONCTION GPS AUTOMATIQUE ====================
def get_gps_auto_js(button_id):
    """Génère le JavaScript qui obtient la position ET exécute l'action"""
    return f"""
    <div id="gps_status_{button_id}" style="margin-bottom: 5px; font-size: 12px; text-align: center; color: #666;"></div>
    <button onclick="getPositionAndAction_{button_id}()" style="background-color: #4CAF50; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%; cursor: pointer; font-size: 16px; font-weight: bold;">
        🚀 DÉPART / DEMM
    </button>
    <script>
    function getPositionAndAction_{button_id}() {{
        var statusDiv = document.getElementById('gps_status_{button_id}');
        statusDiv.innerHTML = '📍 Recherche GPS en cours...';
        statusDiv.style.color = '#ff9800';
        
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    var lat = position.coords.latitude;
                    var lon = position.coords.longitude;
                    statusDiv.innerHTML = '✅ Position trouvée ! Enregistrement...';
                    statusDiv.style.color = '#4CAF50';
                    
                    const data = {{action: 'depart', lat: lat, lon: lon}};
                    const event = new CustomEvent('streamlit:setComponentValue', {{
                        detail: {{value: JSON.stringify(data)}}
                    }});
                    window.dispatchEvent(event);
                }},
                function(error) {{
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
            statusDiv.innerHTML = '❌ GPS non supporté par ce navigateur';
            statusDiv.style.color = '#f44336';
        }}
    }}
    </script>
    """

def get_gps_action_js(button_id, action_name, button_text):
    """Génère le JavaScript pour une action avec GPS automatique"""
    return f"""
    <div id="gps_status_{button_id}" style="margin-bottom: 5px; font-size: 12px; text-align: center; color: #666;"></div>
    <button onclick="getPositionAndAction_{button_id}()" style="background-color: #2196F3; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%; cursor: pointer; font-size: 16px; font-weight: bold;">
        {button_text}
    </button>
    <script>
    function getPositionAndAction_{button_id}() {{
        var statusDiv = document.getElementById('gps_status_{button_id}');
        statusDiv.innerHTML = '📍 Recherche GPS en cours...';
        statusDiv.style.color = '#ff9800';
        
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    var lat = position.coords.latitude;
                    var lon = position.coords.longitude;
                    statusDiv.innerHTML = '✅ Position trouvée ! Enregistrement...';
                    statusDiv.style.color = '#4CAF50';
                    
                    const data = {{action: '{action_name}', lat: lat, lon: lon}};
                    const event = new CustomEvent('streamlit:setComponentValue', {{
                        detail: {{value: JSON.stringify(data)}}
                    }});
                    window.dispatchEvent(event);
                }},
                function(error) {{
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
            statusDiv.innerHTML = '❌ GPS non supporté';
            statusDiv.style.color = '#f44336';
        }}
    }}
    </script>
    """

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
    .info-card {
        background-color: #e3f2fd;
        padding: 0.5rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== INITIALISATION SESSION ====================
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
if 'derniere_action' not in st.session_state:
    st.session_state.derniere_action = None

# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("### 🗑️ Commune de Mékhé")
    st.markdown("---")
    
    mode = st.radio("🔐 Mode", ["🧑‍🌾 Agent de terrain", "📊 Responsable / Dashboard"])
    
    if mode == "🧑‍🌾 Agent de terrain":
        st.session_state.role = "agent"
        st.markdown("---")
        st.session_state.agent_nom = st.text_input("✍️ Votre nom", placeholder="Ex: Alioune Diop")
        
        st.markdown("---")
        st.markdown("### 📍 Informations de la tournée")
        
        st.session_state.quartier = st.selectbox("📍 Quartier", 
            ["HLM", "NDIOP", "LEBOU EST", "NGAYE DIAGNE", "MAMBARA", "NGAYE DJITTE", "LEBOU OUEST"])
        
        st.session_state.equipe = st.selectbox("👥 Équipe", 
            ["Équipe A", "Équipe B", "Équipe C", "Équipe D"])
        
        st.session_state.type_tracteur = st.selectbox("🚜 Type de tracteur", 
            ["TAFE", "New Holland", "Massey Ferguson", "John Deere", "Autre"])
        
        st.session_state.numero_parc = st.text_input("🔢 Numéro de parc", placeholder="Ex: TR-001")
    else:
        st.session_state.role = "dashboard"
    
    st.markdown("---")
    st.caption("📍 GPS automatique à chaque clic")

# Récepteur des actions GPS
gps_receiver = st.text_input("", key="gps_receiver", label_visibility="collapsed", placeholder="")

if gps_receiver:
    try:
        data = json.loads(gps_receiver)
        action = data.get("action")
        lat = data.get("lat")
        lon = data.get("lon")
        
        if action == "depart":
            st.session_state.horaires["depart"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.points.append({
                "type": "depart",
                "titre": "🏭 Départ du dépôt",
                "heure": st.session_state.horaires["depart"],
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ Départ enregistré à {st.session_state.horaires['depart']}")
            st.balloons()
            
        elif action == "collecte1":
            st.session_state.horaires["debut_collecte1"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.points.append({
                "type": "debut_collecte1",
                "titre": "🗑️ Début collecte 1",
                "heure": st.session_state.horaires["debut_collecte1"],
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ Début collecte 1 à {st.session_state.horaires['debut_collecte1']}")
            
        elif action == "decharge":
            st.session_state.horaires["decharge"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.points.append({
                "type": "decharge",
                "titre": "🚛 Vidage à la décharge",
                "heure": st.session_state.horaires["decharge"],
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ Vidage à {st.session_state.horaires['decharge']}")
            
        elif action == "collecte2":
            st.session_state.horaires["debut_collecte2"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.points.append({
                "type": "debut_collecte2",
                "titre": "🗑️ Début collecte 2",
                "heure": st.session_state.horaires["debut_collecte2"],
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ Début collecte 2 à {st.session_state.horaires['debut_collecte2']}")
            
        elif action == "decharge2":
            st.session_state.horaires["decharge2"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.points.append({
                "type": "decharge2",
                "titre": "🚛 Second vidage",
                "heure": st.session_state.horaires["decharge2"],
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ Second vidage à {st.session_state.horaires['decharge2']}")
            
        elif action == "retour":
            st.session_state.horaires["retour"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.points.append({
                "type": "retour",
                "titre": "🏁 Retour au dépôt",
                "heure": st.session_state.horaires["retour"],
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ Retour enregistré à {st.session_state.horaires['retour']}")
            
        st.rerun()
    except:
        pass

# ==================== MODE AGENT ====================
if st.session_state.role == "agent":
    
    st.markdown("""
    <div class="main-header">
        <h1>🗑️ Agent de Collecte - Mékhé</h1>
        <p>Cliquez directement sur les boutons - Le GPS se déclenche automatiquement</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.agent_nom:
        st.warning("⚠️ Veuillez entrer votre nom dans la barre latérale")
        st.stop()
    
    st.success(f"✅ Agent connecté : {st.session_state.agent_nom}")
    
    # Récapitulatif des infos
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"📍 Quartier: **{st.session_state.quartier}**")
    with col2:
        st.info(f"👥 Équipe: **{st.session_state.equipe}**")
    with col3:
        st.info(f"🚜 Tracteur: **{st.session_state.type_tracteur}** {st.session_state.numero_parc}")
    
    st.markdown("---")
    
    # ==================== BOUTONS AVEC GPS AUTOMATIQUE ====================
    st.markdown("### 🎤 Cliquez sur les boutons (GPS automatique)")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.components.v1.html(get_gps_action_js("btn_depart", "depart", "🚀 DÉPART\nDEMM"), height=100)
    
    with col2:
        st.components.v1.html(get_gps_action_js("btn_collecte1", "collecte1", "🗑️ DÉBUT\nCOLLECTE 1"), height=100)
    
    with col3:
        if st.button("🏁 FIN COLLECTE 1", use_container_width=True):
            st.session_state.horaires["fin_collecte1"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.collecte1_terminee = True
            st.success(f"✅ Fin collecte 1 à {st.session_state.horaires['fin_collecte1']}")
    
    with col4:
        st.components.v1.html(get_gps_action_js("btn_decharge", "decharge", "🚛 VIDAGE\nDÉCHARGE"), height=100)
    
    with col5:
        st.components.v1.html(get_gps_action_js("btn_retour", "retour", "🏁 RETOUR\nFANAN"), height=100)
    
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
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.components.v1.html(get_gps_action_js("btn_collecte2", "collecte2", "🗑️ DÉBUT\nCOLLECTE 2"), height=100)
        
        with col2:
            if st.button("🏁 FIN COLLECTE 2", use_container_width=True):
                st.session_state.horaires["fin_collecte2"] = datetime.now().strftime("%H:%M:%S")
                st.success(f"✅ Fin collecte 2 à {st.session_state.horaires['fin_collecte2']}")
        
        with col3:
            st.components.v1.html(get_gps_action_js("btn_decharge2", "decharge2", "🚛 SECOND\nVIDAGE"), height=100)
        
        v2 = st.number_input("📦 Volume collecte 2 (m³)", 0.0, 20.0, st.session_state.volumes["collecte2"], 0.5, key="vol2")
        if v2 != st.session_state.volumes["collecte2"]:
            st.session_state.volumes["collecte2"] = v2
        
        st.markdown("---")
    
    # ==================== RÉCAPITULATIF ====================
    with st.expander("📋 Voir le récapitulatif de la tournée"):
        if st.session_state.horaires:
            st.markdown("**Horaires enregistrés :**")
            for key, value in st.session_state.horaires.items():
                st.write(f"- {key}: {value}")
        
        if st.session_state.points:
            st.markdown("**Points GPS enregistrés :**")
            for p in st.session_state.points:
                st.write(f"- {p['titre']} à {p['heure']} → ({p['lat']:.6f}, {p['lon']:.6f})")
    
    # ==================== CARTE ====================
    if st.session_state.points:
        points_valides = [p for p in st.session_state.points if p.get("lat")]
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
                📍 **Quartier :** {st.session_state.quartier}
                👥 **Équipe :** {st.session_state.equipe}
                🚜 **Tracteur :** {st.session_state.type_tracteur} {st.session_state.numero_parc}
                📦 **Volume total :** {total_volume} m³
                📍 **Points GPS :** {len(st.session_state.points)}
                """)
                
                if engine:
                    try:
                        with engine.connect() as conn:
                            # S'assurer que les colonnes acceptent NULL
                            try:
                                conn.execute(text("ALTER TABLE tournees ALTER COLUMN quartier_id DROP NOT NULL;"))
                                conn.execute(text("ALTER TABLE tournees ALTER COLUMN equipe_id DROP NOT NULL;"))
                                conn.commit()
                            except:
                                pass
                            
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
                            st.success("✅ Données enregistrées dans Neon.tech !")
                    except Exception as e:
                        st.warning(f"⚠️ Base: {e}")
                
                if st.button("🔄 NOUVELLE TOURNÉE", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key not in ['agent_nom', 'role', 'quartier', 'equipe', 'type_tracteur', 'numero_parc']:
                            if key != 'derniere_action':
                                st.session_state[key] = {} if key in ['points', 'horaires', 'volumes'] else False if key in ['collecte2_active', 'collecte1_terminee'] else 0.0 if key in ['volumes'] else None
                    st.session_state.points = []
                    st.session_state.horaires = {}
                    st.session_state.volumes = {"collecte1": 0.0, "collecte2": 0.0}
                    st.session_state.collecte2_active = False
                    st.session_state.collecte1_terminee = False
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
        else:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📋 Collectes", len(df_tournees))
            with col2:
                st.metric("📦 Volume total", f"{df_tournees['volume_total'].sum():.1f} m³")
            with col3:
                st.metric("📍 Points GPS", len(df_points))
            with col4:
                st.metric("👤 Dernier agent", df_tournees.iloc[0]["agent_nom"])
            
            st.markdown("---")
            
            if not df_points.empty:
                st.subheader("🗺️ Carte des points GPS")
                points_map = df_points.dropna(subset=["latitude", "longitude"])
                if not points_map.empty:
                    m = folium.Map(location=[points_map["latitude"].mean(), points_map["longitude"].mean()], zoom_start=13)
                    for _, p in points_map.iterrows():
                        folium.Marker([p["latitude"], p["longitude"]], popup=f"{p['type_point']}<br>{p['heure']}", icon=folium.Icon(color="blue")).add_to(m)
                    folium_static(m, width=800, height=400)
            
            st.subheader("📋 Liste des collectes")
            st.dataframe(df_tournees[["date_tournee", "agent_nom", "volume_total", "heure_depot_depart", "heure_retour_depot"]], use_container_width=True)
            
            if st.button("📥 EXPORTER EN EXCEL"):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_tournees.to_excel(writer, sheet_name="Collectes", index=False)
                    if not df_points.empty:
                        df_points.to_excel(writer, sheet_name="Points GPS", index=False)
                st.download_button("📥 Télécharger", output.getvalue(), f"dashboard_mekhe_{date.today()}.xlsx")
    except Exception as e:
        st.info(f"📭 Base en attente: {e}")

# ==================== CONSIGNES SÉCURITÉ ====================
with st.expander("🛡️ Consignes de sécurité / Làppu sécurité"):
    st.markdown("""
    1. **Gestes et postures / Baal sa bànqaas** : Pliez les jambes pour soulever
    2. **Protection / Jar gi ak noppal** : Portez gants et masque
    3. **Ne montez pas sur le tracteur / Bul wàcc ci tracteur bu ngi faj**
    4. **Éloignez-vous lors du vidage / Bul def ci diggante bu yendu remorque**
    5. **Circulation / Bul koom ci ndaw** : Ne restez pas au milieu de la route
    """)

st.caption(f"📍 GPS automatique | {'Agent: ' + st.session_state.agent_nom if st.session_state.role == 'agent' else 'Dashboard'} | 🗑️ Commune de Mékhé")
