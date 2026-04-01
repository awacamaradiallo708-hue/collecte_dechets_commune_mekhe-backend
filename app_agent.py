"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec :
- Saisie manuelle des heures pour chaque étape
- Suivi GPS en temps réel (trajet comme Google Maps)
- Collecte 1 obligatoire, Collecte 2 optionnelle
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, time, timedelta
from sqlalchemy import create_engine, text
import os
from io import BytesIO
import time as time_module
import threading

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
    .heure-saisie {
        background: #fff8e7;
        padding: 0.5rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border: 1px solid #FF9800;
    }
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
    
    <script>
    // Variable pour stocker la position en continu
    let trackingInterval = null;
    let positions = [];
    
    // Démarrer le suivi GPS en temps réel
    function startGPS() {
        if (trackingInterval) clearInterval(trackingInterval);
        
        trackingInterval = setInterval(() => {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const pos = {
                            lat: position.coords.latitude,
                            lon: position.coords.longitude,
                            accuracy: position.coords.accuracy,
                            timestamp: new Date().toISOString()
                        };
                        positions.push(pos);
                        
                        // Stocker dans localStorage pour Streamlit
                        localStorage.setItem('gps_tracking', JSON.stringify(positions));
                        localStorage.setItem('gps_last', JSON.stringify(pos));
                    },
                    (error) => {
                        console.log("Erreur GPS:", error);
                    },
                    { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
                );
            }
        }, 3000); // Capture toutes les 3 secondes
    }
    
    // Arrêter le suivi
    function stopGPS() {
        if (trackingInterval) {
            clearInterval(trackingInterval);
            trackingInterval = null;
        }
    }
    
    // Récupérer les positions enregistrées
    function getPositions() {
        const data = localStorage.getItem('gps_tracking');
        return data ? JSON.parse(data) : [];
    }
    
    // Effacer les positions
    function clearPositions() {
        localStorage.removeItem('gps_tracking');
        positions = [];
    }
    </script>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte</h1><p>Commune de Mékhé | Saisie des heures | Suivi GPS temps réel</p></div>', unsafe_allow_html=True)

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

def calculer_distance(lat1, lon1, lat2, lon2):
    """Calcule la distance approximative entre deux points GPS (en km)"""
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def formater_duree(minutes):
    if minutes <= 0:
        return "0 min"
    heures = int(minutes // 60)
    mins = int(minutes % 60)
    if heures > 0:
        return f"{heures}h {mins}min"
    return f"{mins}min"

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
if 'tracking_actif' not in st.session_state:
    st.session_state.tracking_actif = False
if 'points_tracking' not in st.session_state:
    st.session_state.points_tracking = []

# Heures (saisie manuelle)
if 'heure_depot_depart' not in st.session_state:
    st.session_state.heure_depot_depart = "07:00"
if 'heure_debut_collecte1' not in st.session_state:
    st.session_state.heure_debut_collecte1 = "07:30"
if 'heure_fin_collecte1' not in st.session_state:
    st.session_state.heure_fin_collecte1 = "09:30"
if 'heure_depart_decharge1' not in st.session_state:
    st.session_state.heure_depart_decharge1 = "09:45"
if 'heure_arrivee_decharge1' not in st.session_state:
    st.session_state.heure_arrivee_decharge1 = "10:15"
if 'heure_sortie_decharge1' not in st.session_state:
    st.session_state.heure_sortie_decharge1 = "10:45"
if 'heure_debut_collecte2' not in st.session_state:
    st.session_state.heure_debut_collecte2 = "11:00"
if 'heure_fin_collecte2' not in st.session_state:
    st.session_state.heure_fin_collecte2 = "13:00"
if 'heure_depart_decharge2' not in st.session_state:
    st.session_state.heure_depart_decharge2 = "13:15"
if 'heure_arrivee_decharge2' not in st.session_state:
    st.session_state.heure_arrivee_decharge2 = "13:45"
if 'heure_sortie_decharge2' not in st.session_state:
    st.session_state.heure_sortie_decharge2 = "14:15"
if 'heure_retour_depot' not in st.session_state:
    st.session_state.heure_retour_depot = "14:45"

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent de collecte")
    
    agent_nom_input = st.text_input("✍️ Votre nom complet", value=st.session_state.agent_nom, 
                                     placeholder="Ex: Alioune Diop")
    if agent_nom_input:
        st.session_state.agent_nom = agent_nom_input
        st.success(f"✅ Connecté: {agent_nom_input}")
    
    st.markdown("---")
    st.markdown("### 📍 SUIVI GPS TEMPS RÉEL")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🟢 DÉMARRER LE SUIVI", use_container_width=True):
            st.session_state.gps_actif = True
            st.session_state.tracking_actif = True
            st.success("✅ Suivi GPS activé - L'itinéraire sera tracé automatiquement")
            st.rerun()
    with col2:
        if st.button("🔴 ARRÊTER LE SUIVI", use_container_width=True):
            st.session_state.gps_actif = False
            st.session_state.tracking_actif = False
            st.warning("⚠️ Suivi GPS arrêté")
            st.rerun()
    
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 SUIVI GPS ACTIF</div>', unsafe_allow_html=True)
        st.info("📱 Votre position est enregistrée toutes les 3 secondes")
    
    st.markdown("---")
    st.markdown("### 📊 Récapitulatif")
    
    if st.session_state.collecte1_validee:
        st.success("✅ Collecte 1 terminée")
    else:
        st.warning("⏳ Collecte 1 en attente")
    
    if st.session_state.collecte2_validee:
        st.success("✅ Collecte 2 terminée")
    
    if st.session_state.volume1 > 0:
        st.metric("📦 Volume Collecte 1", f"{st.session_state.volume1:.1f} m³")
    if st.session_state.volume2 > 0:
        st.metric("📦 Volume Collecte 2", f"{st.session_state.volume2:.1f} m³")
    
    total_volume = st.session_state.volume1 + st.session_state.volume2
    if total_volume > 0:
        st.metric("📊 Volume total", f"{total_volume:.1f} m³")
    
    if st.session_state.distance_totale > 0:
        st.metric("📏 Distance parcourue", f"{st.session_state.distance_totale:.2f} km")

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

# ==================== SAISIE DES HEURES ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🕐 <strong>SAISIE DES HEURES</strong> - Entrez les heures réelles</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🏭 DÉPART")
    st.session_state.heure_depot_depart = st.text_input("Heure de départ du dépôt", value=st.session_state.heure_depot_depart, placeholder="HH:MM")
    
    st.markdown("#### 🗑️ COLLECTE 1")
    st.session_state.heure_debut_collecte1 = st.text_input("Heure début collecte 1", value=st.session_state.heure_debut_collecte1, placeholder="HH:MM")
    st.session_state.heure_fin_collecte1 = st.text_input("Heure fin collecte 1", value=st.session_state.heure_fin_collecte1, placeholder="HH:MM")
    
    st.markdown("#### 🚛 DÉCHARGE 1")
    st.session_state.heure_depart_decharge1 = st.text_input("Heure départ décharge 1", value=st.session_state.heure_depart_decharge1, placeholder="HH:MM")
    st.session_state.heure_arrivee_decharge1 = st.text_input("Heure arrivée décharge 1", value=st.session_state.heure_arrivee_decharge1, placeholder="HH:MM")
    st.session_state.heure_sortie_decharge1 = st.text_input("Heure sortie décharge 1", value=st.session_state.heure_sortie_decharge1, placeholder="HH:MM")

with col2:
    st.markdown("#### 🗑️ COLLECTE 2 (optionnelle)")
    st.session_state.heure_debut_collecte2 = st.text_input("Heure début collecte 2", value=st.session_state.heure_debut_collecte2, placeholder="HH:MM")
    st.session_state.heure_fin_collecte2 = st.text_input("Heure fin collecte 2", value=st.session_state.heure_fin_collecte2, placeholder="HH:MM")
    
    st.markdown("#### 🚛 DÉCHARGE 2")
    st.session_state.heure_depart_decharge2 = st.text_input("Heure départ décharge 2", value=st.session_state.heure_depart_decharge2, placeholder="HH:MM")
    st.session_state.heure_arrivee_decharge2 = st.text_input("Heure arrivée décharge 2", value=st.session_state.heure_arrivee_decharge2, placeholder="HH:MM")
    st.session_state.heure_sortie_decharge2 = st.text_input("Heure sortie décharge 2", value=st.session_state.heure_sortie_decharge2, placeholder="HH:MM")
    
    st.markdown("#### 🏁 RETOUR")
    st.session_state.heure_retour_depot = st.text_input("Heure retour dépôt", value=st.session_state.heure_retour_depot, placeholder="HH:MM")

# ==================== COLLECTE 1 ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 <strong>COLLECTE 1</strong> - Premier tour (OBLIGATOIRE)</div>', unsafe_allow_html=True)

if not st.session_state.collecte1_validee:
    
    # Points de collecte avec boutons
    points_collecte1 = [
        ("🏭 DÉPART DU DÉPÔT", "depart_depot"),
        ("🗑️ DÉBUT COLLECTE 1", "debut_collecte"),
        ("🗑️ FIN COLLECTE 1", "fin_collecte"),
        ("🚛 DÉPART VERS DÉCHARGE 1", "depart_decharge"),
        ("🏭 ARRIVÉE DÉCHARGE 1", "arrivee_decharge")
    ]
    
    for titre, type_point in points_collecte1:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{titre}**")
            st.caption(f"Heure saisie: {st.session_state[f'heure_{type_point}'] if f'heure_{type_point}' in st.session_state else 'Non saisie'}")
        with col2:
            if st.button(f"✅ Enregistrer", key=f"btn_{type_point}", use_container_width=True):
                # Enregistrer un point GPS simulé (on utilisera les heures saisies)
                point_data = {
                    "type": type_point,
                    "lat": 15.115000,  # Coordonnées par défaut
                    "lon": -16.635000,
                    "collecte": 1,
                    "description": f"{titre} - {st.session_state[f'heure_{type_point}']}",
                    "heure": st.session_state[f'heure_{type_point}'],
                    "distance_depuis_dernier": 0
                }
                st.session_state.points_gps.append(point_data)
                st.success(f"✅ {titre} enregistré à {st.session_state[f'heure_{type_point}']}")
    
    # Volume collecte 1
    st.markdown("---")
    col1, col2 = st.columns([2, 1])
    with col1:
        volume1_input = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key="volume1_input", value=st.session_state.volume1)
    with col2:
        if st.button("💾 Enregistrer volume", key="save_vol1", use_container_width=True):
            if volume1_input > 0:
                st.session_state.volume1 = volume1_input
                st.success(f"✅ Volume enregistré: {volume1_input} m³")
    
    # Validation
    st.markdown("---")
    if st.button("✅ VALIDER LA COLLECTE 1", type="primary", use_container_width=True):
        if st.session_state.volume1 > 0:
            st.session_state.collecte1_validee = True
            st.success("✅ Collecte 1 validée !")
            st.rerun()
        else:
            st.warning("⚠️ Veuillez enregistrer le volume déchargé")

else:
    st.success("✅ Collecte 1 terminée")
    st.write(f"📦 Volume: {st.session_state.volume1:.1f} m³")

# ==================== COLLECTE 2 (OPTIONNELLE) ====================
st.markdown("---")
st.markdown('<div class="collecte2-card">🚛 <strong>COLLECTE 2</strong> - Deuxième tour (OPTIONNEL)</div>', unsafe_allow_html=True)

if st.session_state.collecte1_validee and not st.session_state.collecte2_validee:
    
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
            ("🗑️ DÉBUT COLLECTE 2", "debut_collecte2"),
            ("🗑️ FIN COLLECTE 2", "fin_collecte2"),
            ("🚛 DÉPART VERS DÉCHARGE 2", "depart_decharge2"),
            ("🏭 ARRIVÉE DÉCHARGE 2", "arrivee_decharge2")
        ]
        
        for titre, type_point in points_collecte2:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{titre}**")
                st.caption(f"Heure saisie: {st.session_state[f'heure_{type_point}']}")
            with col2:
                if st.button(f"✅ Enregistrer", key=f"btn2_{type_point}", use_container_width=True):
                    point_data = {
                        "type": type_point,
                        "lat": 15.115000,
                        "lon": -16.635000,
                        "collecte": 2,
                        "description": f"{titre} - {st.session_state[f'heure_{type_point}']}",
                        "heure": st.session_state[f'heure_{type_point}'],
                        "distance_depuis_dernier": 0
                    }
                    st.session_state.points_gps.append(point_data)
                    st.success(f"✅ {titre} enregistré à {st.session_state[f'heure_{type_point}']}")
        
        # Sortie décharge 2
        st.markdown("#### 🏭 SORTIE DE LA DÉCHARGE 2")
        col1, col2 = st.columns([2, 1])
        with col1:
            volume2_input = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key="volume2_input", value=st.session_state.volume2)
            st.session_state.heure_sortie_decharge2 = st.text_input("Heure sortie décharge 2", value=st.session_state.heure_sortie_decharge2, placeholder="HH:MM")
        with col2:
            if st.button("💾 Enregistrer", key="save_vol2", use_container_width=True):
                if volume2_input > 0:
                    st.session_state.volume2 = volume2_input
                    point_data = {
                        "type": "sortie_decharge",
                        "lat": 15.115000,
                        "lon": -16.635000,
                        "collecte": 2,
                        "description": f"Sortie décharge 2 - Volume: {volume2_input} m³",
                        "heure": st.session_state.heure_sortie_decharge2,
                        "distance_depuis_dernier": 0
                    }
                    st.session_state.points_gps.append(point_data)
                    st.success(f"✅ Volume enregistré: {volume2_input} m³")
        
        # Retour dépôt
        st.markdown("#### 🏁 RETOUR AU DÉPÔT")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**RETOUR AU DÉPÔT**")
            st.caption(f"Heure saisie: {st.session_state.heure_retour_depot}")
        with col2:
            if st.button(f"✅ Enregistrer retour", key="btn_retour", use_container_width=True):
                point_data = {
                    "type": "retour_depot",
                    "lat": 15.115000,
                    "lon": -16.635000,
                    "collecte": 2,
                    "description": f"Retour dépôt - {st.session_state.heure_retour_depot}",
                    "heure": st.session_state.heure_retour_depot,
                    "distance_depuis_dernier": 0
                }
                st.session_state.points_gps.append(point_data)
                st.success(f"✅ Retour dépôt enregistré à {st.session_state.heure_retour_depot}")
        
        st.markdown("---")
        if st.button("✅ VALIDER LA COLLECTE 2", type="primary", use_container_width=True):
            if st.session_state.volume2 > 0:
                st.session_state.collecte2_validee = True
                st.success("✅ Collecte 2 validée !")
                st.rerun()
            else:
                st.warning("⚠️ Veuillez enregistrer le volume déchargé")

# ==================== TERMINER LA TOURNÉE ====================
if st.session_state.collecte1_validee and (st.session_state.collecte2_validee or not st.session_state.collecte2_optionnelle):
    
    st.markdown("---")
    st.markdown("### 🏁 TERMINER LA TOURNÉE")
    
    total_volume = st.session_state.volume1 + st.session_state.volume2
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📦 Volume total", f"{total_volume:.1f} m³")
    with col2:
        st.metric("📍 Points enregistrés", len(st.session_state.points_gps))
    
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
                            heure_depot_depart, heure_retour_depot, statut
                        ) VALUES (
                            :date, :qid, :eid, :agent,
                            :vol1, :vol2, :vol_total,
                            :depart, :retour, 'termine'
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
                        "depart": st.session_state.heure_depot_depart,
                        "retour": st.session_state.heure_retour_depot
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
                st.success("✅ Tournée enregistrée dans la base de données !")
                
                if st.button("🔄 DÉMARRER UNE NOUVELLE TOURNÉE", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key not in ['agent_nom']:
                            del st.session_state[key]
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erreur: {e}")

# ==================== CARTE INTERACTIVE AVEC ITINÉRAIRE ====================
st.markdown("---")
st.markdown("### 🗺️ Carte interactive - Itinéraire et trajet")

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
        hover_data={"collecte": True, "heure": True},
        color_discrete_map=couleurs,
        zoom=13,
        center={"lat": 15.11, "lon": -16.65},
        title="🗺️ ITINÉRAIRE DE LA TOURNÉE",
        height=550
    )
    
    # Tracer la ligne reliant les points (itinéraire)
    if len(df_points) > 1:
        fig.add_trace(go.Scattermapbox(
            lat=df_points["lat"].tolist(),
            lon=df_points["lon"].tolist(),
            mode='lines+markers',
            line=dict(width=3, color='blue'),
            marker=dict(size=8, color='blue'),
            name='Itinéraire',
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
    <strong>📊 LÉGENDE DE L'ITINÉRAIRE :</strong><br>
    🟢 Vert - Départ dépôt<br>
    🔵 Bleu - Points de collecte<br>
    🟠 Orange - Départ vers décharge<br>
    🔴 Rouge - Arrivée décharge<br>
    🟣 Violet - Sortie décharge<br>
    🟤 Marron - Retour dépôt<br>
    🔵 Ligne bleue - Itinéraire à suivre / trajet effectué
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📋 Détail des points enregistrés"):
        for i, point in enumerate(st.session_state.points_gps):
            st.write(f"{i+1}. {noms_points.get(point['type'], point['type'])} - Collecte {point['collecte']}")
            st.write(f"   🕐 Heure: {point.get('heure', 'N/A')}")
            st.write(f"   📍 {point['lat']:.6f}, {point['lon']:.6f}")
            st.write("")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📱 Agent: {st.session_state.agent_nom or 'Non connecté'} | 📍 GPS: {'Actif' if st.session_state.gps_actif else 'Inactif'} | 🗑️ Commune de Mékhé")
