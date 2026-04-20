"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version complète avec :
- Interface Agent (boutons simples)
- GPS automatique (un clic sur "Ma position")
- Dashboard Responsable
- Base de données Neon.tech
- Conforme aux préconisations PDF
"""

import streamlit as st
import pandas as pd
import requests
from datetime import date, datetime, time
from sqlalchemy import create_engine, text
import folium
from streamlit_folium import folium_static
import plotly.express as px
from io import BytesIO

# ==================== CONFIGURATION PAGE ====================
st.set_page_config(
    page_title="Collecte Déchets - Mékhé",
    page_icon="🗑️",
    layout="wide"
)

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
        st.error(f"❌ Base de données non accessible: {e}")
        return None

engine = init_connection()

# ==================== INITIALISATION SESSION STATE ====================
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'role' not in st.session_state:
    st.session_state.role = "agent"
if 'collecte_active' not in st.session_state:
    st.session_state.collecte_active = False

# Données de la collecte en cours
if 'points' not in st.session_state:
    st.session_state.points = []           # Liste des points GPS
if 'horaires' not in st.session_state:
    st.session_state.horaires = {}         # Dictionnaire des horaires
if 'volumes' not in st.session_state:
    st.session_state.volumes = {"collecte1": 0.0, "collecte2": 0.0}
if 'collecte2_active' not in st.session_state:
    st.session_state.collecte2_active = False
if 'position_actuelle' not in st.session_state:
    st.session_state.position_actuelle = {"lat": 15.121048, "lon": -16.686826}
if 'collecte1_terminee' not in st.session_state:
    st.session_state.collecte1_terminee = False

# ==================== FONCTIONS ====================
def get_gps_automatique():
    """Récupère la position GPS via l'API ipapi.co"""
    try:
        response = requests.get('https://ipapi.co/json/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            lat = data.get('latitude')
            lon = data.get('longitude')
            if lat and lon:
                return {"lat": lat, "lon": lon}
    except:
        pass
    return {"lat": 15.121048, "lon": -16.686826}  # Position par défaut (Mékhé)

def ajouter_point(type_point, titre):
    """Ajoute un point avec la position actuelle"""
    st.session_state.points.append({
        "type": type_point,
        "titre": titre,
        "heure": datetime.now().strftime("%H:%M:%S"),
        "lat": st.session_state.position_actuelle["lat"],
        "lon": st.session_state.position_actuelle["lon"]
    })

def get_quartiers():
    return ["HLM", "NDIOP", "LEBOU EST", "NGAYE DIAGNE", "MAMBARA", "NGAYE DJITTE", "LEBOU OUEST"]

def get_equipes():
    return ["Équipe A", "Équipe B", "Équipe C", "Équipe D"]

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
    .big-btn {
        font-size: 18px !important;
        font-weight: bold !important;
        padding: 15px !important;
    }
    .gps-card {
        background-color: #e3f2fd;
        padding: 0.8rem;
        border-radius: 10px;
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
    .success-card {
        background-color: #e8f5e9;
        padding: 0.5rem;
        border-radius: 10px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== SIDEBAR ====================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2948/2948212.png", width=50)
    st.markdown("### 🗑️ Commune de Mékhé")
    
    # Choix du mode
    st.markdown("---")
    mode = st.radio("🔐 Mode", ["🧑‍🌾 Agent de terrain", "📊 Responsable / Dashboard"])
    
    if mode == "🧑‍🌾 Agent de terrain":
        st.session_state.role = "agent"
        st.markdown("---")
        st.session_state.agent_nom = st.text_input("✍️ Votre nom", placeholder="Ex: Alioune Diop")
    else:
        st.session_state.role = "dashboard"
    
    st.markdown("---")
    st.caption("🔋 Version 2.0 | GPS automatique")

# ==================== MODE AGENT ====================
if st.session_state.role == "agent":
    
    # En-tête
    st.markdown("""
    <div class="main-header">
        <h1>🗑️ Agent de Collecte - Mékhé</h1>
        <p>Cliquez sur les boutons dans l'ordre | Wax sa réew mi</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Vérification du nom
    if not st.session_state.agent_nom:
        st.warning("⚠️ Veuillez entrer votre nom dans la barre latérale")
        st.stop()
    
    st.success(f"✅ Agent connecté : {st.session_state.agent_nom}")
    
    # ==================== GPS AUTOMATIQUE ====================
    st.markdown("### 📍 Position GPS")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📍 MA POSITION", type="primary", use_container_width=True):
            with st.spinner("🔍 Récupération de votre position..."):
                nouvelle_position = get_gps_automatique()
                st.session_state.position_actuelle = nouvelle_position
                st.success(f"✅ Position enregistrée : {st.session_state.position_actuelle['lat']:.6f}, {st.session_state.position_actuelle['lon']:.6f}")
    
    st.markdown(f"""
    <div class="gps-card">
        🗺️ Position actuelle :<br>
        <b>Latitude : {st.session_state.position_actuelle['lat']:.6f}</b><br>
        <b>Longitude : {st.session_state.position_actuelle['lon']:.6f}</b>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ==================== BOUTONS DE COLLECTE ====================
    st.markdown("### 🎤 Enregistrement de la tournée")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("🚀 DÉPART\nDEMM", use_container_width=True, type="primary"):
            st.session_state.horaires["depart"] = datetime.now().strftime("%H:%M:%S")
            ajouter_point("depart", "🏭 Départ du dépôt")
            st.success(f"✅ Départ à {st.session_state.horaires['depart']}")
            st.balloons()
    
    with col2:
        if st.button("🗑️ DÉBUT\nCOLLECTE 1", use_container_width=True):
            st.session_state.horaires["debut_collecte1"] = datetime.now().strftime("%H:%M:%S")
            ajouter_point("debut_collecte1", "🗑️ Début collecte 1")
            st.success(f"✅ Début collecte 1 à {st.session_state.horaires['debut_collecte1']}")
    
    with col3:
        if st.button("🏁 FIN\nCOLLECTE 1", use_container_width=True):
            st.session_state.horaires["fin_collecte1"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.collecte1_terminee = True
            st.success(f"✅ Fin collecte 1 à {st.session_state.horaires['fin_collecte1']}")
    
    with col4:
        if st.button("🚛 VIDAGE\nDÉCHARGE", use_container_width=True):
            st.session_state.horaires["decharge"] = datetime.now().strftime("%H:%M:%S")
            ajouter_point("decharge", "🚛 Vidage à la décharge")
            st.success(f"✅ Vidage à {st.session_state.horaires['decharge']}")
    
    with col5:
        if st.button("🏁 RETOUR\nFANAN", use_container_width=True):
            st.session_state.horaires["retour"] = datetime.now().strftime("%H:%M:%S")
            ajouter_point("retour", "🏁 Retour au dépôt")
            st.success(f"✅ Retour à {st.session_state.horaires['retour']}")
    
    st.markdown("---")
    
    # ==================== COLLECTE 2 (OPTIONNELLE) ====================
    if st.session_state.collecte1_terminee and not st.session_state.collecte2_active:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ ACTIVER COLLECTE 2", use_container_width=True):
                st.session_state.collecte2_active = True
                st.success("✅ Collecte 2 activée")
        with col2:
            if st.button("⏭️ PASSER COLLECTE 2", use_container_width=True):
                st.session_state.collecte2_active = True  # Pour valider la fin
                st.info("Collecte 2 ignorée")
    
    if st.session_state.collecte2_active and "fin_collecte2" not in st.session_state.horaires:
        st.markdown("#### 🚛 COLLECTE 2")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🗑️ DÉBUT COLLECTE 2", use_container_width=True):
                st.session_state.horaires["debut_collecte2"] = datetime.now().strftime("%H:%M:%S")
                ajouter_point("debut_collecte2", "🗑️ Début collecte 2")
                st.success(f"✅ Début collecte 2 à {st.session_state.horaires['debut_collecte2']}")
        
        with col2:
            if st.button("🏁 FIN COLLECTE 2", use_container_width=True):
                st.session_state.horaires["fin_collecte2"] = datetime.now().strftime("%H:%M:%S")
                st.success(f"✅ Fin collecte 2 à {st.session_state.horaires['fin_collecte2']}")
        
        with col3:
            if st.button("🚛 VIDAGE 2", use_container_width=True):
                st.session_state.horaires["decharge2"] = datetime.now().strftime("%H:%M:%S")
                ajouter_point("decharge2", "🚛 Second vidage")
                st.success(f"✅ Second vidage à {st.session_state.horaires['decharge2']}")
    
    st.markdown("---")
    
    # ==================== VOLUMES ====================
    st.markdown("### 📦 Volumes collectés")
    
    col1, col2 = st.columns(2)
    with col1:
        v1 = st.number_input("Volume collecte 1 (m³)", 0.0, 20.0, st.session_state.volumes["collecte1"], 0.5)
        if v1 != st.session_state.volumes["collecte1"]:
            st.session_state.volumes["collecte1"] = v1
        # Taux de remplissage
        taux = (v1 / 10) * 100
        st.progress(min(taux/100, 1.0))
        st.caption(f"📊 Taux de remplissage : {taux:.0f}% (remorque 10m³)")
    
    with col2:
        if "fin_collecte2" in st.session_state.horaires or st.session_state.collecte2_active:
            v2 = st.number_input("Volume collecte 2 (m³)", 0.0, 20.0, st.session_state.volumes["collecte2"], 0.5)
            if v2 != st.session_state.volumes["collecte2"]:
                st.session_state.volumes["collecte2"] = v2
    
    st.markdown("---")
    
    # ==================== RÉCAPITULATIF AVANT ENREGISTREMENT ====================
    with st.expander("📋 Voir le récapitulatif de la tournée"):
        st.markdown("**Horaires enregistrés :**")
        for key, value in st.session_state.horaires.items():
            st.write(f"- {key}: {value}")
        
        st.markdown("**Points GPS enregistrés :**")
        for p in st.session_state.points:
            st.write(f"- {p['titre']} à {p['heure']} → ({p['lat']:.6f}, {p['lon']:.6f})")
        
        st.markdown(f"**Volumes :** Collecte 1 = {st.session_state.volumes['collecte1']} m³, Collecte 2 = {st.session_state.volumes['collecte2']} m³")
        st.markdown(f"**Total :** {st.session_state.volumes['collecte1'] + st.session_state.volumes['collecte2']} m³")
    
    # ==================== TERMINER ====================
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
                ✅ TOURNÉE TERMINÉE AVEC SUCCÈS !
                
                📊 **Récapitulatif final**
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                👤 Agent : {st.session_state.agent_nom}
                📦 Volume total : {total_volume} m³
                🚛 Nombre de vidages : {len([p for p in st.session_state.points if 'decharge' in p['type']])}
                📍 Points GPS : {len(st.session_state.points)}
                🕐 Départ : {st.session_state.horaires.get('depart', 'N/A')}
                🕐 Retour : {st.session_state.horaires.get('retour', 'N/A')}
                """)
                
                # Enregistrement dans la base Neon.tech
                if engine:
                    try:
                        with engine.connect() as conn:
                            # 1. Insérer dans tournees
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
                            
                            # 2. Insérer les points GPS
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
                
                # Réinitialisation pour une nouvelle tournée
                if st.button("🔄 NOUVELLE TOURNÉE"):
                    st.session_state.points = []
                    st.session_state.horaires = {}
                    st.session_state.volumes = {"collecte1": 0.0, "collecte2": 0.0}
                    st.session_state.collecte2_active = False
                    st.session_state.collecte1_terminee = False
                    st.rerun()
    
    # ==================== CARTE DES POINTS ====================
    if st.session_state.points:
        st.markdown("---")
        st.markdown("### 🗺️ Carte des points enregistrés")
        
        points_valides = [p for p in st.session_state.points if p["lat"] and p["lon"]]
        if points_valides:
            m = folium.Map(location=[points_valides[0]["lat"], points_valides[0]["lon"]], zoom_start=14)
            
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
            
            # Tracer le trajet
            if len(points_valides) > 1:
                coords = [[p["lat"], p["lon"]] for p in points_valides]
                folium.PolyLine(coords, color="blue", weight=3, opacity=0.7).add_to(m)
            
            folium_static(m, width=800, height=400)

# ==================== MODE DASHBOARD ====================
else:
    st.markdown("""
    <div class="main-header">
        <h1>📊 Tableau de bord - Collecte des déchets</h1>
        <p>Commune de Mékhé | Suivi des performances</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not engine:
        st.error("❌ Base de données non accessible")
        st.stop()
    
    # Chargement des données
    try:
        df_tournees = pd.read_sql("""
            SELECT * FROM tournees 
            ORDER BY date_tournee DESC 
            LIMIT 100
        """, engine)
        
        df_points = pd.read_sql("""
            SELECT * FROM points_arret 
            ORDER BY id DESC 
            LIMIT 500
        """, engine)
    except Exception as e:
        st.info("📭 Aucune donnée pour le moment")
        df_tournees = pd.DataFrame()
        df_points = pd.DataFrame()
    
    if df_tournees.empty:
        st.info("📭 Aucune collecte enregistrée pour le moment")
        st.stop()
    
    # ==================== KPI ====================
    st.markdown("### 📊 Indicateurs clés")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        nb_collectes = len(df_tournees)
        st.metric("📋 Nombre de collectes", nb_collectes)
    
    with col2:
        total_volume = df_tournees["volume_collecte1"].sum() + df_tournees["volume_collecte2"].sum()
        st.metric("📦 Volume total", f"{total_volume:.1f} m³")
    
    with col3:
        nb_points = len(df_points) if not df_points.empty else 0
        st.metric("📍 Points GPS", nb_points)
    
    with col4:
        if not df_tournees.empty:
            dernier_agent = df_tournees.iloc[0]["agent_nom"]
            st.metric("👤 Dernier agent", dernier_agent)
    
    st.markdown("---")
    
    # ==================== FILTRES ====================
    col1, col2 = st.columns(2)
    with col1:
        date_min = df_tournees["date_tournee"].min()
        date_max = df_tournees["date_tournee"].max()
        date_range = st.date_input("Période", [date_min, date_max])
    
    with col2:
        agents = ["Tous"] + list(df_tournees["agent_nom"].unique())
        agent_filter = st.selectbox("Agent", agents)
    
    # Application des filtres
    df_filtered = df_tournees.copy()
    if len(date_range) == 2:
        df_filtered = df_filtered[(df_filtered["date_tournee"] >= pd.to_datetime(date_range[0])) & 
                                   (df_filtered["date_tournee"] <= pd.to_datetime(date_range[1]))]
    if agent_filter != "Tous":
        df_filtered = df_filtered[df_filtered["agent_nom"] == agent_filter]
    
    # ==================== GRAPHIQUES ====================
    col1, col2 = st.columns(2)
    
    with col1:
        # Volume par jour
        daily_volume = df_filtered.groupby("date_tournee")[["volume_collecte1", "volume_collecte2"]].sum().reset_index()
        fig = px.bar(daily_volume, x="date_tournee", y=["volume_collecte1", "volume_collecte2"],
                      title="Volume collecté par jour",
                      labels={"value": "Volume (m³)", "variable": "Collecte"},
                      color_discrete_map={"volume_collecte1": "#4CAF50", "volume_collecte2": "#FF9800"})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Volume par agent
        agent_volume = df_filtered.groupby("agent_nom")[["volume_collecte1", "volume_collecte2"]].sum().reset_index()
        fig2 = px.bar(agent_volume, x="agent_nom", y="volume_collecte1",
                       title="Volume par agent",
                       labels={"volume_collecte1": "Volume (m³)"},
                       color_discrete_sequence=["#4CAF50"])
        st.plotly_chart(fig2, use_container_width=True)
    
    # ==================== CARTE DES POINTS ====================
    if not df_points.empty and "latitude" in df_points.columns:
        points_map = df_points.dropna(subset=["latitude", "longitude"])
        if not points_map.empty:
            st.markdown("### 🗺️ Carte des points GPS")
            
            m = folium.Map(location=[points_map["latitude"].mean(), points_map["longitude"].mean()], zoom_start=13)
            
            for _, p in points_map.iterrows():
                folium.Marker(
                    [p["latitude"], p["longitude"]],
                    popup=f"{p['type_point']}<br>Tournée #{p['tournee_id']}",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)
            
            folium_static(m, width=800, height=400)
    
    # ==================== TABLEAU DES COLLECTES ====================
    st.markdown("### 📋 Détail des collectes")
    
    columns_to_show = ["date_tournee", "agent_nom", "volume_collecte1", "volume_collecte2", "heure_depot_depart", "heure_retour_depot", "statut"]
    available_cols = [col for col in columns_to_show if col in df_filtered.columns]
    st.dataframe(df_filtered[available_cols], use_container_width=True)
    
    # ==================== EXPORT ====================
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📥 EXPORTER EN EXCEL", type="primary", use_container_width=True):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_filtered.to_excel(writer, sheet_name="Collectes", index=False)
                if not df_points.empty:
                    df_points.to_excel(writer, sheet_name="Points GPS", index=False)
            
            st.download_button(
                "📥 Télécharger",
                output.getvalue(),
                f"dashboard_mekhe_{date.today()}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

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
st.caption(f"🗑️ Commune de Mékhé | {'Agent: ' + st.session_state.agent_nom if st.session_state.role == 'agent' else 'Tableau de bord'} | 📍 GPS automatique")
