"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec GPS réel à chaque action
- Chaque bouton obtient sa propre position GPS
- Les positions changent selon où se trouve l'agent
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
    .gps-status {
        font-size: 11px;
        text-align: center;
        margin-top: 5px;
        color: #666;
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

# Stockage temporaire pour la dernière position GPS reçue
if 'derniere_position' not in st.session_state:
    st.session_state.derniere_position = {"lat": 15.121048, "lon": -16.686826}

# ==================== FONCTION GPS POUR CHAQUE ACTION ====================
def get_gps_button(action_name, button_text, button_color="#4CAF50"):
    """Génère un bouton avec GPS automatique qui obtient la position en temps réel"""
    return f"""
    <div id="gps_status_{action_name}" class="gps-status">📍 En attente...</div>
    <button onclick="getPositionAndSend('{action_name}')" style="background-color: {button_color}; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%; cursor: pointer; font-size: 16px; font-weight: bold;">
        {button_text}
    </button>
    <script>
    function getPositionAndSend(actionName) {{
        var statusDiv = document.getElementById('gps_status_' + actionName);
        statusDiv.innerHTML = '🔍 Recherche GPS en cours...';
        statusDiv.style.color = '#ff9800';
        
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    var lat = position.coords.latitude;
                    var lon = position.coords.longitude;
                    statusDiv.innerHTML = '✅ Position: ' + lat.toFixed(6) + ', ' + lon.toFixed(6);
                    statusDiv.style.color = '#4CAF50';
                    
                    var data = JSON.stringify({{action: actionName, lat: lat, lon: lon}});
                    var input = document.getElementById('gps_receiver');
                    if (input) {{
                        input.value = data;
                        input.dispatchEvent(new Event('input', {{bubbles: true}}));
                    }}
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

# Champ caché pour recevoir les données GPS
gps_receiver = st.text_input("", key="gps_receiver", label_visibility="collapsed", placeholder="")

if gps_receiver:
    try:
        data = json.loads(gps_receiver)
        action = data.get("action")
        lat = data.get("lat")
        lon = data.get("lon")
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # Traiter selon l'action
        if action == "depart":
            st.session_state.horaires["depart"] = current_time
            st.session_state.points.append({
                "type": "depart",
                "titre": "🏭 Départ du dépôt",
                "heure": current_time,
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ DÉPART enregistré à {current_time} - Position: {lat:.6f}, {lon:.6f}")
            st.balloons()
            
        elif action == "debut_collecte1":
            st.session_state.horaires["debut_collecte1"] = current_time
            st.session_state.points.append({
                "type": "debut_collecte1",
                "titre": "🗑️ Début collecte 1",
                "heure": current_time,
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ DÉBUT COLLECTE 1 à {current_time} - Position: {lat:.6f}, {lon:.6f}")
            
        elif action == "fin_collecte1":
            st.session_state.horaires["fin_collecte1"] = current_time
            st.session_state.collecte1_terminee = True
            st.session_state.points.append({
                "type": "fin_collecte1",
                "titre": "🏁 Fin collecte 1",
                "heure": current_time,
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ FIN COLLECTE 1 à {current_time} - Position: {lat:.6f}, {lon:.6f}")
            
        elif action == "decharge1":
            st.session_state.horaires["decharge1"] = current_time
            st.session_state.points.append({
                "type": "decharge1",
                "titre": "🚛 Vidage décharge 1",
                "heure": current_time,
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ VIDAGE DÉCHARGE 1 à {current_time} - Position: {lat:.6f}, {lon:.6f}")
            
        elif action == "debut_collecte2":
            st.session_state.horaires["debut_collecte2"] = current_time
            st.session_state.points.append({
                "type": "debut_collecte2",
                "titre": "🗑️ Début collecte 2",
                "heure": current_time,
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ DÉBUT COLLECTE 2 à {current_time} - Position: {lat:.6f}, {lon:.6f}")
            
        elif action == "fin_collecte2":
            st.session_state.horaires["fin_collecte2"] = current_time
            st.session_state.points.append({
                "type": "fin_collecte2",
                "titre": "🏁 Fin collecte 2",
                "heure": current_time,
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ FIN COLLECTE 2 à {current_time} - Position: {lat:.6f}, {lon:.6f}")
            
        elif action == "decharge2":
            st.session_state.horaires["decharge2"] = current_time
            st.session_state.points.append({
                "type": "decharge2",
                "titre": "🚛 Vidage décharge 2",
                "heure": current_time,
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ SECOND VIDAGE à {current_time} - Position: {lat:.6f}, {lon:.6f}")
            
        elif action == "retour":
            st.session_state.horaires["retour"] = current_time
            st.session_state.points.append({
                "type": "retour",
                "titre": "🏁 Retour au dépôt",
                "heure": current_time,
                "lat": lat,
                "lon": lon
            })
            st.success(f"✅ RETOUR enregistré à {current_time} - Position: {lat:.6f}, {lon:.6f}")
        
        st.rerun()
    except:
        pass

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
        st.markdown("### 📍 Informations tournée")
        st.session_state.quartier = st.selectbox("Quartier", ["HLM", "NDIOP", "LEBOU EST", "NGAYE DIAGNE", "MAMBARA", "NGAYE DJITTE", "LEBOU OUEST"])
        st.session_state.equipe = st.selectbox("Équipe", ["Équipe A", "Équipe B", "Équipe C", "Équipe D"])
        st.session_state.type_tracteur = st.selectbox("Type tracteur", ["TAFE", "New Holland", "Massey Ferguson", "John Deere"])
        st.session_state.numero_parc = st.text_input("N° Parc", placeholder="Ex: TR-001")
    else:
        st.session_state.role = "dashboard"
    
    st.markdown("---")
    st.caption("📍 Chaque bouton obtient sa propre position GPS")

# ==================== MODE AGENT ====================
if st.session_state.role == "agent":
    
    st.markdown("""
    <div class="main-header">
        <h1>🗑️ Agent de Collecte - Mékhé</h1>
        <p>Cliquez sur les boutons - Le GPS se déclenche automatiquement à chaque fois</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.agent_nom:
        st.warning("⚠️ Veuillez entrer votre nom dans la barre latérale")
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
    
    # ==================== BOUTONS DE COLLECTE ====================
    st.markdown("### 🎤 Enregistrement de la tournée")
    st.info("💡 **Chaque clic obtient une nouvelle position GPS** (là où vous vous trouvez à ce moment)")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(get_gps_button("depart", "🚀 DÉPART / DEMM", "#4CAF50"), unsafe_allow_html=True)
    
    with col2:
        st.markdown(get_gps_button("debut_collecte1", "🗑️ DÉBUT\nCOLLECTE 1", "#2196F3"), unsafe_allow_html=True)
    
    with col3:
        st.markdown(get_gps_button("fin_collecte1", "🏁 FIN\nCOLLECTE 1", "#FF9800"), unsafe_allow_html=True)
    
    with col4:
        st.markdown(get_gps_button("decharge1", "🚛 VIDAGE\nDÉCHARGE 1", "#f44336"), unsafe_allow_html=True)
    
    with col5:
        st.markdown(get_gps_button("retour", "🏁 RETOUR\nFANAN", "#9C27B0"), unsafe_allow_html=True)
    
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
            st.markdown(get_gps_button("debut_collecte2", "🗑️ DÉBUT\nCOLLECTE 2", "#2196F3"), unsafe_allow_html=True)
        
        with col2:
            st.markdown(get_gps_button("fin_collecte2", "🏁 FIN\nCOLLECTE 2", "#FF9800"), unsafe_allow_html=True)
        
        with col3:
            st.markdown(get_gps_button("decharge2", "🚛 SECOND\nVIDAGE", "#f44336"), unsafe_allow_html=True)
        
        v2 = st.number_input("📦 Volume collecte 2 (m³)", 0.0, 20.0, st.session_state.volumes["collecte2"], 0.5, key="vol2")
        if v2 != st.session_state.volumes["collecte2"]:
            st.session_state.volumes["collecte2"] = v2
    
    st.markdown("---")
    
    # ==================== RÉCAPITULATIF DES HEURES ====================
    st.markdown("### 📋 Récapitulatif des horaires")
    
    horaire_data = []
    if st.session_state.horaires.get("depart"):
        horaire_data.append(["🚀 DÉPART", st.session_state.horaires["depart"]])
    if st.session_state.horaires.get("debut_collecte1"):
        horaire_data.append(["🗑️ DÉBUT COLLECTE 1", st.session_state.horaires["debut_collecte1"]])
    if st.session_state.horaires.get("fin_collecte1"):
        horaire_data.append(["🏁 FIN COLLECTE 1", st.session_state.horaires["fin_collecte1"]])
    if st.session_state.horaires.get("decharge1"):
        horaire_data.append(["🚛 VIDAGE DÉCHARGE 1", st.session_state.horaires["decharge1"]])
    if st.session_state.horaires.get("debut_collecte2"):
        horaire_data.append(["🗑️ DÉBUT COLLECTE 2", st.session_state.horaires["debut_collecte2"]])
    if st.session_state.horaires.get("fin_collecte2"):
        horaire_data.append(["🏁 FIN COLLECTE 2", st.session_state.horaires["fin_collecte2"]])
    if st.session_state.horaires.get("decharge2"):
        horaire_data.append(["🚛 VIDAGE DÉCHARGE 2", st.session_state.horaires["decharge2"]])
    if st.session_state.horaires.get("retour"):
        horaire_data.append(["🏁 RETOUR", st.session_state.horaires["retour"]])
    
    if horaire_data:
        df_horaires = pd.DataFrame(horaire_data, columns=["Étape", "Heure"])
        st.dataframe(df_horaires, use_container_width=True)
    else:
        st.info("Aucun horaire enregistré pour le moment")
    
    # ==================== POINTS GPS ====================
    if st.session_state.points:
        st.markdown("### 📍 Points GPS enregistrés")
        points_df = pd.DataFrame([(p["titre"], p["heure"], p["lat"], p["lon"]) for p in st.session_state.points], 
                                  columns=["Action", "Heure", "Latitude", "Longitude"])
        st.dataframe(points_df, use_container_width=True)
    
    # ==================== CARTE ====================
    points_valides = [p for p in st.session_state.points if p.get("lat") and p.get("lon")]
    if len(points_valides) >= 1:
        st.markdown("### 🗺️ Carte des points GPS")
        
        center_lat = points_valides[0]["lat"]
        center_lon = points_valides[0]["lon"]
        m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
        
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
            distance_totale = 0
            for i in range(1, len(coords)):
                from math import radians, sin, cos, sqrt, atan2
                R = 6371
                lat1, lon1, lat2, lon2 = map(radians, [coords[i-1][0], coords[i-1][1], coords[i][0], coords[i][1]])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                distance_totale += R * c
            st.caption(f"📏 Distance totale parcourue : {distance_totale:.2f} km")
        
        folium_static(m, width=800, height=400)
    
    # ==================== TERMINER ====================
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("✅ TERMINER LA TOURNÉE", type="primary", use_container_width=True):
            # Vérifications
            if not st.session_state.horaires.get("depart"):
                st.error("❌ Veuillez enregistrer le DÉPART")
            elif st.session_state.volumes["collecte1"] == 0:
                st.error("❌ Veuillez entrer le volume de la collecte 1")
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
                📦 **Volume collecte 1 :** {st.session_state.volumes['collecte1']} m³
                📦 **Volume collecte 2 :** {st.session_state.volumes['collecte2']} m³
                📦 **Volume total :** {total_volume} m³
                📍 **Points GPS :** {len(st.session_state.points)}
                """)
                
                # Enregistrement dans la base
                if engine:
                    try:
                        with engine.connect() as conn:
                            # Supprimer les contraintes NOT NULL
                            try:
                                conn.execute(text("ALTER TABLE tournees ALTER COLUMN quartier_id DROP NOT NULL;"))
                                conn.execute(text("ALTER TABLE tournees ALTER COLUMN equipe_id DROP NOT NULL;"))
                                conn.commit()
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
                            st.success("✅ Données enregistrées dans Neon.tech !")
                    except Exception as e:
                        st.warning(f"⚠️ Base: {e}")
                
                # Réinitialisation
                if st.button("🔄 NOUVELLE TOURNÉE", use_container_width=True):
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
                    total_volume = df_tournees["volume_collecte1"].sum() + df_tournees["volume_collecte2"].sum()
                    st.metric("📦 Volume total", f"{total_volume:.1f} m³")
                with col3:
                    st.metric("📍 Points GPS", len(df_points))
                with col4:
                    st.metric("👤 Dernier agent", df_tournees.iloc[0]["agent_nom"] if not df_tournees.empty else "-")
                
                if not df_points.empty:
                    st.subheader("🗺️ Carte des points GPS")
                    points_map = df_points.dropna(subset=["latitude", "longitude"])
                    if not points_map.empty:
                        m = folium.Map(location=[points_map["latitude"].mean(), points_map["longitude"].mean()], zoom_start=13)
                        for _, p in points_map.iterrows():
                            folium.Marker([p["latitude"], p["longitude"]], popup=p["type_point"], icon=folium.Icon(color="blue")).add_to(m)
                        folium_static(m, width=800, height=400)
                
                st.subheader("📋 Liste des collectes")
                st.dataframe(df_tournees[["date_tournee", "agent_nom", "volume_collecte1", "volume_collecte2", "heure_depot_depart", "heure_retour_depot"]], use_container_width=True)
                
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
with st.expander("🛡️ Consignes de sécurité"):
    st.markdown("""
    1. **Gestes et postures** : Pliez les jambes pour soulever
    2. **Protection** : Portez gants et masque
    3. **Ne montez pas sur le tracteur**
    4. **Éloignez-vous lors du vidage**
    5. **Circulation** : Ne restez pas au milieu de la route
    """)

st.caption(f"📍 GPS temps réel - chaque action a sa propre position | {'Agent: ' + st.session_state.agent_nom if st.session_state.role == 'agent' else 'Dashboard'} | 🗑️ Commune de Mékhé")
