"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec GPS EXACT en temps réel via streamlit-js-eval
- Collecte 1 obligatoire, Collecte 2 optionnelle
- GPS haute précision (quelques mètres)
- Suivi d'itinéraire exact et calcul des distances réelles
- Quartiers selon recensement 2023
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, time, timedelta
from sqlalchemy import create_engine, text
import os
from io import BytesIO
from geopy.distance import geodesic

# Import pour le GPS exact
try:
    from streamlit_js_eval import get_geolocation
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    st.warning("⚠️ streamlit-js-eval non installé. Installez-le avec: pip install streamlit-js-eval")

# Configuration de la page
st.set_page_config(
    page_title="Agent Collecte - Mékhé",
    page_icon="🗑️",
    layout="wide"
)

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
    .collecte-card {
        background: #e8f5e9;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 4px solid #4CAF50;
    }
    .collecte2-card {
        background: #fff8e7;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 4px solid #FF9800;
    }
    .collecte2-optional {
        background: #fef7e0;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #FF9800;
        margin-bottom: 1rem;
    }
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #2196F3;
        margin: 1rem 0;
    }
    .gps-active {
        background: #4CAF50;
        color: white;
        padding: 0.5rem;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    .gps-inactive {
        background: #f44336;
        color: white;
        padding: 0.5rem;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
    }
    .gps-precision-high {
        background: #4CAF50;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        display: inline-block;
    }
    .gps-precision-medium {
        background: #FF9800;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        display: inline-block;
    }
    .gps-precision-low {
        background: #f44336;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        display: inline-block;
    }
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
    
    <script>
    // Script pour demander la permission GPS au chargement
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                console.log("✅ Permission GPS accordée");
            },
            (error) => {
                console.log("❌ Permission GPS refusée:", error.message);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    }
    </script>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte - Suivi de Tournée</h1><p>Commune de Mékhé | GPS Haute Précision | Itinéraire en temps réel</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BASE DE DONNÉES ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ Configuration base de données manquante")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS GPS ====================

def get_position_exacte():
    """
    Récupère la position GPS exacte via l'API de géolocalisation du navigateur
    Utilise streamlit-js-eval pour un accès direct au GPS avec haute précision
    """
    if not GPS_AVAILABLE:
        return {"lat": 15.115000, "lon": -16.635000, "accuracy": 100, "error": "Package non installé"}
    
    try:
        # Utiliser streamlit-js-eval pour obtenir la géolocalisation exacte
        geolocation = get_geolocation()
        
        if geolocation and 'coords' in geolocation:
            coords = geolocation['coords']
            
            # Vérifier si les coordonnées sont valides
            lat = coords.get('latitude')
            lon = coords.get('longitude')
            accuracy = coords.get('accuracy', 100)
            
            if lat and lon:
                return {
                    "lat": lat,
                    "lon": lon,
                    "accuracy": accuracy,
                    "altitude": coords.get('altitude'),
                    "speed": coords.get('speed'),
                    "heading": coords.get('heading'),
                    "timestamp": geolocation.get('timestamp'),
                    "status": "success"
                }
            else:
                return {"lat": 15.115000, "lon": -16.635000, "accuracy": 100, "status": "no_coords", "error": "Coordonnées non disponibles"}
        else:
            return {"lat": 15.115000, "lon": -16.635000, "accuracy": 100, "status": "no_data", "error": "Aucune donnée GPS"}
            
    except Exception as e:
        return {"lat": 15.115000, "lon": -16.635000, "accuracy": 100, "status": "error", "error": str(e)}

def get_precision_label(accuracy):
    """Retourne un label et une classe CSS basés sur la précision GPS"""
    if accuracy < 10:
        return ("🟢 Excellente", "gps-precision-high", "Moins de 10 mètres")
    elif accuracy < 50:
        return ("🟡 Bonne", "gps-precision-medium", f"{accuracy:.0f} mètres")
    else:
        return ("🔴 Faible", "gps-precision-low", f"{accuracy:.0f} mètres")

def calculer_distance(point1, point2):
    """Calcule la distance exacte entre deux points GPS en km"""
    if point1 and point2 and point1.get('lat') and point2.get('lat'):
        try:
            return geodesic(
                (point1['lat'], point1['lon']),
                (point2['lat'], point2['lon'])
            ).kilometers
        except:
            return 0
    return 0

def enregistrer_point_gps(tournee_id, type_point, description, lat, lon, collecte_numero=None, position_ordre=None, precision=0, vitesse=None):
    """Enregistre un point GPS exact dans la base de données"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, precision_m, vitesse_kmh, description, collecte_numero, position_ordre)
                VALUES (:tid, :heure, :type, :lat, :lon, :precision, :vitesse, :desc, :collecte, :ordre)
            """), {
                "tid": tournee_id,
                "heure": datetime.now(),
                "type": type_point,
                "lat": lat,
                "lon": lon,
                "precision": precision,
                "vitesse": vitesse,
                "desc": description,
                "collecte": collecte_numero,
                "ordre": position_ordre
            })
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur enregistrement GPS: {e}")
        return False

# ==================== FONCTIONS BASE DE DONNÉES ====================

def get_quartiers():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, nom FROM quartiers WHERE actif = true ORDER BY nom")).fetchall()
        return [(r[0], r[1]) for r in result]

def get_equipes():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, nom FROM equipes WHERE actif = true ORDER BY nom")).fetchall()
        return [(r[0], r[1]) for r in result]

def get_quartier_id(nom):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM quartiers WHERE nom = :nom"), {"nom": nom}).first()
        return result[0] if result else None

def get_equipe_id(nom):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM equipes WHERE nom = :nom"), {"nom": nom}).first()
        return result[0] if result else None

def formater_duree(minutes):
    if minutes <= 0:
        return "0 min"
    heures = int(minutes // 60)
    mins = int(minutes % 60)
    if heures > 0:
        return f"{heures}h {mins}min"
    return f"{mins}min"

def exporter_tournee_excel(tournee_data):
    """Exporte le résumé complet de la tournée en Excel"""
    try:
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            
            resume = pd.DataFrame({
                "Informations": [
                    "Date de la tournée", "Agent", "Quartier", "Équipe",
                    "Distance totale (km)", "Volume total collecté (m³)",
                    "Nombre de points GPS", "Collecte 2 effectuée", "Statut"
                ],
                "Valeur": [
                    tournee_data.get("date", ""), tournee_data.get("agent", ""),
                    tournee_data.get("quartier", ""), tournee_data.get("equipe", ""),
                    f"{tournee_data.get('distance', 0):.2f}", f"{tournee_data.get('volume_total', 0):.1f}",
                    tournee_data.get("nb_points", 0), "Oui" if tournee_data.get("collecte2_effectuee", False) else "Non",
                    "Terminée"
                ]
            })
            resume.to_excel(writer, sheet_name="Résumé général", index=False)
            
            if tournee_data.get("points_gps"):
                points_list = []
                noms_points = {
                    "depart_depot": "🏭 Départ dépôt", "debut_collecte": "🗑️ Début collecte",
                    "fin_collecte": "🗑️ Fin collecte", "depart_decharge": "🚛 Départ décharge",
                    "arrivee_decharge": "🏭 Arrivée décharge", "sortie_decharge": "🏭 Sortie décharge",
                    "retour_depot": "🏁 Retour dépôt"
                }
                for i, point in enumerate(tournee_data["points_gps"]):
                    points_list.append({
                        "Ordre": i + 1, "Type": noms_points.get(point.get("type", ""), point.get("type", "")),
                        "Collecte": f"Collecte {point.get('collecte', '')}", "Heure": point.get("heure", ""),
                        "Latitude": f"{point.get('lat', 0):.6f}", "Longitude": f"{point.get('lon', 0):.6f}",
                        "Précision (m)": point.get("precision", "N/A"),
                        "Distance depuis dernier (km)": f"{point.get('distance_depuis_dernier', 0):.2f}"
                    })
                df_points = pd.DataFrame(points_list)
                df_points.to_excel(writer, sheet_name="Itinéraire détaillé", index=False)
            
            stats = pd.DataFrame({
                "Indicateur": ["📊 Volume Collecte 1 (m³)", "📊 Volume Collecte 2 (m³)", "📊 Volume total (m³)",
                               "📏 Distance totale (km)", "⏱️ Durée totale", "📍 Points Collecte 1", "📍 Points Collecte 2",
                               "⚡ Efficacité (km/m³)", "🎯 Précision GPS moyenne (m)"],
                "Valeur": [
                    f"{tournee_data.get('volume1', 0):.1f}", f"{tournee_data.get('volume2', 0):.1f}",
                    f"{tournee_data.get('volume_total', 0):.1f}", f"{tournee_data.get('distance', 0):.2f}",
                    tournee_data.get("duree_totale", "N/A"), tournee_data.get('nb_points_1', 0),
                    tournee_data.get('nb_points_2', 0), f"{tournee_data.get('efficacite', 0):.2f}",
                    f"{tournee_data.get('precision_moyenne', 0):.1f}"
                ]
            })
            stats.to_excel(writer, sheet_name="Statistiques", index=False)
        
        return output.getvalue()
    except Exception as e:
        st.error(f"Erreur export: {e}")
        return None

# ==================== SESSION STATE ====================
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'tournee_id' not in st.session_state:
    st.session_state.tournee_id = None
if 'date_tournee' not in st.session_state:
    st.session_state.date_tournee = date.today()
if 'quartier_nom' not in st.session_state:
    st.session_state.quartier_nom = ""
if 'volume1' not in st.session_state:
    st.session_state.volume1 = 0.0
if 'volume2' not in st.session_state:
    st.session_state.volume2 = 0.0
if 'points_gps' not in st.session_state:
    st.session_state.points_gps = []
if 'gps_actif' not in st.session_state:
    st.session_state.gps_actif = False
if 'collecte1_validee' not in st.session_state:
    st.session_state.collecte1_validee = False
if 'collecte2_validee' not in st.session_state:
    st.session_state.collecte2_validee = False
if 'collecte2_optionnelle' not in st.session_state:
    st.session_state.collecte2_optionnelle = False
if 'distance_totale' not in st.session_state:
    st.session_state.distance_totale = 0.0
if 'derniere_position' not in st.session_state:
    st.session_state.derniere_position = None
if 'temps_debut_tournee' not in st.session_state:
    st.session_state.temps_debut_tournee = None
if 'precision_moyenne' not in st.session_state:
    st.session_state.precision_moyenne = 0.0

# Horaires
if 'heure_depot_depart' not in st.session_state:
    st.session_state.heure_depot_depart = None
if 'heure_retour_depot' not in st.session_state:
    st.session_state.heure_retour_depot = None
if 'heure_debut_collecte1' not in st.session_state:
    st.session_state.heure_debut_collecte1 = None
if 'heure_fin_collecte1' not in st.session_state:
    st.session_state.heure_fin_collecte1 = None
if 'heure_depart_decharge1' not in st.session_state:
    st.session_state.heure_depart_decharge1 = None
if 'heure_arrivee_decharge1' not in st.session_state:
    st.session_state.heure_arrivee_decharge1 = None
if 'heure_sortie_decharge1' not in st.session_state:
    st.session_state.heure_sortie_decharge1 = None

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent de collecte")
    
    agent_nom_input = st.text_input("Votre nom complet", value=st.session_state.agent_nom, 
                                     placeholder="Ex: Alioune Diop")
    if agent_nom_input:
        st.session_state.agent_nom = agent_nom_input
        st.success(f"✅ Connecté: {agent_nom_input}")
    
    st.markdown("---")
    st.markdown("### 📍 GPS Haute Précision")
    
    if not GPS_AVAILABLE:
        st.error("❌ streamlit-js-eval non installé")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎯 ACTIVER GPS", use_container_width=True):
            st.session_state.gps_actif = True
            st.info("📱 Autorisez la géolocalisation dans votre navigateur")
            st.rerun()
    with col2:
        if st.button("⏸️ DÉSACTIVER", use_container_width=True):
            st.session_state.gps_actif = False
    
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF - Localisation haute précision</div>', unsafe_allow_html=True)
        
        pos_actuelle = get_position_exacte()
        
        if pos_actuelle.get('status') == 'success':
            st.metric("📍 Latitude", f"{pos_actuelle['lat']:.6f}")
            st.metric("📍 Longitude", f"{pos_actuelle['lon']:.6f}")
            
            precision_label, precision_class, precision_detail = get_precision_label(pos_actuelle['accuracy'])
            st.markdown(f'<span class="{precision_class}">🎯 Précision: {precision_label} ({precision_detail})</span>', unsafe_allow_html=True)
            
            if pos_actuelle.get('speed'):
                st.metric("🚗 Vitesse", f"{pos_actuelle['speed']:.1f} km/h")
            
            if pos_actuelle.get('altitude'):
                st.metric("⛰️ Altitude", f"{pos_actuelle['altitude']:.0f} m")
        else:
            st.warning(f"⚠️ En attente de signal GPS...")
            st.info("💡 Assurez-vous d'avoir autorisé la géolocalisation")
    else:
        st.markdown('<div class="gps-inactive">⚠️ GPS INACTIF</div>', unsafe_allow_html=True)
        st.info("💡 Activez le GPS pour enregistrer votre position exacte et suivre votre itinéraire")
    
    st.markdown("---")
    st.markdown("### 📊 Récapitulatif")
    
    if st.session_state.collecte1_validee:
        st.success("✅ Collecte 1 terminée")
    else:
        st.warning("⏳ Collecte 1 en attente")
    
    if st.session_state.collecte2_validee:
        st.success("✅ Collecte 2 terminée")
    elif st.session_state.collecte1_validee:
        st.info("ℹ️ Collecte 2 optionnelle")
    
    if st.session_state.volume1 > 0:
        st.metric("📦 Volume Collecte 1", f"{st.session_state.volume1:.1f} m³")
    if st.session_state.volume2 > 0:
        st.metric("📦 Volume Collecte 2", f"{st.session_state.volume2:.1f} m³")
    
    total_volume = st.session_state.volume1 + st.session_state.volume2
    if total_volume > 0:
        st.metric("📊 Volume total", f"{total_volume:.1f} m³")
    
    if st.session_state.distance_totale > 0:
        st.metric("📏 Distance parcourue", f"{st.session_state.distance_totale:.2f} km")
    
    if st.session_state.temps_debut_tournee:
        duree = (datetime.now() - st.session_state.temps_debut_tournee).total_seconds() / 60
        st.metric("⏱️ Durée tournée", formater_duree(duree))

# ==================== SECTION COMMUNE ====================
col1, col2 = st.columns(2)
with col1:
    date_tournee = st.date_input("📅 Date", value=st.session_state.date_tournee)
    st.session_state.date_tournee = date_tournee
with col2:
    quartiers_list = get_quartiers()
    if quartiers_list:
        quartier_nom = st.selectbox("📍 Quartier", [q[1] for q in quartiers_list])
        st.session_state.quartier_nom = quartier_nom

col1, col2 = st.columns(2)
with col1:
    equipes_list = get_equipes()
    if equipes_list:
        equipe_nom = st.selectbox("👥 Équipe", [e[1] for e in equipes_list])
with col2:
    if st.button("🚀 DÉMARRER LA TOURNÉE", type="primary", use_container_width=True):
        st.session_state.temps_debut_tournee = datetime.now()
        st.success("✅ Tournée démarrée !")

# ==================== COLLECTE 1 (OBLIGATOIRE) ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 <strong>COLLECTE 1</strong> - Premier tour (OBLIGATOIRE)</div>', unsafe_allow_html=True)

if not st.session_state.collecte1_validee:
    
    points_collecte1 = [
        ("🏭 DÉPART DU DÉPÔT", "depart_depot", "Départ du dépôt"),
        ("🗑️ DÉBUT COLLECTE 1", "debut_collecte", "Début de la collecte 1"),
        ("🗑️ FIN COLLECTE 1", "fin_collecte", "Fin de la collecte 1"),
        ("🚛 DÉPART VERS DÉCHARGE 1", "depart_decharge", "Départ vers décharge 1"),
        ("🏭 ARRIVÉE DÉCHARGE 1", "arrivee_decharge", "Arrivée décharge 1")
    ]
    
    for titre, type_point, description in points_collecte1:
        st.markdown(f"#### {titre}")
        col1, col2 = st.columns([2, 1])
        with col2:
            if st.button(f"📍 Enregistrer", key=f"btn_{type_point}", use_container_width=True):
                if st.session_state.gps_actif:
                    pos = get_position_exacte()
                    heure_actuelle = datetime.now()
                    
                    if pos.get('status') == 'success':
                        # Sauvegarder l'heure
                        if type_point == "depart_depot":
                            st.session_state.heure_depot_depart = heure_actuelle
                        elif type_point == "debut_collecte":
                            st.session_state.heure_debut_collecte1 = heure_actuelle
                        elif type_point == "fin_collecte":
                            st.session_state.heure_fin_collecte1 = heure_actuelle
                        elif type_point == "depart_decharge":
                            st.session_state.heure_depart_decharge1 = heure_actuelle
                        elif type_point == "arrivee_decharge":
                            st.session_state.heure_arrivee_decharge1 = heure_actuelle
                        
                        # Calculer distance depuis dernier point
                        distance_depuis_dernier = 0
                        if st.session_state.derniere_position:
                            distance_depuis_dernier = calculer_distance(st.session_state.derniere_position, pos)
                            st.session_state.distance_totale += distance_depuis_dernier
                        
                        # Mettre à jour la précision moyenne
                        if st.session_state.points_gps:
                            total_precision = sum([p.get('precision', 0) for p in st.session_state.points_gps])
                            st.session_state.precision_moyenne = (total_precision + pos['accuracy']) / (len(st.session_state.points_gps) + 1)
                        else:
                            st.session_state.precision_moyenne = pos['accuracy']
                        
                        point_data = {
                            "type": type_point,
                            "lat": pos["lat"],
                            "lon": pos["lon"],
                            "collecte": 1,
                            "description": f"{description} - {heure_actuelle.strftime('%H:%M:%S')}",
                            "heure": heure_actuelle.strftime("%H:%M:%S"),
                            "distance_depuis_dernier": distance_depuis_dernier,
                            "precision": pos["accuracy"]
                        }
                        st.session_state.points_gps.append(point_data)
                        st.session_state.derniere_position = pos
                        
                        precision_label, _, _ = get_precision_label(pos['accuracy'])
                        st.success(f"✅ {description} enregistré à {heure_actuelle.strftime('%H:%M:%S')}")
                        st.info(f"🎯 Précision: {precision_label}")
                        if distance_depuis_dernier > 0:
                            st.info(f"📏 Distance depuis dernier point: {distance_depuis_dernier:.2f} km")
                    else:
                        st.error("❌ Position GPS non disponible. Vérifiez votre connexion et les permissions.")
                else:
                    st.warning("⚠️ Activez le GPS d'abord")
    
    # Point de sortie décharge avec volume
    st.markdown("#### 🏭 SORTIE DE LA DÉCHARGE 1")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        volume1_input = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key="volume1_input")
    with col2:
        if st.button("📍 Sortie + Volume", key="btn_sortie1", use_container_width=True):
            if st.session_state.gps_actif and volume1_input > 0:
                pos = get_position_exacte()
                heure_actuelle = datetime.now()
                
                if pos.get('status') == 'success':
                    st.session_state.heure_sortie_decharge1 = heure_actuelle
                    st.session_state.volume1 = volume1_input
                    
                    distance_depuis_dernier = calculer_distance(st.session_state.derniere_position, pos)
                    st.session_state.distance_totale += distance_depuis_dernier
                    
                    point_data = {
                        "type": "sortie_decharge",
                        "lat": pos["lat"],
                        "lon": pos["lon"],
                        "collecte": 1,
                        "description": f"Sortie décharge 1 - Volume: {volume1_input} m³",
                        "heure": heure_actuelle.strftime("%H:%M:%S"),
                        "distance_depuis_dernier": distance_depuis_dernier,
                        "precision": pos["accuracy"]
                    }
                    st.session_state.points_gps.append(point_data)
                    st.session_state.derniere_position = pos
                    
                    st.success(f"✅ Sortie enregistrée - Volume: {volume1_input} m³")
                else:
                    st.error("❌ Position GPS non disponible")
            elif volume1_input <= 0:
                st.warning("⚠️ Veuillez saisir le volume déchargé")
            else:
                st.warning("⚠️ Activez le GPS")
    
    # Validation Collecte 1
    st.markdown("---")
    if st.button("✅ VALIDER LA COLLECTE 1", type="primary", use_container_width=True):
        if st.session_state.volume1 > 0:
            st.session_state.collecte1_validee = True
            st.success("✅ Collecte 1 validée !")
            st.info("ℹ️ Vous pouvez maintenant effectuer la Collecte 2 (optionnelle) ou terminer la tournée")
            st.rerun()
        else:
            st.warning("⚠️ Veuillez enregistrer le volume déchargé")

else:
    st.success("✅ Collecte 1 terminée et validée")
    st.write(f"📦 Volume déchargé: {st.session_state.volume1:.1f} m³")
    
    if st.session_state.heure_debut_collecte1 and st.session_state.heure_fin_collecte1:
        duree_collecte1 = (st.session_state.heure_fin_collecte1 - st.session_state.heure_debut_collecte1).total_seconds() / 60
        st.info(f"⏱️ Durée Collecte 1: {formater_duree(duree_collecte1)}")
    
    if st.button("📝 Modifier Collecte 1", use_container_width=True):
        st.session_state.collecte1_validee = False
        st.rerun()

# ==================== COLLECTE 2 (OPTIONNELLE) ====================
st.markdown("---")
st.markdown('<div class="collecte2-optional">🚛 <strong>COLLECTE 2</strong> - Deuxième tour (OPTIONNEL)</div>', unsafe_allow_html=True)

if st.session_state.collecte1_validee:
    
    if not st.session_state.collecte2_validee:
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ EFFECTUER LA COLLECTE 2", use_container_width=True):
                st.session_state.collecte2_optionnelle = True
                st.rerun()
        with col2:
            if st.button("⏭️ PASSER LA COLLECTE 2", use_container_width=True):
                st.session_state.collecte2_validee = True
                st.rerun()
        
        if st.session_state.collecte2_optionnelle:
            
            points_collecte2 = [
                ("🗑️ DÉBUT COLLECTE 2", "debut_collecte", "Début de la collecte 2"),
                ("🗑️ FIN COLLECTE 2", "fin_collecte", "Fin de la collecte 2"),
                ("🚛 DÉPART VERS DÉCHARGE 2", "depart_decharge", "Départ vers décharge 2"),
                ("🏭 ARRIVÉE DÉCHARGE 2", "arrivee_decharge", "Arrivée décharge 2")
            ]
            
            for titre, type_point, description in points_collecte2:
                st.markdown(f"#### {titre}")
                col1, col2 = st.columns([2, 1])
                with col2:
                    if st.button(f"📍 Enregistrer", key=f"btn2_{type_point}", use_container_width=True):
                        if st.session_state.gps_actif:
                            pos = get_position_exacte()
                            heure_actuelle = datetime.now()
                            
                            if pos.get('status') == 'success':
                                distance_depuis_dernier = calculer_distance(st.session_state.derniere_position, pos)
                                st.session_state.distance_totale += distance_depuis_dernier
                                
                                point_data = {
                                    "type": type_point,
                                    "lat": pos["lat"],
                                    "lon": pos["lon"],
                                    "collecte": 2,
                                    "description": f"{description} - {heure_actuelle.strftime('%H:%M:%S')}",
                                    "heure": heure_actuelle.strftime("%H:%M:%S"),
                                    "distance_depuis_dernier": distance_depuis_dernier,
                                    "precision": pos["accuracy"]
                                }
                                st.session_state.points_gps.append(point_data)
                                st.session_state.derniere_position = pos
                                st.success(f"✅ {description} enregistré")
                            else:
                                st.error("❌ Position GPS non disponible")
                        else:
                            st.warning("⚠️ Activez le GPS")
            
            # Sortie décharge 2 avec volume
            st.markdown("#### 🏭 SORTIE DE LA DÉCHARGE 2")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                volume2_input = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key="volume2_input")
            with col2:
                if st.button("📍 Sortie + Volume 2", key="btn_sortie2", use_container_width=True):
                    if st.session_state.gps_actif and volume2_input > 0:
                        pos = get_position_exacte()
                        heure_actuelle = datetime.now()
                        
                        if pos.get('status') == 'success':
                            st.session_state.volume2 = volume2_input
                            
                            distance_depuis_dernier = calculer_distance(st.session_state.derniere_position, pos)
                            st.session_state.distance_totale += distance_depuis_dernier
                            
                            point_data = {
                                "type": "sortie_decharge",
                                "lat": pos["lat"],
                                "lon": pos["lon"],
                                "collecte": 2,
                                "description": f"Sortie décharge 2 - Volume: {volume2_input} m³",
                                "heure": heure_actuelle.strftime("%H:%M:%S"),
                                "distance_depuis_dernier": distance_depuis_dernier,
                                "precision": pos["accuracy"]
                            }
                            st.session_state.points_gps.append(point_data)
                            st.session_state.derniere_position = pos
                            st.success(f"✅ Sortie enregistrée - Volume: {volume2_input} m³")
                        else:
                            st.error("❌ Position GPS non disponible")
                    elif volume2_input <= 0:
                        st.warning("⚠️ Veuillez saisir le volume déchargé")
                    else:
                        st.warning("⚠️ Activez le GPS")
            
            # Retour dépôt
            st.markdown("#### 🏁 RETOUR AU DÉPÔT")
            col1, col2 = st.columns([2, 1])
            with col2:
                if st.button("📍 Retour dépôt", key="btn_retour", use_container_width=True):
                    if st.session_state.gps_actif:
                        pos = get_position_exacte()
                        heure_actuelle = datetime.now()
                        
                        if pos.get('status') == 'success':
                            st.session_state.heure_retour_depot = heure_actuelle
                            
                            distance_depuis_dernier = calculer_distance(st.session_state.derniere_position, pos)
                            st.session_state.distance_totale += distance_depuis_dernier
                            
                            point_data = {
                                "type": "retour_depot",
                                "lat": pos["lat"],
                                "lon": pos["lon"],
                                "collecte": 2,
                                "description": f"Retour au dépôt - {heure_actuelle.strftime('%H:%M:%S')}",
                                "heure": heure_actuelle.strftime("%H:%M:%S"),
                                "distance_depuis_dernier": distance_depuis_dernier,
                                "precision": pos["accuracy"]
                            }
                            st.session_state.points_gps.append(point_data)
                            st.session_state.derniere_position = pos
                            st.success(f"✅ Retour dépôt enregistré")
                        else:
                            st.error("❌ Position GPS non disponible")
                    else:
                        st.warning("⚠️ Activez le GPS")
            
            st.markdown("---")
            if st.button("✅ VALIDER LA COLLECTE 2", type="primary", use_container_width=True):
                if st.session_state.volume2 > 0:
                    st.session_state.collecte2_validee = True
                    st.success("✅ Collecte 2 validée !")
                    st.rerun()
                else:
                    st.warning("⚠️ Veuillez enregistrer le volume déchargé")
    
    else:
        if st.session_state.volume2 > 0:
            st.success("✅ Collecte 2 terminée")
            st.write(f"📦 Volume déchargé: {st.session_state.volume2:.1f} m³")
        else:
            st.info("ℹ️ Collecte 2 non effectuée")

# ==================== TERMINER LA TOURNÉE ====================
if st.session_state.collecte1_validee and (st.session_state.collecte2_validee or not st.session_state.collecte2_optionnelle):
    
    st.markdown("---")
    st.markdown("### 🏁 TERMINER LA TOURNÉE")
    
    total_volume = st.session_state.volume1 + st.session_state.volume2
    duree_totale = (datetime.now() - st.session_state.temps_debut_tournee).total_seconds() / 60 if st.session_state.temps_debut_tournee else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📦 Volume total", f"{total_volume:.1f} m³")
    with col2:
        st.metric("📏 Distance totale", f"{st.session_state.distance_totale:.2f} km")
    with col3:
        st.metric("⏱️ Durée totale", formater_duree(duree_totale))
    with col4:
        efficacite = st.session_state.distance_totale / total_volume if total_volume > 0 else 0
        st.metric("⚡ Efficacité", f"{efficacite:.2f} km/m³")
    
    if st.session_state.precision_moyenne > 0:
        st.metric("🎯 Précision GPS moyenne", f"{st.session_state.precision_moyenne:.1f} m")
    
    if st.button("💾 ENREGISTRER LE RAPPORT FINAL", type="primary", use_container_width=True):
        quartier_id = get_quartier_id(st.session_state.quartier_nom)
        equipe_id = get_equipe_id(equipe_nom)
        
        if quartier_id and equipe_id:
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("""
                        INSERT INTO tournees (
                            date_tournee, quartier_id, equipe_id, agent_nom,
                            volume_collecte1, volume_collecte2, volume_m3,
                            heure_depot_depart, heure_retour_depot, distance_parcourue_km, 
                            collecte2_effectuee, duree_totale_minutes, statut
                        ) VALUES (
                            :date, :qid, :eid, :agent,
                            :vol1, :vol2, :vol_total,
                            :depart, :retour, :distance,
                            :collecte2, :duree, 'termine'
                        )
                        RETURNING id
                    """), {
                        "date": st.session_state.date_tournee,
                        "qid": quartier_id,
                        "eid": equipe_id,
                        "agent": st.session_state.agent_nom,
                        "vol1": st.session_state.volume1,
                        "vol2": st.session_state.volume2,
                        "vol_total": total_volume,
                        "depart": st.session_state.heure_depot_depart.strftime("%H:%M:%S") if st.session_state.heure_depot_depart else None,
                        "retour": st.session_state.heure_retour_depot.strftime("%H:%M:%S") if st.session_state.heure_retour_depot else None,
                        "distance": st.session_state.distance_totale,
                        "collecte2": st.session_state.collecte2_validee,
                        "duree": duree_totale
                    })
                    tournee_id = result.fetchone()[0]
                    
                    for idx, point in enumerate(st.session_state.points_gps):
                        conn.execute(text("""
                            INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, precision_m, description, collecte_numero, position_ordre)
                            VALUES (:tid, :heure, :type, :lat, :lon, :precision, :desc, :collecte, :ordre)
                        """), {
                            "tid": tournee_id,
                            "heure": datetime.now(),
                            "type": point["type"],
                            "lat": point["lat"],
                            "lon": point["lon"],
                            "precision": point.get("precision", 0),
                            "desc": point.get("description", ""),
                            "collecte": point["collecte"],
                            "ordre": idx + 1
                        })
                    conn.commit()
                
                st.balloons()
                st.success("✅ Tournée enregistrée avec succès dans la base de données !")
                
                if st.button("🔄 DÉMARRER UNE NOUVELLE TOURNÉE", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key not in ['agent_nom']:
                            del st.session_state[key]
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erreur lors de l'enregistrement: {e}")

# ==================== CARTE INTERACTIVE ====================
st.markdown("---")
st.markdown("### 🗺️ Carte interactive - Itinéraire en temps réel")

if st.session_state.points_gps:
    df_points = pd.DataFrame(st.session_state.points_gps)
    
    couleurs = {
        "depart_depot": "green", "debut_collecte": "blue", "fin_collecte": "blue",
        "depart_decharge": "orange", "arrivee_decharge": "red", "sortie_decharge": "purple", "retour_depot": "brown"
    }
    
    noms_points = {
        "depart_depot": "🏭 Départ dépôt", "debut_collecte": "🗑️ Début collecte",
        "fin_collecte": "🗑️ Fin collecte", "depart_decharge": "🚛 Départ décharge",
        "arrivee_decharge": "🏭 Arrivée décharge", "sortie_decharge": "🏭 Sortie décharge",
        "retour_depot": "🏁 Retour dépôt"
    }
    
    df_points["nom_affichage"] = df_points["type"].map(noms_points)
    
    fig = px.scatter_mapbox(
        df_points,
        lat="lat",
        lon="lon",
        color="type",
        hover_name="nom_affichage",
        hover_data={"collecte": True, "heure": True, "distance_depuis_dernier": True, "precision": True},
        color_discrete_map=couleurs,
        zoom=14,
        center={"lat": 15.11, "lon": -16.65},
        title="Itinéraire exact de la tournée - Points GPS enregistrés avec précision",
        height=550
    )
    
    if len(df_points) > 1:
        fig.add_trace(go.Scattermapbox(
            lat=df_points["lat"].tolist(),
            lon=df_points["lon"].tolist(),
            mode='lines+markers',
            line=dict(width=3, color='blue'),
            marker=dict(size=8, color='blue'),
            name='Trajet réel effectué',
            showlegend=True
        ))
    
    if st.session_state.gps_actif:
        pos_actuelle = get_position_exacte()
        if pos_actuelle.get('status') == 'success':
            fig.add_trace(go.Scattermapbox(
                lat=[pos_actuelle["lat"]],
                lon=[pos_actuelle["lon"]],
                mode='markers',
                marker=dict(size=14, color='red', symbol='circle'),
                name='Position actuelle (GPS haute précision)',
                showlegend=True
            ))
    
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=13,
        margin={"r": 0, "t": 40, "l": 0, "b": 0}
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("""
    <div class="info-box">
    <strong>📊 Légende de l'itinéraire GPS haute précision :</strong><br>
    🟢 Vert - Départ dépôt<br>
    🔵 Bleu - Points de collecte (début/fin)<br>
    🟠 Orange - Départ vers décharge<br>
    🔴 Rouge - Arrivée décharge<br>
    🟣 Violet - Sortie décharge<br>
    🟤 Marron - Retour dépôt<br>
    🔵 Ligne bleue - Trajet réel effectué<br>
    🔴 Point rouge - Position actuelle (GPS temps réel avec précision métrique)
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📋 Détail complet de l'itinéraire avec précision GPS"):
        for i, point in enumerate(st.session_state.points_gps):
            precision_label, _, _ = get_precision_label(point.get('precision', 100))
            st.write(f"**{i+1}. {noms_points.get(point['type'], point['type'])}** - Collecte {point['collecte']}")
            st.write(f"   🕐 Heure: {point.get('heure', 'N/A')}")
            st.write(f"   📍 {point['lat']:.6f}, {point['lon']:.6f}")
            st.write(f"   🎯 Précision: {precision_label}")
            if point.get('distance_depuis_dernier', 0) > 0:
                st.write(f"   📏 Distance depuis dernier point: {point['distance_depuis_dernier']:.2f} km")
            st.write("")

# ==================== EXPORT RAPPORT ====================
if st.session_state.collecte1_validee and (st.session_state.collecte2_validee or not st.session_state.collecte2_optionnelle):
    
    st.markdown("---")
    st.markdown("### 📥 Exporter le rapport")
    
    total_volume = st.session_state.volume1 + st.session_state.volume2
    nb_points_1 = len([p for p in st.session_state.points_gps if p.get("collecte") == 1])
    nb_points_2 = len([p for p in st.session_state.points_gps if p.get("collecte") == 2])
    duree_totale = (datetime.now() - st.session_state.temps_debut_tournee).total_seconds() / 60 if st.session_state.temps_debut_tournee else 0
    
    tournee_data = {
        "date": st.session_state.date_tournee.strftime("%d/%m/%Y"),
        "agent": st.session_state.agent_nom,
        "quartier": st.session_state.quartier_nom,
        "equipe": equipe_nom,
        "distance": st.session_state.distance_totale,
        "volume1": st.session_state.volume1,
        "volume2": st.session_state.volume2,
        "volume_total": total_volume,
        "nb_points": len(st.session_state.points_gps),
        "nb_points_1": nb_points_1,
        "nb_points_2": nb_points_2,
        "points_gps": st.session_state.points_gps,
        "collecte2_effectuee": st.session_state.collecte2_validee,
        "duree_totale": formater_duree(duree_totale),
        "efficacite": st.session_state.distance_totale / total_volume if total_volume > 0 else 0,
        "precision_moyenne": st.session_state.precision_moyenne
    }
    
    col1, col2 = st.columns(2)
    with col1:
        excel_data = exporter_tournee_excel(tournee_data)
        if excel_data:
            st.download_button(
                label="📥 EXPORTER EN EXCEL (Rapport complet avec GPS)",
                data=excel_data,
                file_name=f"rapport_collecte_{st.session_state.date_tournee.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    with col2:
        csv_data = f"""Date,Agent,Quartier,Volume1 (m³),Volume2 (m³),Volume Total (m³),Distance (km),Durée,Efficacité (km/m³),Précision GPS moyenne (m)
{st.session_state.date_tournee.strftime("%d/%m/%Y")},{st.session_state.agent_nom},{st.session_state.quartier_nom},{st.session_state.volume1},{st.session_state.volume2},{total_volume},{st.session_state.distance_totale:.2f},{formater_duree(duree_totale)},{tournee_data['efficacite']:.2f},{st.session_state.precision_moyenne:.1f}
"""
        st.download_button(
            label="📄 EXPORTER EN CSV",
            data=csv_data,
            file_name=f"rapport_collecte_{st.session_state.date_tournee.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📱 Agent: {st.session_state.agent_nom or 'Non connecté'} | GPS: {'🟢 Haute précision' if st.session_state.gps_actif else '🔴 Inactif'} | Commune de Mékhé | Quartiers: HLM, LEBOU EST, LEBOU OUEST, MBAMBARA, NDIOB, NGAYE DIJINE, NGAYE DJITE")
