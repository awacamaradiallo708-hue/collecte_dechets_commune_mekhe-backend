"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version complète avec :
- Collecte 1 et Collecte 2 séparées
- Carte interactive avec tracé du trajet
- Export Excel (6 feuilles)
- Calcul des durées et statistiques
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, time, timedelta
from sqlalchemy import create_engine, text
import os
from io import BytesIO

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
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #2196F3;
        margin: 1rem 0;
    }
    .success-box {
        background: #d4edda;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .gps-active {
        background: #4CAF50;
        color: white;
        padding: 0.5rem;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
    }
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte - Suivi de Tournée</h1><p>Commune de Mékhé | Carte interactive | GPS temps réel | Export Excel</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BASE DE DONNÉES ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ Configuration base de données manquante")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS ====================

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

def enregistrer_point_gps(tournee_id, type_point, description, lat, lon, collecte_numero=None):
    """Enregistre un point GPS"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description, collecte_numero)
                VALUES (:tid, :heure, :type, :lat, :lon, :desc, :collecte)
            """), {
                "tid": tournee_id,
                "heure": datetime.now(),
                "type": type_point,
                "lat": lat,
                "lon": lon,
                "desc": description,
                "collecte": collecte_numero
            })
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur GPS: {e}")
        return False

def get_position():
    """Récupère la position GPS (simulée pour le moment)"""
    # Dans une vraie application, utiliser l'API de géolocalisation
    return {"lat": 15.115000, "lon": -16.635000, "accuracy": 10}

# ==================== FONCTION EXPORT EXCEL ====================
def exporter_tournee_excel(tournee_data):
    """
    Exporte le résumé complet de la tournée en Excel avec 6 feuilles
    """
    try:
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            
            # ========== FEUILLE 1 : RÉSUMÉ GÉNÉRAL ==========
            resume = pd.DataFrame({
                "Informations": [
                    "Date de la tournée",
                    "Agent",
                    "Quartier",
                    "Équipe",
                    "Distance totale (km)",
                    "Volume total collecté (m³)",
                    "Nombre de points GPS",
                    "Statut"
                ],
                "Valeur": [
                    tournee_data.get("date", ""),
                    tournee_data.get("agent", ""),
                    tournee_data.get("quartier", ""),
                    tournee_data.get("equipe", ""),
                    tournee_data.get("distance", "N/A"),
                    f"{tournee_data.get('volume_total', 0):.1f}",
                    tournee_data.get("nb_points", 0),
                    "Terminée"
                ]
            })
            resume.to_excel(writer, sheet_name="Résumé général", index=False)
            
            # ========== FEUILLE 2 : HORAIRES ==========
            horaires = pd.DataFrame({
                "Étape": [
                    "🏭 Départ du dépôt",
                    "🗑️ Début Collecte 1",
                    "🗑️ Fin Collecte 1",
                    "🚛 Départ vers Décharge 1",
                    "🏭 Arrivée Décharge 1",
                    "🏭 Sortie Décharge 1",
                    "🗑️ Début Collecte 2",
                    "🗑️ Fin Collecte 2",
                    "🚛 Départ vers Décharge 2",
                    "🏭 Arrivée Décharge 2",
                    "🏭 Sortie Décharge 2",
                    "🏁 Retour au dépôt"
                ],
                "Heure": [
                    tournee_data.get("heure_depot_depart", ""),
                    tournee_data.get("heure_debut_collecte1", ""),
                    tournee_data.get("heure_fin_collecte1", ""),
                    tournee_data.get("heure_depart_decharge1", ""),
                    tournee_data.get("heure_arrivee_decharge1", ""),
                    tournee_data.get("heure_sortie_decharge1", ""),
                    tournee_data.get("heure_debut_collecte2", ""),
                    tournee_data.get("heure_fin_collecte2", ""),
                    tournee_data.get("heure_depart_decharge2", ""),
                    tournee_data.get("heure_arrivee_decharge2", ""),
                    tournee_data.get("heure_sortie_decharge2", ""),
                    tournee_data.get("heure_retour_depot", "")
                ]
            })
            horaires.to_excel(writer, sheet_name="Horaires", index=False)
            
            # ========== FEUILLE 3 : DURÉES ==========
            def calc_duree_str(debut, fin):
                if debut and fin and debut != "" and fin != "":
                    try:
                        h1, m1 = map(int, debut.split(':'))
                        h2, m2 = map(int, fin.split(':'))
                        minutes = (h2 * 60 + m2) - (h1 * 60 + m1)
                        if minutes >= 0:
                            return f"{minutes // 60}h {minutes % 60}min"
                    except:
                        pass
                return "N/A"
            
            durees = pd.DataFrame({
                "Activité": [
                    "⏱️ Durée Collecte 1",
                    "🚚 Trajet vers Décharge 1",
                    "🏭 Temps à la Décharge 1",
                    "⏱️ Durée Collecte 2",
                    "🚚 Trajet vers Décharge 2",
                    "🏭 Temps à la Décharge 2",
                    "🏁 Retour au dépôt",
                    "⏰ Temps total de la tournée"
                ],
                "Durée": [
                    calc_duree_str(tournee_data.get("heure_debut_collecte1", ""), tournee_data.get("heure_fin_collecte1", "")),
                    calc_duree_str(tournee_data.get("heure_fin_collecte1", ""), tournee_data.get("heure_arrivee_decharge1", "")),
                    calc_duree_str(tournee_data.get("heure_arrivee_decharge1", ""), tournee_data.get("heure_sortie_decharge1", "")),
                    calc_duree_str(tournee_data.get("heure_debut_collecte2", ""), tournee_data.get("heure_fin_collecte2", "")),
                    calc_duree_str(tournee_data.get("heure_fin_collecte2", ""), tournee_data.get("heure_arrivee_decharge2", "")),
                    calc_duree_str(tournee_data.get("heure_arrivee_decharge2", ""), tournee_data.get("heure_sortie_decharge2", "")),
                    calc_duree_str(tournee_data.get("heure_sortie_decharge2", ""), tournee_data.get("heure_retour_depot", "")),
                    calc_duree_str(tournee_data.get("heure_depot_depart", ""), tournee_data.get("heure_retour_depot", ""))
                ]
            })
            durees.to_excel(writer, sheet_name="Durées", index=False)
            
            # ========== FEUILLE 4 : VOLUMES ==========
            volumes = pd.DataFrame({
                "Collecte": ["Collecte 1", "Collecte 2", "Total"],
                "Volume (m³)": [
                    tournee_data.get("volume1", 0),
                    tournee_data.get("volume2", 0),
                    tournee_data.get("volume_total", 0)
                ],
                "Équivalence (tonnes)": [
                    tournee_data.get("volume1", 0) * 0.8,
                    tournee_data.get("volume2", 0) * 0.8,
                    tournee_data.get("volume_total", 0) * 0.8
                ]
            })
            volumes.to_excel(writer, sheet_name="Volumes", index=False)
            
            # ========== FEUILLE 5 : POINTS GPS ==========
            if tournee_data.get("points_gps"):
                points_list = []
                noms_points = {
                    "depart_depot": "🏭 Départ dépôt",
                    "debut_collecte": "🗑️ Début collecte",
                    "fin_collecte": "🗑️ Fin collecte",
                    "depart_decharge": "🚛 Départ décharge",
                    "arrivee_decharge": "🏭 Arrivée décharge",
                    "sortie_decharge": "🏭 Sortie décharge",
                    "retour_depot": "🏁 Retour dépôt"
                }
                for i, point in enumerate(tournee_data["points_gps"]):
                    points_list.append({
                        "N°": i + 1,
                        "Type": noms_points.get(point.get("type", ""), point.get("type", "")),
                        "Collecte": f"Collecte {point.get('collecte', '')}",
                        "Latitude": f"{point.get('lat', 0):.6f}",
                        "Longitude": f"{point.get('lon', 0):.6f}",
                        "Description": point.get("description", "")
                    })
                df_points = pd.DataFrame(points_list)
                df_points.to_excel(writer, sheet_name="Points GPS", index=False)
            
            # ========== FEUILLE 6 : STATISTIQUES ==========
            stats = pd.DataFrame({
                "Indicateur": [
                    "📊 Efficacité (km/m³)",
                    "⏱️ Volume par heure (m³/h)",
                    "📍 Points Collecte 1",
                    "📍 Points Collecte 2",
                    "📦 Volume Collecte 1 (m³)",
                    "📦 Volume Collecte 2 (m³)",
                    "🏆 Volume total (m³)",
                    "📏 Distance totale (km)"
                ],
                "Valeur": [
                    f"{tournee_data.get('efficacite', 0):.2f}" if tournee_data.get('efficacite') else "N/A",
                    f"{tournee_data.get('volume_par_heure', 0):.1f}" if tournee_data.get('volume_par_heure') else "N/A",
                    tournee_data.get('nb_points_1', 0),
                    tournee_data.get('nb_points_2', 0),
                    f"{tournee_data.get('volume1', 0):.1f}",
                    f"{tournee_data.get('volume2', 0):.1f}",
                    f"{tournee_data.get('volume_total', 0):.1f}",
                    f"{tournee_data.get('distance', 0):.1f}"
                ]
            })
            stats.to_excel(writer, sheet_name="Statistiques", index=False)
        
        return output.getvalue()
        
    except Exception as e:
        st.error(f"Erreur lors de l'export: {e}")
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
if 'distance_totale' not in st.session_state:
    st.session_state.distance_totale = 25.0

# Horaires
if 'heure_depot_depart' not in st.session_state:
    st.session_state.heure_depot_depart = time(7, 0)
if 'heure_retour_depot' not in st.session_state:
    st.session_state.heure_retour_depot = time(14, 45)
if 'heure_debut_collecte1' not in st.session_state:
    st.session_state.heure_debut_collecte1 = time(7, 30)
if 'heure_fin_collecte1' not in st.session_state:
    st.session_state.heure_fin_collecte1 = time(9, 30)
if 'heure_depart_decharge1' not in st.session_state:
    st.session_state.heure_depart_decharge1 = time(9, 45)
if 'heure_arrivee_decharge1' not in st.session_state:
    st.session_state.heure_arrivee_decharge1 = time(10, 15)
if 'heure_sortie_decharge1' not in st.session_state:
    st.session_state.heure_sortie_decharge1 = time(10, 45)
if 'heure_debut_collecte2' not in st.session_state:
    st.session_state.heure_debut_collecte2 = time(11, 0)
if 'heure_fin_collecte2' not in st.session_state:
    st.session_state.heure_fin_collecte2 = time(13, 0)
if 'heure_depart_decharge2' not in st.session_state:
    st.session_state.heure_depart_decharge2 = time(13, 15)
if 'heure_arrivee_decharge2' not in st.session_state:
    st.session_state.heure_arrivee_decharge2 = time(13, 45)
if 'heure_sortie_decharge2' not in st.session_state:
    st.session_state.heure_sortie_decharge2 = time(14, 15)

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent de collecte")
    
    agent_nom_input = st.text_input("Votre nom complet", value=st.session_state.agent_nom, 
                                     placeholder="Ex: Alioune Diop")
    if agent_nom_input:
        st.session_state.agent_nom = agent_nom_input
        st.success(f"✅ Connecté: {agent_nom_input}")
    
    st.markdown("---")
    st.markdown("### 📊 Récapitulatif")
    
    if st.session_state.collecte1_validee:
        st.success("✅ Collecte 1 terminée")
    else:
        st.warning("⏳ Collecte 1 en attente")
    
    if st.session_state.collecte2_validee:
        st.success("✅ Collecte 2 terminée")
    else:
        st.warning("⏳ Collecte 2 en attente")
    
    if st.session_state.volume1 > 0:
        st.metric("📦 Volume Collecte 1", f"{st.session_state.volume1:.1f} m³")
    if st.session_state.volume2 > 0:
        st.metric("📦 Volume Collecte 2", f"{st.session_state.volume2:.1f} m³")
    
    total_volume = st.session_state.volume1 + st.session_state.volume2
    if total_volume > 0:
        st.metric("📊 Volume total", f"{total_volume:.1f} m³")
    
    st.markdown("---")
    
    if st.button("📍 ACTIVER LE GPS", use_container_width=True):
        st.session_state.gps_actif = True
        st.success("✅ GPS activé")
    
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF</div>', unsafe_allow_html=True)

# ==================== SECTION COMMUNE ====================
col1, col2 = st.columns(2)
with col1:
    date_tournee = st.date_input("📅 Date", value=st.session_state.date_tournee)
    st.session_state.date_tournee = date_tournee
with col2:
    quartier_nom = st.selectbox("📍 Quartier", [q[1] for q in get_quartiers()])
    st.session_state.quartier_nom = quartier_nom

col1, col2 = st.columns(2)
with col1:
    st.session_state.distance_totale = st.number_input("📏 Distance totale (km)", min_value=0.0, step=0.5, value=st.session_state.distance_totale)
with col2:
    equipe_nom = st.selectbox("👥 Équipe", [e[1] for e in get_equipes()])

# ==================== COLLECTE 1 ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 <strong>COLLECTE 1</strong> - Premier tour</div>', unsafe_allow_html=True)

if not st.session_state.collecte1_validee:
    
    # 1. Départ dépôt
    st.markdown("#### 🏭 1. DÉPART DU DÉPÔT")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_depot_depart = st.time_input("Heure de départ", value=st.session_state.heure_depot_depart, key="depart1")
    with col2:
        if st.button("📍 Enregistrer départ", key="btn_depart1"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_depot", "Départ du dépôt - Collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "depart_depot", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Départ du dépôt"})
                st.success("✅ Départ enregistré")
    
    # 2. Début collecte 1
    st.markdown("#### 🗑️ 2. DÉBUT DE LA COLLECTE 1")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_debut_collecte1 = st.time_input("Heure début collecte", value=st.session_state.heure_debut_collecte1, key="debut_collecte1")
    with col2:
        if st.button("📍 Enregistrer début collecte", key="btn_debut1"):
            pos = get_position()
            if enregistrer_point_gps(None, "debut_collecte", "Début de la collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "debut_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Début collecte 1"})
                st.success("✅ Début collecte enregistré")
    
    # 3. Fin collecte 1
    st.markdown("#### 🗑️ 3. FIN DE LA COLLECTE 1")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_fin_collecte1 = st.time_input("Heure fin collecte", value=st.session_state.heure_fin_collecte1, key="fin_collecte1")
    with col2:
        if st.button("📍 Enregistrer fin collecte", key="btn_fin1"):
            pos = get_position()
            if enregistrer_point_gps(None, "fin_collecte", "Fin de la collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "fin_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Fin collecte 1"})
                st.success("✅ Fin collecte enregistrée")
    
    # 4. Départ vers décharge 1
    st.markdown("#### 🚛 4. DÉPART VERS LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_depart_decharge1 = st.time_input("Heure départ décharge", value=st.session_state.heure_depart_decharge1, key="depart_decharge1")
    with col2:
        if st.button("📍 Enregistrer départ décharge", key="btn_depart_decharge1"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_decharge", "Départ vers décharge 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "depart_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Départ vers décharge 1"})
                st.success("✅ Départ décharge enregistré")
    
    # 5. Arrivée décharge 1
    st.markdown("#### 🏭 5. ARRIVÉE À LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_arrivee_decharge1 = st.time_input("Heure arrivée décharge", value=st.session_state.heure_arrivee_decharge1, key="arrivee_decharge1")
    with col2:
        if st.button("📍 Enregistrer arrivée décharge", key="btn_arrivee_decharge1"):
            pos = get_position()
            if enregistrer_point_gps(None, "arrivee_decharge", "Arrivée décharge 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "arrivee_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Arrivée décharge 1"})
                st.success("✅ Arrivée décharge enregistrée")
    
    # 6. Sortie décharge 1 + Volume
    st.markdown("#### 🏭 6. SORTIE DE LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_sortie_decharge1 = st.time_input("Heure sortie décharge", value=st.session_state.heure_sortie_decharge1, key="sortie_decharge1")
        volume1_input = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key="volume1_input", value=st.session_state.volume1)
    with col2:
        if st.button("📍 Enregistrer sortie + Volume", key="btn_sortie1"):
            pos = get_position()
            if volume1_input > 0:
                if enregistrer_point_gps(None, "sortie_decharge", f"Sortie décharge 1 - Volume: {volume1_input} m³", pos["lat"], pos["lon"], 1):
                    st.session_state.points_gps.append({"type": "sortie_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": f"Sortie décharge 1 - Volume: {volume1_input} m³"})
                    st.session_state.volume1 = volume1_input
                    st.success(f"✅ Sortie décharge enregistrée - Volume: {volume1_input} m³")
            else:
                st.warning("⚠️ Veuillez saisir le volume déchargé")
    
    # 7. Valider Collecte 1
    st.markdown("---")
    if st.button("✅ VALIDER LA COLLECTE 1", type="primary", use_container_width=True):
        if st.session_state.volume1 > 0:
            st.session_state.collecte1_validee = True
            st.success("✅ Collecte 1 validée ! Passez à la Collecte 2")
            st.rerun()
        else:
            st.warning("⚠️ Veuillez enregistrer le volume déchargé")

else:
    st.success("✅ Collecte 1 terminée et validée")
    st.write(f"📦 Volume déchargé: {st.session_state.volume1:.1f} m³")
    if st.button("📝 Modifier Collecte 1", use_container_width=True):
        st.session_state.collecte1_validee = False
        st.rerun()

# ==================== COLLECTE 2 ====================
st.markdown("---")
st.markdown('<div class="collecte2-card">🚛 <strong>COLLECTE 2</strong> - Deuxième tour</div>', unsafe_allow_html=True)

if st.session_state.collecte1_validee and not st.session_state.collecte2_validee:
    
    # 1. Début collecte 2
    st.markdown("#### 🗑️ 1. DÉBUT DE LA COLLECTE 2")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_debut_collecte2 = st.time_input("Heure début collecte 2", value=st.session_state.heure_debut_collecte2, key="debut_collecte2")
    with col2:
        if st.button("📍 Enregistrer début collecte 2", key="btn_debut2"):
            pos = get_position()
            if enregistrer_point_gps(None, "debut_collecte", "Début de la collecte 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "debut_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Début collecte 2"})
                st.success("✅ Début collecte 2 enregistré")
    
    # 2. Fin collecte 2
    st.markdown("#### 🗑️ 2. FIN DE LA COLLECTE 2")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_fin_collecte2 = st.time_input("Heure fin collecte 2", value=st.session_state.heure_fin_collecte2, key="fin_collecte2")
    with col2:
        if st.button("📍 Enregistrer fin collecte 2", key="btn_fin2"):
            pos = get_position()
            if enregistrer_point_gps(None, "fin_collecte", "Fin de la collecte 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "fin_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Fin collecte 2"})
                st.success("✅ Fin collecte 2 enregistrée")
    
    # 3. Départ vers décharge 2
    st.markdown("#### 🚛 3. DÉPART VERS LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_depart_decharge2 = st.time_input("Heure départ décharge 2", value=st.session_state.heure_depart_decharge2, key="depart_decharge2")
    with col2:
        if st.button("📍 Enregistrer départ décharge 2", key="btn_depart_decharge2"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_decharge", "Départ vers décharge 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "depart_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Départ vers décharge 2"})
                st.success("✅ Départ décharge 2 enregistré")
    
    # 4. Arrivée décharge 2
    st.markdown("#### 🏭 4. ARRIVÉE À LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_arrivee_decharge2 = st.time_input("Heure arrivée décharge 2", value=st.session_state.heure_arrivee_decharge2, key="arrivee_decharge2")
    with col2:
        if st.button("📍 Enregistrer arrivée décharge 2", key="btn_arrivee_decharge2"):
            pos = get_position()
            if enregistrer_point_gps(None, "arrivee_decharge", "Arrivée décharge 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "arrivee_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Arrivée décharge 2"})
                st.success("✅ Arrivée décharge 2 enregistrée")
    
    # 5. Sortie décharge 2 + Volume
    st.markdown("#### 🏭 5. SORTIE DE LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_sortie_decharge2 = st.time_input("Heure sortie décharge 2", value=st.session_state.heure_sortie_decharge2, key="sortie_decharge2")
        volume2_input = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key="volume2_input", value=st.session_state.volume2)
    with col2:
        if st.button("📍 Enregistrer sortie + Volume 2", key="btn_sortie2"):
            pos = get_position()
            if volume2_input > 0:
                if enregistrer_point_gps(None, "sortie_decharge", f"Sortie décharge 2 - Volume: {volume2_input} m³", pos["lat"], pos["lon"], 2):
                    st.session_state.points_gps.append({"type": "sortie_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": f"Sortie décharge 2 - Volume: {volume2_input} m³"})
                    st.session_state.volume2 = volume2_input
                    st.success(f"✅ Sortie décharge 2 enregistrée - Volume: {volume2_input} m³")
            else:
                st.warning("⚠️ Veuillez saisir le volume déchargé")
    
    # 6. Retour dépôt
    st.markdown("#### 🏁 6. RETOUR AU DÉPÔT")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_retour_depot = st.time_input("Heure retour dépôt", value=st.session_state.heure_retour_depot, key="retour")
    with col2:
        if st.button("📍 Enregistrer retour", key="btn_retour"):
            pos = get_position()
            if enregistrer_point_gps(None, "retour_depot", "Retour au dépôt", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "retour_depot", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Retour au dépôt"})
                st.success("✅ Retour dépôt enregistré")
    
    # 7. Valider Collecte 2
    st.markdown("---")
    if st.button("✅ VALIDER LA COLLECTE 2", type="primary", use_container_width=True):
        if st.session_state.volume2 > 0:
            st.session_state.collecte2_validee = True
            st.success("✅ Collecte 2 validée ! Tournée terminée")
            
            # Enregistrer dans la base de données
            quartier_id = get_quartier_id(st.session_state.quartier_nom)
            equipe_id = get_equipe_id(equipe_nom)
            
            if quartier_id and equipe_id:
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text("""
                            INSERT INTO tournees (
                                date_tournee, quartier_id, equipe_id, agent_nom,
                                volume_collecte1, volume_collecte2, volume_m3,
                                heure_depot_depart, heure_retour_depot, distance_parcourue_km, statut
                            ) VALUES (
                                :date, :qid, :eid, :agent,
                                :vol1, :vol2, :vol_total,
                                :depart, :retour, :distance, 'termine'
                            )
                            RETURNING id
                        """), {
                            "date": st.session_state.date_tournee,
                            "qid": quartier_id,
                            "eid": equipe_id,
                            "agent": st.session_state.agent_nom,
                            "vol1": st.session_state.volume1,
                            "vol2": st.session_state.volume2,
                            "vol_total": st.session_state.volume1 + st.session_state.volume2,
                            "depart": st.session_state.heure_depot_depart.strftime("%H:%M:%S"),
                            "retour": st.session_state.heure_retour_depot.strftime("%H:%M:%S"),
                            "distance": st.session_state.distance_totale
                        })
                        tournee_id = result.fetchone()[0]
                        
                        for point in st.session_state.points_gps:
                            conn.execute(text("""
                                INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description, collecte_numero)
                                VALUES (:tid, :heure, :type, :lat, :lon, :desc, :collecte)
                            """), {
                                "tid": tournee_id,
                                "heure": datetime.now(),
                                "type": point["type"],
                                "lat": point["lat"],
                                "lon": point["lon"],
                                "desc": point.get("description", ""),
                                "collecte": point["collecte"]
                            })
                        conn.commit()
                    
                    st.balloons()
                    st.success("✅ Tournée enregistrée dans la base de données!")
                except Exception as e:
                    st.error(f"Erreur lors de l'enregistrement: {e}")
            
            st.rerun()
        else:
            st.warning("⚠️ Veuillez enregistrer le volume déchargé")

elif st.session_state.collecte2_validee:
    st.success("✅ Tournée complète terminée !")
    st.write(f"📦 Volume total déchargé: {st.session_state.volume1 + st.session_state.volume2:.1f} m³")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 DÉMARRER UNE NOUVELLE TOURNÉE", use_container_width=True):
            st.session_state.collecte1_validee = False
            st.session_state.collecte2_validee = False
            st.session_state.points_gps = []
            st.session_state.volume1 = 0.0
            st.session_state.volume2 = 0.0
            st.rerun()

# ==================== CARTE INTERACTIVE ====================
st.markdown("---")
st.markdown("### 🗺️ Carte interactive du trajet")

if st.session_state.points_gps:
    df_points = pd.DataFrame(st.session_state.points_gps)
    
    couleurs = {
        "depart_depot": "green",
        "debut_collecte": "blue",
        "fin_collecte": "blue",
        "depart_decharge": "orange",
        "arrivee_decharge": "red",
        "sortie_decharge": "purple",
        "retour_depot": "brown"
    }
    
    noms_points = {
        "depart_depot": "🏭 Départ dépôt",
        "debut_collecte": "🗑️ Début collecte",
        "fin_collecte": "🗑️ Fin collecte",
        "depart_decharge": "🚛 Départ décharge",
        "arrivee_decharge": "🏭 Arrivée décharge",
        "sortie_decharge": "🏭 Sortie décharge",
        "retour_depot": "🏁 Retour dépôt"
    }
    
    df_points["nom_affichage"] = df_points["type"].map(noms_points)
    
    fig = px.scatter_mapbox(
        df_points,
        lat="lat",
        lon="lon",
        color="type",
        hover_name="nom_affichage",
        hover_data={"collecte": True, "type": False},
        color_discrete_map=couleurs,
        zoom=13,
        center={"lat": 15.11, "lon": -16.65},
        title="Trajet de la tournée - Points GPS enregistrés",
        height=500
    )
    
    if len(df_points) > 1:
        fig.add_trace(go.Scattermapbox(
            lat=df_points["lat"].tolist(),
            lon=df_points["lon"].tolist(),
            mode='lines+markers',
            line=dict(width=3, color='blue'),
            marker=dict(size=8, color='blue'),
            name='Trajet',
            showlegend=True
        ))
    
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=12,
        margin={"r": 0, "t": 40, "l": 0, "b": 0}
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("""
    <div class="info-box">
    <strong>📊 Légende des points :</strong><br>
    🟢 Vert - Départ dépôt<br>
    🔵 Bleu - Points de collecte (début/fin)<br>
    🟠 Orange - Départ vers décharge<br>
    🔴 Rouge - Arrivée décharge<br>
    🟣 Violet - Sortie décharge<br>
    🟤 Marron - Retour dépôt<br>
    🔵 Ligne bleue - Trajet effectué
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📋 Détail des points enregistrés"):
        for i, point in enumerate(st.session_state.points_gps):
            st.write(f"{i+1}. {noms_points.get(point['type'], point['type'])} - Collecte {point['collecte']}")
            st.write(f"   📍 {point['lat']:.6f}, {point['lon']:.6f}")
            if point.get("description"):
                st.write(f"   📝 {point['description']}")

# ==================== SECTION EXPORT EXCEL ====================
st.markdown("---")
st.markdown("### 📥 Exporter le rapport")

if st.session_state.collecte2_validee:
    # Préparer les données pour l'export
    total_volume = st.session_state.volume1 + st.session_state.volume2
    
    # Calcul des points par collecte
    nb_points_1 = len([p for p in st.session_state.points_gps if p.get("collecte") == 1])
    nb_points_2 = len([p for p in st.session_state.points_gps if p.get("collecte") == 2])
    
    # Calcul de l'efficacité
    efficacite = st.session_state.distance_totale / total_volume if total_volume > 0 else 0
    
    # Calcul du volume par heure
    try:
        h1 = st.session_state.heure_depot_depart.hour
        m1 = st.session_state.heure_depot_depart.minute
        h2 = st.session_state.heure_retour_depot.hour
        m2 = st.session_state.heure_retour_depot.minute
        duree_heures = (h2 * 60 + m2 - h1 * 60 - m1) / 60
        volume_par_heure = total_volume / duree_heures if duree_heures > 0 else 0
    except:
        volume_par_heure = 0
    
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
        "efficacite": efficacite,
        "volume_par_heure": volume_par_heure,
        "heure_depot_depart": st.session_state.heure_depot_depart.strftime("%H:%M"),
        "heure_retour_depot": st.session_state.heure_retour_depot.strftime("%H:%M"),
        "heure_debut_collecte1": st.session_state.heure_debut_collecte1.strftime("%H:%M"),
        "heure_fin_collecte1": st.session_state.heure_fin_collecte1.strftime("%H:%M"),
        "heure_depart_decharge1": st.session_state.heure_depart_decharge1.strftime("%H:%M"),
        "heure_arrivee_decharge1": st.session_state.heure_arrivee_decharge1.strftime("%H:%M"),
        "heure_sortie_decharge1": st.session_state.heure_sortie_decharge1.strftime("%H:%M"),
        "heure_debut_collecte2": st.session_state.heure_debut_collecte2.strftime("%H:%M"),
        "heure_fin_collecte2": st.session_state.heure_fin_collecte2.strftime("%H:%M"),
        "heure_depart_decharge2": st.session_state.heure_depart_decharge2.strftime("%H:%M"),
        "heure_arrivee_decharge2": st.session_state.heure_arrivee_decharge2.strftime("%H:%M"),
        "heure_sortie_decharge2": st.session_state.heure_sortie_decharge2.strftime("%H:%M")
    }
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 EXPORTER EN EXCEL", use_container_width=True, type="primary"):
            excel_data = exporter_tournee_excel(tournee_data)
            if excel_data:
                st.download_button(
                    label="📊 Télécharger le rapport Excel",
                    data=excel_data,
                    file_name=f"rapport_collecte_{st.session_state.date_tournee.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    with col2:
        # Export CSV rapide
        csv_data = f"""Date,Agent,Quartier,Volume1 (m³),Volume2 (m³),Volume Total (m³),Distance (km),Efficacité (km/m³)
{st.session_state.date_tournee.strftime("%d/%m/%Y")},{st.session_state.agent_nom},{st.session_state.quartier_nom},{st.session_state.volume1},{st.session_state.volume2},{total_volume},{st.session_state.distance_totale},{efficacite:.2f}
"""
        st.download_button(
            label="📄 EXPORTER EN CSV",
            data=csv_data,
            file_name=f"rapport_collecte_{st.session_state.date_tournee.strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📱 Agent: {st.session_state.agent_nom or 'Non connecté'} | GPS: {'Actif' if st.session_state.gps_actif else 'Inactif'} | Commune de Mékhé")
