"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec GPS réel via streamlit-js-eval (corrigée)
- Une seule demande de position par bouton "Actualiser GPS"
- Stockage de la position en session
- Tracé de l'itinéraire
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from io import BytesIO
import time as time_module

try:
    from streamlit_js_eval import get_geolocation
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    st.warning("⚠️ streamlit-js-eval non installé. Installez-le avec: pip install streamlit-js-eval")

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
    }
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte</h1><p>Commune de Mékhé | GPS réel | Tracé d\'itinéraire</p></div>', unsafe_allow_html=True)

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
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def get_current_gps():
    """Appelle get_geolocation une seule fois et retourne la position."""
    if not GPS_AVAILABLE:
        return None
    try:
        geolocation = get_geolocation()
        if geolocation and 'coords' in geolocation:
            return {
                "lat": geolocation['coords']['latitude'],
                "lon": geolocation['coords']['longitude'],
                "accuracy": geolocation['coords'].get('accuracy', 100)
            }
        return None
    except Exception as e:
        st.error(f"Erreur GPS: {e}")
        return None

# ==================== SESSION STATE ====================
defaults = {
    'agent_nom': "",
    'tournee_id': None,
    'date_tournee': date.today(),
    'quartier_nom': "",
    'volume1': 0.0,
    'volume2': 0.0,
    'points_gps': [],
    'collecte1_validee': False,
    'collecte2_validee': False,
    'collecte2_optionnelle': False,
    'derniere_position': None,
    'distance_totale': 0.0,
    'heure_depot_depart': "07:00",
    'heure_debut_collecte1': "07:30",
    'heure_fin_collecte1': "09:30",
    'heure_depart_decharge1': "09:45",
    'heure_arrivee_decharge1': "10:15",
    'heure_sortie_decharge1': "10:45",
    'heure_debut_collecte2': "11:00",
    'heure_fin_collecte2': "13:00",
    'heure_depart_decharge2': "13:15",
    'heure_arrivee_decharge2': "13:45",
    'heure_sortie_decharge2': "14:15",
    'heure_retour_depot': "14:45",
    'temps_debut_tournee': None,
    'gps_actif': False,
    'current_gps': None   # Stocke la dernière position GPS obtenue
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent de collecte")
    agent_nom_input = st.text_input("✍️ Votre nom", value=st.session_state.agent_nom, placeholder="Ex: Alioune Diop")
    if agent_nom_input:
        st.session_state.agent_nom = agent_nom_input
        st.success(f"✅ Connecté: {agent_nom_input}")
    
    st.markdown("---")
    st.markdown("### 📍 GPS")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎯 ACTIVER GPS", use_container_width=True):
            st.session_state.gps_actif = True
            st.success("✅ GPS activé")
            st.rerun()
    with col2:
        if st.button("⏸️ DÉSACTIVER", use_container_width=True):
            st.session_state.gps_actif = False
            st.info("GPS désactivé")
            st.rerun()
    
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF</div>', unsafe_allow_html=True)
        # Bouton pour actualiser la position
        if st.button("📍 ACTUALISER MA POSITION", use_container_width=True):
            pos = get_current_gps()
            if pos:
                st.session_state.current_gps = pos
                st.success(f"✅ Position mise à jour : {pos['lat']:.6f}, {pos['lon']:.6f} (précision {pos['accuracy']:.0f} m)")
            else:
                st.error("❌ Impossible d'obtenir la position. Vérifiez les permissions.")
        # Afficher la position actuelle stockée
        if st.session_state.current_gps:
            st.metric("📍 Latitude", f"{st.session_state.current_gps['lat']:.6f}")
            st.metric("📍 Longitude", f"{st.session_state.current_gps['lon']:.6f}")
            st.caption(f"🎯 Précision: {st.session_state.current_gps['accuracy']:.0f} m")
        else:
            st.info("Cliquez sur 'Actualiser ma position' pour obtenir votre position GPS.")
    else:
        st.info("GPS désactivé. Les coordonnées du quartier seront utilisées.")
    
    st.markdown("---")
    st.markdown("### 📊 Récapitulatif")
    if st.session_state.collecte1_validee:
        st.success("✅ Collecte 1 terminée")
    else:
        st.warning("⏳ Collecte 1 en attente")
    if st.session_state.volume1 > 0:
        st.metric("📦 Volume 1", f"{st.session_state.volume1:.1f} m³")
    if st.session_state.volume2 > 0:
        st.metric("📦 Volume 2", f"{st.session_state.volume2:.1f} m³")
    if st.session_state.distance_totale > 0:
        st.metric("📏 Distance", f"{st.session_state.distance_totale:.2f} km")

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
    if st.button("🚀 DÉMARRER", type="primary", use_container_width=True):
        st.session_state.temps_debut_tournee = datetime.now()
        st.success("✅ Tournée démarrée")

# ==================== SAISIE DES HEURES ====================
st.markdown("---")
st.markdown("### 🕐 SAISIE DES HEURES")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**🏭 DÉPART**")
    st.session_state.heure_depot_depart = st.text_input("Départ dépôt", value=st.session_state.heure_depot_depart)
    
    st.markdown("**🗑️ COLLECTE 1**")
    st.session_state.heure_debut_collecte1 = st.text_input("Début collecte 1", value=st.session_state.heure_debut_collecte1)
    st.session_state.heure_fin_collecte1 = st.text_input("Fin collecte 1", value=st.session_state.heure_fin_collecte1)
    
    st.markdown("**🚛 DÉCHARGE 1**")
    st.session_state.heure_depart_decharge1 = st.text_input("Départ décharge 1", value=st.session_state.heure_depart_decharge1)
    st.session_state.heure_arrivee_decharge1 = st.text_input("Arrivée décharge 1", value=st.session_state.heure_arrivee_decharge1)
    st.session_state.heure_sortie_decharge1 = st.text_input("Sortie décharge 1", value=st.session_state.heure_sortie_decharge1)

with col2:
    st.markdown("**🗑️ COLLECTE 2** (optionnel)")
    st.session_state.heure_debut_collecte2 = st.text_input("Début collecte 2", value=st.session_state.heure_debut_collecte2)
    st.session_state.heure_fin_collecte2 = st.text_input("Fin collecte 2", value=st.session_state.heure_fin_collecte2)
    
    st.markdown("**🚛 DÉCHARGE 2**")
    st.session_state.heure_depart_decharge2 = st.text_input("Départ décharge 2", value=st.session_state.heure_depart_decharge2)
    st.session_state.heure_arrivee_decharge2 = st.text_input("Arrivée décharge 2", value=st.session_state.heure_arrivee_decharge2)
    st.session_state.heure_sortie_decharge2 = st.text_input("Sortie décharge 2", value=st.session_state.heure_sortie_decharge2)
    
    st.markdown("**🏁 RETOUR**")
    st.session_state.heure_retour_depot = st.text_input("Retour dépôt", value=st.session_state.heure_retour_depot)

# ==================== COLLECTE 1 ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 COLLECTE 1</div>', unsafe_allow_html=True)

if not st.session_state.collecte1_validee:
    
    etapes = [
        ("🏭 DÉPART DÉPÔT", "depart_depot", "heure_depot_depart"),
        ("🗑️ DÉBUT COLLECTE 1", "debut_collecte", "heure_debut_collecte1"),
        ("🗑️ FIN COLLECTE 1", "fin_collecte", "heure_fin_collecte1"),
        ("🚛 DÉPART DÉCHARGE 1", "depart_decharge", "heure_depart_decharge1"),
        ("🏭 ARRIVÉE DÉCHARGE 1", "arrivee_decharge", "heure_arrivee_decharge1"),
        ("🏭 SORTIE DÉCHARGE 1 + VOLUME", "sortie_decharge", "heure_sortie_decharge1")
    ]
    
    for titre, type_point, heure_key in etapes:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"**{titre}**")
            st.caption(f"Heure: {st.session_state[heure_key]}")
        with col2:
            if type_point == "sortie_decharge":
                volume = st.number_input("Volume (m³)", min_value=0.0, step=0.5, key=f"vol_{type_point}", value=0.0)
            else:
                volume = None
        with col3:
            if st.button(f"📍 Enregistrer", key=f"btn_{type_point}", use_container_width=True):
                # Récupérer la position à utiliser
                if st.session_state.gps_actif and st.session_state.current_gps:
                    lat = st.session_state.current_gps['lat']
                    lon = st.session_state.current_gps['lon']
                    accuracy = st.session_state.current_gps['accuracy']
                    st.success(f"📍 Position GPS utilisée (précision: {accuracy:.0f}m)")
                else:
                    # Fallback : coordonnées du quartier
                    quartier_coords = {
                        "NDIOP": (15.121048, -16.686826),
                        "Lébou Est": (15.109558, -16.628958),
                        "Lébou Ouest": (15.098159, -16.619668),
                        "Ngaye Djitté": (15.115900, -16.632128),
                        "HLM": (15.117350, -16.635411),
                        "Mbambara": (15.115765, -16.632181),
                        "Ngaye Diagne": (15.120364, -16.635608)
                    }
                    lat, lon = quartier_coords.get(st.session_state.quartier_nom, (15.115000, -16.635000))
                    accuracy = 100
                    if st.session_state.gps_actif:
                        st.warning("⚠️ Aucune position GPS disponible. Actualisez d'abord votre position.")
                    else:
                        st.info("📍 GPS désactivé, utilisation des coordonnées du quartier.")
                
                point = {
                    "type": type_point,
                    "lat": lat,
                    "lon": lon,
                    "heure": st.session_state[heure_key],
                    "titre": titre,
                    "volume": volume if volume else None,
                    "precision": accuracy
                }
                
                if type_point == "sortie_decharge" and volume > 0:
                    st.session_state.volume1 = volume
                    st.success(f"✅ {titre} - Volume: {volume} m³")
                else:
                    st.success(f"✅ {titre} enregistré")
                
                # Calcul de la distance depuis le dernier point
                if st.session_state.derniere_position:
                    distance = calculer_distance(
                        st.session_state.derniere_position["lat"],
                        st.session_state.derniere_position["lon"],
                        lat, lon
                    )
                    st.session_state.distance_totale += distance
                    st.info(f"📏 Distance depuis dernier point: {distance:.2f} km")
                
                point["distance_depuis_dernier"] = distance if st.session_state.derniere_position else 0
                st.session_state.derniere_position = point
                st.session_state.points_gps.append(point)
    
    # Validation Collecte 1
    st.markdown("---")
    if st.button("✅ VALIDER COLLECTE 1", type="primary", use_container_width=True):
        if st.session_state.volume1 > 0:
            st.session_state.collecte1_validee = True
            st.success("✅ Collecte 1 validée")
            st.rerun()
        else:
            st.warning("⚠️ Veuillez enregistrer le volume")

else:
    st.success("✅ Collecte 1 terminée")
    st.write(f"📦 Volume: {st.session_state.volume1:.1f} m³")

# ==================== COLLECTE 2 ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 COLLECTE 2 (OPTIONNELLE)</div>', unsafe_allow_html=True)

if st.session_state.collecte1_validee and not st.session_state.collecte2_validee:
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ FAIRE COLLECTE 2", use_container_width=True):
            st.session_state.collecte2_optionnelle = True
            st.rerun()
    with col2:
        if st.button("⏭️ PASSER", use_container_width=True):
            st.session_state.collecte2_validee = True
            st.rerun()
    
    if st.session_state.collecte2_optionnelle:
        
        etapes2 = [
            ("🗑️ DÉBUT COLLECTE 2", "debut_collecte2", "heure_debut_collecte2"),
            ("🗑️ FIN COLLECTE 2", "fin_collecte2", "heure_fin_collecte2"),
            ("🚛 DÉPART DÉCHARGE 2", "depart_decharge2", "heure_depart_decharge2"),
            ("🏭 ARRIVÉE DÉCHARGE 2", "arrivee_decharge2", "heure_arrivee_decharge2"),
            ("🏭 SORTIE DÉCHARGE 2 + VOLUME", "sortie_decharge2", "heure_sortie_decharge2"),
            ("🏁 RETOUR DÉPÔT", "retour_depot", "heure_retour_depot")
        ]
        
        for titre, type_point, heure_key in etapes2:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**{titre}**")
                st.caption(f"Heure: {st.session_state[heure_key]}")
            with col2:
                if type_point == "sortie_decharge2":
                    volume = st.number_input("Volume (m³)", min_value=0.0, step=0.5, key=f"vol_{type_point}", value=0.0)
                else:
                    volume = None
            with col3:
                if st.button(f"📍 Enregistrer", key=f"btn2_{type_point}", use_container_width=True):
                    if st.session_state.gps_actif and st.session_state.current_gps:
                        lat = st.session_state.current_gps['lat']
                        lon = st.session_state.current_gps['lon']
                        accuracy = st.session_state.current_gps['accuracy']
                        st.success(f"📍 Position GPS utilisée (précision: {accuracy:.0f}m)")
                    else:
                        quartier_coords = {
                            "NDIOP": (15.121048, -16.686826),
                            "Lébou Est": (15.109558, -16.628958),
                            "Lébou Ouest": (15.098159, -16.619668),
                            "Ngaye Djitté": (15.115900, -16.632128),
                            "HLM": (15.117350, -16.635411),
                            "Mbambara": (15.115765, -16.632181),
                            "Ngaye Diagne": (15.120364, -16.635608)
                        }
                        lat, lon = quartier_coords.get(st.session_state.quartier_nom, (15.115000, -16.635000))
                        accuracy = 100
                        if st.session_state.gps_actif:
                            st.warning("⚠️ Aucune position GPS disponible. Actualisez d'abord votre position.")
                        else:
                            st.info("📍 GPS désactivé, utilisation des coordonnées du quartier.")
                    
                    point = {
                        "type": type_point,
                        "lat": lat,
                        "lon": lon,
                        "heure": st.session_state[heure_key],
                        "titre": titre,
                        "collecte": 2,
                        "volume": volume if volume else None,
                        "precision": accuracy
                    }
                    
                    if type_point == "sortie_decharge2" and volume > 0:
                        st.session_state.volume2 = volume
                        st.success(f"✅ {titre} - Volume: {volume} m³")
                    else:
                        st.success(f"✅ {titre} enregistré")
                    
                    if st.session_state.derniere_position:
                        distance = calculer_distance(
                            st.session_state.derniere_position["lat"],
                            st.session_state.derniere_position["lon"],
                            lat, lon
                        )
                        st.session_state.distance_totale += distance
                        st.info(f"📏 Distance: {distance:.2f} km")
                    
                    point["distance_depuis_dernier"] = distance if st.session_state.derniere_position else 0
                    st.session_state.derniere_position = point
                    st.session_state.points_gps.append(point)
        
        st.markdown("---")
        if st.button("✅ VALIDER COLLECTE 2", type="primary", use_container_width=True):
            if st.session_state.volume2 > 0:
                st.session_state.collecte2_validee = True
                st.success("✅ Collecte 2 validée")
                st.rerun()
            else:
                st.warning("⚠️ Veuillez enregistrer le volume")

# ==================== TERMINER ====================
if st.session_state.collecte1_validee and (st.session_state.collecte2_validee or not st.session_state.collecte2_optionnelle):
    
    st.markdown("---")
    st.markdown("### 🏁 TERMINER")
    
    total_volume = st.session_state.volume1 + st.session_state.volume2
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📦 Volume total", f"{total_volume:.1f} m³")
    with col2:
        st.metric("📏 Distance totale", f"{st.session_state.distance_totale:.2f} km")
    
    if st.button("💾 ENREGISTRER", type="primary", use_container_width=True):
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
                        "vol_total": total_volume,
                        "depart": st.session_state.heure_depot_depart,
                        "retour": st.session_state.heure_retour_depot,
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
                            "desc": point.get("description", f"{point['titre']} - {point['heure']}"),
                            "collecte": point.get("collecte", 1)
                        })
                    conn.commit()
                
                st.balloons()
                st.success("✅ Tournée enregistrée !")
                
                if st.button("🔄 NOUVELLE TOURNÉE", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key not in ['agent_nom']:
                            del st.session_state[key]
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erreur: {e}")

# ==================== CARTE ====================
st.markdown("---")
st.markdown("### 🗺️ ITINÉRAIRE")

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
    
    fig = px.scatter_mapbox(
        df_points,
        lat="lat",
        lon="lon",
        color="type",
        hover_name="titre",
        hover_data={"heure": True, "distance_depuis_dernier": True, "precision": True},
        color_discrete_map=couleurs,
        zoom=13,
        center={"lat": 15.11, "lon": -16.65},
        title="🗺️ ITINÉRAIRE - Points enregistrés",
        height=500
    )
    
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
    
    with st.expander("📋 Détail des points"):
        for i, point in enumerate(st.session_state.points_gps):
            st.write(f"{i+1}. {point['titre']} - {point['heure']}")
            st.write(f"   📍 {point['lat']:.6f}, {point['lon']:.6f}")
            if point.get('distance_depuis_dernier', 0) > 0:
                st.write(f"   📏 Distance: {point['distance_depuis_dernier']:.2f} km")
            if point.get('precision'):
                st.write(f"   🎯 Précision GPS: {point['precision']:.0f} m")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"👤 Agent: {st.session_state.agent_nom or 'Non connecté'} | 📡 GPS: {'Actif' if st.session_state.gps_actif else 'Inactif'} | 🗑️ Commune de Mékhé")
