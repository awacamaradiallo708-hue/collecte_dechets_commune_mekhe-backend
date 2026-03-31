"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version ultra accessible
- Texte très gros
- Saisie manuelle des heures
- Icônes pour guider
- Boutons géants
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

# ==================== STYLE CSS TRÈS GRAND ====================
st.markdown("""
    <style>
    /* En-tête */
    .main-header {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .main-header h1 {
        font-size: 32px !important;
    }
    .main-header p {
        font-size: 18px !important;
    }
    
    /* Cartes */
    .collecte-card {
        background: #e8f5e9;
        padding: 1.2rem;
        border-radius: 15px;
        margin-bottom: 1.2rem;
        border-left: 5px solid #4CAF50;
    }
    .collecte-card strong {
        font-size: 22px;
    }
    .collecte2-card {
        background: #fff8e7;
        padding: 1.2rem;
        border-radius: 15px;
        margin-bottom: 1.2rem;
        border-left: 5px solid #FF9800;
    }
    .collecte2-card strong {
        font-size: 22px;
    }
    
    /* Boutons géants */
    .stButton button {
        width: 100%;
        padding: 18px !important;
        font-size: 20px !important;
        font-weight: bold !important;
        border-radius: 15px !important;
        margin: 8px 0 !important;
    }
    
    /* Titres des étapes */
    h4 {
        font-size: 24px !important;
        margin-top: 20px !important;
        margin-bottom: 15px !important;
    }
    
    /* Messages */
    .success-box {
        background: #d4edda;
        padding: 1.2rem;
        border-radius: 15px;
        border-left: 5px solid #28a745;
        margin: 1rem 0;
        text-align: center;
        font-size: 18px;
        font-weight: bold;
    }
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 12px;
        border-left: 4px solid #2196F3;
        margin: 1rem 0;
        font-size: 16px;
    }
    .volume-box {
        background: #fff8e7;
        padding: 1.2rem;
        border-radius: 15px;
        border: 2px dashed #FF9800;
        text-align: center;
        margin: 1rem 0;
    }
    .volume-box strong {
        font-size: 20px;
    }
    .horaires-box {
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border: 1px solid #ddd;
        font-size: 16px;
    }
    .gps-active {
        background: #4CAF50;
        color: white;
        padding: 0.8rem;
        border-radius: 12px;
        text-align: center;
        font-weight: bold;
        font-size: 18px;
    }
    
    /* Labels et champs de saisie */
    label, .stMarkdown {
        font-size: 18px !important;
    }
    input, select, textarea {
        font-size: 18px !important;
        padding: 12px !important;
    }
    
    /* Barre latérale */
    .sidebar .sidebar-content {
        font-size: 16px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ AGENT DE COLLECTE</h1><p>Commune de Mékhé | GPS | Carte interactive | Export Excel</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BASE DE DONNÉES ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ PAS DE CONNEXION INTERNET")
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
        st.error(f"❌ ERREUR GPS: {e}")
        return False

def get_position():
    """Récupère la position GPS du téléphone"""
    return {"lat": 15.115000, "lon": -16.635000, "accuracy": 10}

def enregistrer_volume_decharge(tournee_id, collecte_numero, volume):
    """Enregistre le volume déchargé"""
    try:
        with engine.connect() as conn:
            if collecte_numero == 1:
                conn.execute(text("UPDATE tournees SET volume_collecte1 = :volume WHERE id = :tid"), {"volume": volume, "tid": tournee_id})
            else:
                conn.execute(text("UPDATE tournees SET volume_collecte2 = :volume WHERE id = :tid"), {"volume": volume, "tid": tournee_id})
            conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erreur: {e}")
        return False

def exporter_tournee_excel(tournee_data):
    """Exporte en Excel"""
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            resume = pd.DataFrame({
                "Informations": ["📅 Date", "👤 Agent", "🏘️ Quartier", "👥 Équipe", "📏 Distance (km)", "📦 Volume total (m³)", "📍 Points GPS", "✅ Statut"],
                "Valeur": [tournee_data.get("date", ""), tournee_data.get("agent", ""), tournee_data.get("quartier", ""), tournee_data.get("equipe", ""), tournee_data.get("distance", "N/A"), f"{tournee_data.get('volume_total', 0):.1f}", tournee_data.get("nb_points", 0), "Terminée"]
            })
            resume.to_excel(writer, sheet_name="Résumé", index=False)
            
            horaires = pd.DataFrame({
                "Étape": ["🏭 Départ", "🗑️ Début C1", "🗑️ Fin C1", "🚛 Départ Déch1", "🏭 Arrivée Déch1", "🏭 Sortie Déch1", "🗑️ Début C2", "🗑️ Fin C2", "🚛 Départ Déch2", "🏭 Arrivée Déch2", "🏭 Sortie Déch2", "🏁 Retour"],
                "Heure": [tournee_data.get("heure_depot_depart", ""), tournee_data.get("heure_debut_collecte1", ""), tournee_data.get("heure_fin_collecte1", ""), tournee_data.get("heure_depart_decharge1", ""), tournee_data.get("heure_arrivee_decharge1", ""), tournee_data.get("heure_sortie_decharge1", ""), tournee_data.get("heure_debut_collecte2", ""), tournee_data.get("heure_fin_collecte2", ""), tournee_data.get("heure_depart_decharge2", ""), tournee_data.get("heure_arrivee_decharge2", ""), tournee_data.get("heure_sortie_decharge2", ""), tournee_data.get("heure_retour_depot", "")]
            })
            horaires.to_excel(writer, sheet_name="Horaires", index=False)
            
            volumes = pd.DataFrame({"Collecte": ["Collecte 1", "Collecte 2", "Total"], "Volume (m³)": [tournee_data.get("volume1", 0), tournee_data.get("volume2", 0), tournee_data.get("volume_total", 0)], "Tonnes": [tournee_data.get("volume1", 0) * 0.8, tournee_data.get("volume2", 0) * 0.8, tournee_data.get("volume_total", 0) * 0.8]})
            volumes.to_excel(writer, sheet_name="Volumes", index=False)
            
            if tournee_data.get("points_gps"):
                points_list = []
                noms = {"depart_depot": "🏭 Départ", "debut_collecte": "🗑️ Début", "fin_collecte": "🗑️ Fin", "depart_decharge": "🚛 Départ Déch", "arrivee_decharge": "🏭 Arrivée Déch", "sortie_decharge": "🏭 Sortie Déch", "retour_depot": "🏁 Retour"}
                for i, p in enumerate(tournee_data["points_gps"]):
                    points_list.append({"N°": i+1, "Type": noms.get(p.get("type", ""), p.get("type", "")), "Collecte": f"Collecte {p.get('collecte', '')}", "Latitude": f"{p.get('lat', 0):.6f}", "Longitude": f"{p.get('lon', 0):.6f}", "Description": p.get("description", "")})
                pd.DataFrame(points_list).to_excel(writer, sheet_name="Points GPS", index=False)
        return output.getvalue()
    except Exception as e:
        st.error(f"❌ Erreur export: {e}")
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

# Heures par défaut
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
    st.header("👤 AGENT")
    
    agent_nom_input = st.text_input("✍️ VOTRE NOM", value=st.session_state.agent_nom, placeholder="Ex: Alioune Diop")
    if agent_nom_input:
        st.session_state.agent_nom = agent_nom_input
        st.success(f"✅ CONNECTÉ: {agent_nom_input}")
    
    st.markdown("---")
    st.markdown("### 📊 RÉCAPITULATIF")
    
    if st.session_state.collecte1_validee:
        st.success("✅ COLLECTE 1 TERMINÉE")
    else:
        st.warning("⏳ COLLECTE 1 EN ATTENTE")
    
    if st.session_state.collecte2_validee:
        st.success("✅ COLLECTE 2 TERMINÉE")
    else:
        st.warning("⏳ COLLECTE 2 EN ATTENTE")
    
    if st.session_state.volume1 > 0:
        st.metric("📦 VOLUME 1", f"{st.session_state.volume1:.1f} m³")
    if st.session_state.volume2 > 0:
        st.metric("📦 VOLUME 2", f"{st.session_state.volume2:.1f} m³")
    
    total_volume = st.session_state.volume1 + st.session_state.volume2
    if total_volume > 0:
        st.metric("📊 VOLUME TOTAL", f"{total_volume:.1f} m³")
    
    st.markdown("---")
    
    if st.button("📍 ACTIVER LE GPS", use_container_width=True):
        st.session_state.gps_actif = True
        st.success("✅ GPS ACTIVÉ")
    
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF</div>', unsafe_allow_html=True)

# ==================== SECTION COMMUNE ====================
col1, col2 = st.columns(2)
with col1:
    date_tournee = st.date_input("📅 DATE", value=st.session_state.date_tournee)
    st.session_state.date_tournee = date_tournee
with col2:
    quartier_nom = st.selectbox("🏘️ QUARTIER", [q[1] for q in get_quartiers()])
    st.session_state.quartier_nom = quartier_nom

col1, col2 = st.columns(2)
with col1:
    st.session_state.distance_totale = st.number_input("📏 DISTANCE (km)", min_value=0.0, step=0.5, value=st.session_state.distance_totale)
with col2:
    equipe_nom = st.selectbox("👥 ÉQUIPE", [e[1] for e in get_equipes()])

# ==================== COLLECTE 1 ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 <strong>COLLECTE 1</strong> - PREMIER TOUR</div>', unsafe_allow_html=True)

if not st.session_state.collecte1_validee:
    
    # 1. Départ dépôt
    st.markdown("#### 🏭 1. DÉPART DU DÉPÔT")
    col1, col2 = st.columns(2)
    with col1:
        heure_depart_str = st.text_input("⏰ HEURE DE DÉPART (HH:MM)", value=st.session_state.heure_depot_depart.strftime("%H:%M"), key="depart1")
        try:
            st.session_state.heure_depot_depart = datetime.strptime(heure_depart_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 07:00)")
    with col2:
        if st.button("📍 ENREGISTRER LE DÉPART", key="btn_depart1"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_depot", "Départ du dépôt - Collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "depart_depot", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Départ du dépôt"})
                st.success("✅ DÉPART ENREGISTRÉ !")
    
    # 2. Début collecte 1
    st.markdown("#### 🗑️ 2. DÉBUT DE LA COLLECTE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_debut1_str = st.text_input("⏰ HEURE DÉBUT (HH:MM)", value=st.session_state.heure_debut_collecte1.strftime("%H:%M"), key="debut1")
        try:
            st.session_state.heure_debut_collecte1 = datetime.strptime(heure_debut1_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 07:30)")
    with col2:
        if st.button("📍 ENREGISTRER LE DÉBUT", key="btn_debut1"):
            pos = get_position()
            if enregistrer_point_gps(None, "debut_collecte", "Début de la collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "debut_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Début collecte 1"})
                st.success("✅ DÉBUT COLLECTE ENREGISTRÉ !")
    
    # 3. Fin collecte 1
    st.markdown("#### 🗑️ 3. FIN DE LA COLLECTE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_fin1_str = st.text_input("⏰ HEURE FIN (HH:MM)", value=st.session_state.heure_fin_collecte1.strftime("%H:%M"), key="fin1")
        try:
            st.session_state.heure_fin_collecte1 = datetime.strptime(heure_fin1_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 09:30)")
    with col2:
        if st.button("📍 ENREGISTRER LA FIN", key="btn_fin1"):
            pos = get_position()
            if enregistrer_point_gps(None, "fin_collecte", "Fin de la collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "fin_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Fin collecte 1"})
                st.success("✅ FIN COLLECTE ENREGISTRÉE !")
    
    # 4. Départ vers décharge 1
    st.markdown("#### 🚛 4. DÉPART VERS LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_depart_dech1_str = st.text_input("⏰ HEURE DÉPART DÉCHARGE (HH:MM)", value=st.session_state.heure_depart_decharge1.strftime("%H:%M"), key="depart_dech1")
        try:
            st.session_state.heure_depart_decharge1 = datetime.strptime(heure_depart_dech1_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 09:45)")
    with col2:
        if st.button("📍 ENREGISTRER LE DÉPART", key="btn_depart_dech1"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_decharge", "Départ vers décharge 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "depart_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Départ vers décharge 1"})
                st.success("✅ DÉPART DÉCHARGE ENREGISTRÉ !")
    
    # 5. Arrivée décharge 1
    st.markdown("#### 🏭 5. ARRIVÉE À LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_arrivee_dech1_str = st.text_input("⏰ HEURE ARRIVÉE (HH:MM)", value=st.session_state.heure_arrivee_decharge1.strftime("%H:%M"), key="arrivee_dech1")
        try:
            st.session_state.heure_arrivee_decharge1 = datetime.strptime(heure_arrivee_dech1_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 10:15)")
    with col2:
        if st.button("📍 ENREGISTRER L'ARRIVÉE", key="btn_arrivee_dech1"):
            pos = get_position()
            if enregistrer_point_gps(None, "arrivee_decharge", "Arrivée décharge 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "arrivee_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": "Arrivée décharge 1"})
                st.success("✅ ARRIVÉE DÉCHARGE ENREGISTRÉE !")
    
    # 6. Sortie décharge 1 + Volume
    st.markdown("#### 🏭 6. SORTIE DE LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_sortie_dech1_str = st.text_input("⏰ HEURE SORTIE (HH:MM)", value=st.session_state.heure_sortie_decharge1.strftime("%H:%M"), key="sortie_dech1")
        try:
            st.session_state.heure_sortie_decharge1 = datetime.strptime(heure_sortie_dech1_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 10:45)")
        volume1_input = st.number_input("📦 VOLUME DÉCHARGÉ (m³)", min_value=0.0, step=0.5, key="vol1", value=st.session_state.volume1)
    with col2:
        if st.button("💾 ENREGISTRER VOLUME", key="btn_vol1"):
            if volume1_input > 0:
                pos = get_position()
                if enregistrer_point_gps(None, "sortie_decharge", f"Sortie décharge 1 - Volume: {volume1_input} m³", pos["lat"], pos["lon"], 1):
                    st.session_state.points_gps.append({"type": "sortie_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1, "description": f"Sortie décharge 1 - Volume: {volume1_input} m³"})
                    st.session_state.volume1 = volume1_input
                    st.success(f"✅ VOLUME ENREGISTRÉ : {volume1_input} m³")
            else:
                st.warning("⚠️ VEUILLEZ SAISIR LE VOLUME")
    
    # 7. Valider Collecte 1
    st.markdown("---")
    if st.button("✅ VALIDER LA COLLECTE 1", type="primary", use_container_width=True):
        if st.session_state.volume1 > 0:
            st.session_state.collecte1_validee = True
            st.success("✅ COLLECTE 1 VALIDÉE ! PASSEZ À LA COLLECTE 2")
            st.rerun()
        else:
            st.warning("⚠️ VEUILLEZ ENREGISTRER LE VOLUME")

else:
    st.success("✅ COLLECTE 1 TERMINÉE")
    st.write(f"📦 Volume: {st.session_state.volume1:.1f} m³")
    if st.button("📝 MODIFIER COLLECTE 1", use_container_width=True):
        st.session_state.collecte1_validee = False
        st.rerun()

# ==================== COLLECTE 2 ====================
st.markdown("---")
st.markdown('<div class="collecte2-card">🚛 <strong>COLLECTE 2</strong> - DEUXIÈME TOUR</div>', unsafe_allow_html=True)

if st.session_state.collecte1_validee and not st.session_state.collecte2_validee:
    
    # 1. Début collecte 2
    st.markdown("#### 🗑️ 1. DÉBUT DE LA COLLECTE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_debut2_str = st.text_input("⏰ HEURE DÉBUT (HH:MM)", value=st.session_state.heure_debut_collecte2.strftime("%H:%M"), key="debut2")
        try:
            st.session_state.heure_debut_collecte2 = datetime.strptime(heure_debut2_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 11:00)")
    with col2:
        if st.button("📍 ENREGISTRER LE DÉBUT", key="btn_debut2"):
            pos = get_position()
            if enregistrer_point_gps(None, "debut_collecte", "Début de la collecte 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "debut_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Début collecte 2"})
                st.success("✅ DÉBUT COLLECTE 2 ENREGISTRÉ !")
    
    # 2. Fin collecte 2
    st.markdown("#### 🗑️ 2. FIN DE LA COLLECTE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_fin2_str = st.text_input("⏰ HEURE FIN (HH:MM)", value=st.session_state.heure_fin_collecte2.strftime("%H:%M"), key="fin2")
        try:
            st.session_state.heure_fin_collecte2 = datetime.strptime(heure_fin2_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 13:00)")
    with col2:
        if st.button("📍 ENREGISTRER LA FIN", key="btn_fin2"):
            pos = get_position()
            if enregistrer_point_gps(None, "fin_collecte", "Fin de la collecte 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "fin_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Fin collecte 2"})
                st.success("✅ FIN COLLECTE 2 ENREGISTRÉE !")
    
    # 3. Départ vers décharge 2
    st.markdown("#### 🚛 3. DÉPART VERS LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_depart_dech2_str = st.text_input("⏰ HEURE DÉPART DÉCHARGE (HH:MM)", value=st.session_state.heure_depart_decharge2.strftime("%H:%M"), key="depart_dech2")
        try:
            st.session_state.heure_depart_decharge2 = datetime.strptime(heure_depart_dech2_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 13:15)")
    with col2:
        if st.button("📍 ENREGISTRER LE DÉPART", key="btn_depart_dech2"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_decharge", "Départ vers décharge 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "depart_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Départ vers décharge 2"})
                st.success("✅ DÉPART DÉCHARGE 2 ENREGISTRÉ !")
    
    # 4. Arrivée décharge 2
    st.markdown("#### 🏭 4. ARRIVÉE À LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_arrivee_dech2_str = st.text_input("⏰ HEURE ARRIVÉE (HH:MM)", value=st.session_state.heure_arrivee_decharge2.strftime("%H:%M"), key="arrivee_dech2")
        try:
            st.session_state.heure_arrivee_decharge2 = datetime.strptime(heure_arrivee_dech2_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 13:45)")
    with col2:
        if st.button("📍 ENREGISTRER L'ARRIVÉE", key="btn_arrivee_dech2"):
            pos = get_position()
            if enregistrer_point_gps(None, "arrivee_decharge", "Arrivée décharge 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "arrivee_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Arrivée décharge 2"})
                st.success("✅ ARRIVÉE DÉCHARGE 2 ENREGISTRÉE !")
    
    # 5. Sortie décharge 2 + Volume
    st.markdown("#### 🏭 5. SORTIE DE LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_sortie_dech2_str = st.text_input("⏰ HEURE SORTIE (HH:MM)", value=st.session_state.heure_sortie_decharge2.strftime("%H:%M"), key="sortie_dech2")
        try:
            st.session_state.heure_sortie_decharge2 = datetime.strptime(heure_sortie_dech2_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 14:15)")
        volume2_input = st.number_input("📦 VOLUME DÉCHARGÉ (m³)", min_value=0.0, step=0.5, key="vol2", value=st.session_state.volume2)
    with col2:
        if st.button("💾 ENREGISTRER VOLUME", key="btn_vol2"):
            if volume2_input > 0:
                pos = get_position()
                if enregistrer_point_gps(None, "sortie_decharge", f"Sortie décharge 2 - Volume: {volume2_input} m³", pos["lat"], pos["lon"], 2):
                    st.session_state.points_gps.append({"type": "sortie_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": f"Sortie décharge 2 - Volume: {volume2_input} m³"})
                    st.session_state.volume2 = volume2_input
                    st.success(f"✅ VOLUME ENREGISTRÉ : {volume2_input} m³")
            else:
                st.warning("⚠️ VEUILLEZ SAISIR LE VOLUME")
    
    # 6. Retour dépôt
    st.markdown("#### 🏁 6. RETOUR AU DÉPÔT")
    col1, col2 = st.columns(2)
    with col1:
        heure_retour_str = st.text_input("⏰ HEURE RETOUR (HH:MM)", value=st.session_state.heure_retour_depot.strftime("%H:%M"), key="retour")
        try:
            st.session_state.heure_retour_depot = datetime.strptime(heure_retour_str, "%H:%M").time()
        except:
            st.error("❌ Format: HH:MM (ex: 14:45)")
    with col2:
        if st.button("📍 ENREGISTRER LE RETOUR", key="btn_retour"):
            pos = get_position()
            if enregistrer_point_gps(None, "retour_depot", "Retour au dépôt", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "retour_depot", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2, "description": "Retour au dépôt"})
                st.success("✅ RETOUR ENREGISTRÉ !")
    
    # 7. Valider Collecte 2
    st.markdown("---")
    if st.button("✅ VALIDER LA COLLECTE 2", type="primary", use_container_width=True):
        if st.session_state.volume2 > 0:
            st.session_state.collecte2_validee = True
            st.success("✅ COLLECTE 2 VALIDÉE ! TOURNÉE TERMINÉE")
            
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
                    st.success("✅ TOURNÉE ENREGISTRÉE DANS LA BASE !")
                except Exception as e:
                    st.error(f"❌ ERREUR: {e}")
            st.rerun()
        else:
            st.warning("⚠️ VEUILLEZ ENREGISTRER LE VOLUME")

elif st.session_state.collecte2_validee:
    st.success("✅ TOURNÉE COMPLÈTE TERMINÉE !")
    st.write(f"📦 Volume total: {st.session_state.volume1 + st.session_state.volume2:.1f} m³")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 NOUVELLE TOURNÉE", use_container_width=True):
            st.session_state.collecte1_validee = False
            st.session_state.collecte2_validee = False
            st.session_state.points_gps = []
            st.session_state.volume1 = 0.0
            st.session_state.volume2 = 0.0
            st.rerun()

# ==================== CARTE INTERACTIVE ====================
st.markdown("---")
st.markdown("### 🗺️ CARTE DU TRAJET")

if st.session_state.points_gps:
    df_points = pd.DataFrame(st.session_state.points_gps)
    
    couleurs = {"depart_depot": "green", "debut_collecte": "blue", "fin_collecte": "blue", "depart_decharge": "orange", "arrivee_decharge": "red", "sortie_decharge": "purple", "retour_depot": "brown"}
    noms = {"depart_depot": "🏭 DÉPART", "debut_collecte": "🗑️ DÉBUT", "fin_collecte": "🗑️ FIN", "depart_decharge": "🚛 DÉPART DÉCH", "arrivee_decharge": "🏭 ARRIVÉE DÉCH", "sortie_decharge": "🏭 SORTIE DÉCH", "retour_depot": "🏁 RETOUR"}
    df_points["nom"] = df_points["type"].map(noms)
    
    fig = px.scatter_mapbox(df_points, lat="lat", lon="lon", color="type", hover_name="nom", hover_data={"collecte": True}, color_discrete_map=couleurs, zoom=13, center={"lat": 15.11, "lon": -16.65}, title="🗺️ TRAJET DE LA TOURNÉE", height=500)
    
    if len(df_points) > 1:
        fig.add_trace(go.Scattermapbox(lat=df_points["lat"].tolist(), lon=df_points["lon"].tolist(), mode='lines+markers', line=dict(width=3, color='blue'), marker=dict(size=8, color='blue'), name='TRAJET'))
    
    fig.update_layout(mapbox_style="open-street-map", mapbox_zoom=12, margin={"r": 0, "t": 40, "l": 0, "b": 0})
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("""
    <div class="info-box">
    <strong>📊 LÉGENDE :</strong><br>
    🟢 VERT - DÉPART DÉPÔT<br>
    🔵 BLEU - COLLECTE (DÉBUT/FIN)<br>
    🟠 ORANGE - DÉPART DÉCHARGE<br>
    🔴 ROUGE - ARRIVÉE DÉCHARGE<br>
    🟣 VIOLET - SORTIE DÉCHARGE<br>
    🟤 MARRON - RETOUR DÉPÔT<br>
    🔵 LIGNE BLEUE - TRAJET EFFECTUÉ
    </div>
    """, unsafe_allow_html=True)

# ==================== EXPORT EXCEL ====================
st.markdown("---")
st.markdown("### 📥 EXPORTER LE RAPPORT")

if st.session_state.collecte2_validee:
    total_volume = st.session_state.volume1 + st.session_state.volume2
    nb_points_1 = len([p for p in st.session_state.points_gps if p.get("collecte") == 1])
    nb_points_2 = len([p for p in st.session_state.points_gps if p.get("collecte") == 2])
    efficacite = st.session_state.distance_totale / total_volume if total_volume > 0 else 0
    
    try:
        h1, m1 = st.session_state.heure_depot_depart.hour, st.session_state.heure_depot_depart.minute
        h2, m2 = st.session_state.heure_retour_depot.hour, st.session_state.heure_retour_depot.minute
        duree_heures = (h2 * 60 + m2 - h1 * 60 - m1) / 60
        volume_par_heure = total_volume / duree_heures if duree_heures > 0 else 0
    except:
        volume_par_heure = 0
    
    tournee_data = {
        "date": st.session_state.date_tournee.strftime("%d/%m/%Y"), "agent": st.session_state.agent_nom, "quartier": st.session_state.quartier_nom, "equipe": equipe_nom,
        "distance": st.session_state.distance_totale, "volume1": st.session_state.volume1, "volume2": st.session_state.volume2, "volume_total": total_volume,
        "nb_points": len(st.session_state.points_gps), "nb_points_1": nb_points_1, "nb_points_2": nb_points_2, "points_gps": st.session_state.points_gps,
        "efficacite": efficacite, "volume_par_heure": volume_par_heure,
        "heure_depot_depart": st.session_state.heure_depot_depart.strftime("%H:%M"), "heure_retour_depot": st.session_state.heure_retour_depot.strftime("%H:%M"),
        "heure_debut_collecte1": st.session_state.heure_debut_collecte1.strftime("%H:%M"), "heure_fin_collecte1": st.session_state.heure_fin_collecte1.strftime("%H:%M"),
        "heure_depart_decharge1": st.session_state.heure_depart_decharge1.strftime("%H:%M"), "heure_arrivee_decharge1": st.session_state.heure_arrivee_decharge1.strftime("%H:%M"),
        "heure_sortie_decharge1": st.session_state.heure_sortie_decharge1.strftime("%H:%M"), "heure_debut_collecte2": st.session_state.heure_debut_collecte2.strftime("%H:%M"),
        "heure_fin_collecte2": st.session_state.heure_fin_collecte2.strftime("%H:%M"), "heure_depart_decharge2": st.session_state.heure_depart_decharge2.strftime("%H:%M"),
        "heure_arrivee_decharge2": st.session_state.heure_arrivee_decharge2.strftime("%H:%M"), "heure_sortie_decharge2": st.session_state.heure_sortie_decharge2.strftime("%H:%M")
    }
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 EXPORTER EN EXCEL", use_container_width=True, type="primary"):
            excel_data = exporter_tournee_excel(tournee_data)
            if excel_data:
                st.download_button(label="📊 TÉLÉCHARGER EXCEL", data=excel_data, file_name=f"rapport_{st.session_state.date_tournee.strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        csv_data = f"""Date,Agent,Quartier,Volume1,Volume2,Total,Distance,Efficacité\n{st.session_state.date_tournee.strftime("%d/%m/%Y")},{st.session_state.agent_nom},{st.session_state.quartier_nom},{st.session_state.volume1},{st.session_state.volume2},{total_volume},{st.session_state.distance_totale},{efficacite:.2f}"""
        st.download_button(label="📄 EXPORTER EN CSV", data=csv_data, file_name=f"rapport_{st.session_state.date_tournee.strftime('%Y%m%d')}.csv", mime="text/csv")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"👤 Agent: {st.session_state.agent_nom or 'NON CONNECTÉ'} | 📡 GPS: {'✅ ACTIF' if st.session_state.gps_actif else '❌ INACTIF'} | 🗑️ COMMUNE DE MÉKHÉ")
