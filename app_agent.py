"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec sélection manuelle des points sur carte interactive
Pas de GPS automatique, l'agent clique sur la carte pour chaque étape.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from io import BytesIO
import folium
from streamlit_folium import folium_static
from branca.element import Figure
import json

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
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte</h1><p>Commune de Mékhé | Carte interactive</p></div>', unsafe_allow_html=True)

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

def afficher_carte_et_point(titre, point_initial=None):
    """
    Affiche une carte interactive. L'agent clique pour définir un point.
    Retourne (lat, lon) si un point a été sélectionné, sinon None.
    """
    import folium
    from streamlit_folium import folium_static
    import streamlit.components.v1 as components

    # Centre par défaut
    if point_initial:
        centre = [point_initial[0], point_initial[1]]
    else:
        centre = [15.115, -16.635]

    m = folium.Map(location=centre, zoom_start=14)
    # Ajouter un marqueur temporaire pour indiquer le point
    marker = None
    if point_initial:
        marker = folium.Marker(location=centre, popup="Point actuel")
        marker.add_to(m)

    # Ajouter un script pour capturer le clic et stocker la position
    # On utilise un élément caché pour stocker les coordonnées
    click_js = """
    <script>
    function onMapClick(e) {
        var lat = e.latlng.lat;
        var lng = e.latlng.lng;
        document.getElementById('selected_lat').value = lat;
        document.getElementById('selected_lon').value = lng;
        document.getElementById('selected_accuracy').value = "0";
        // On peut aussi mettre à jour un marqueur, mais pour simplifier on stocke
        console.log("Point cliqué : ", lat, lng);
    }
    // On attend que la carte soit chargée
    setTimeout(() => {
        var map = document.querySelector('.folium-map');
        if (map) {
            map._leaflet_map.on('click', onMapClick);
        }
    }, 1000);
    </script>
    <input type="hidden" id="selected_lat" value="">
    <input type="hidden" id="selected_lon" value="">
    <input type="hidden" id="selected_accuracy" value="">
    """
    # On affiche la carte et on injecte le script via components.html
    # Mais il faut une approche plus simple : on utilise la possibilité de stocker
    # la position dans session_state via un formulaire.

    # Solution pratique : on affiche la carte, et on ajoute deux champs pour que l'agent
    # puisse entrer les coordonnées qu'il lit sur la carte (clic -> popup).
    # On utilise le plugin LatLngPopup.
    m.add_child(folium.LatLngPopup())

    with st.container():
        col1, col2 = st.columns([2, 1])
        with col1:
            st.write(f"**{titre}** : cliquez sur la carte pour obtenir les coordonnées.")
            folium_static(m, width=600, height=400)
        with col2:
            st.write("Coordonnées du point :")
            lat = st.text_input("Latitude", key=f"lat_{titre}")
            lon = st.text_input("Longitude", key=f"lon_{titre}")
            if st.button("Valider ce point", key=f"valider_{titre}"):
                if lat and lon:
                    try:
                        return float(lat), float(lon)
                    except:
                        st.error("Format invalide")
                else:
                    st.warning("Veuillez entrer les coordonnées (cliquez sur la carte pour les obtenir).")
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
if 'collecte1_validee' not in st.session_state:
    st.session_state.collecte1_validee = False
if 'collecte2_validee' not in st.session_state:
    st.session_state.collecte2_validee = False
if 'collecte2_optionnelle' not in st.session_state:
    st.session_state.collecte2_optionnelle = False
if 'derniere_position' not in st.session_state:
    st.session_state.derniere_position = None
if 'distance_totale' not in st.session_state:
    st.session_state.distance_totale = 0.0
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
if 'temps_debut_tournee' not in st.session_state:
    st.session_state.temps_debut_tournee = None

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent de collecte")
    agent_nom_input = st.text_input("✍️ Votre nom", value=st.session_state.agent_nom, placeholder="Ex: Alioune Diop")
    if agent_nom_input:
        st.session_state.agent_nom = agent_nom_input
        st.success(f"✅ Connecté: {agent_nom_input}")

    st.markdown("---")
    st.markdown("### 📍 Aide")
    st.info("""
    Pour chaque point, cliquez sur la carte pour afficher les coordonnées, puis recopiez-les dans les champs.
    Vous pouvez aussi utiliser un lien Google Maps pour obtenir votre position actuelle.
    """)
    # Lien vers Google Maps
    st.markdown("""
    <a href="https://www.google.com/maps/search/ma+position" target="_blank">
        <button style="background:#2196F3; color:white; border:none; padding:10px; border-radius:8px; width:100%; margin-bottom:10px;">📍 OBTENIR MA POSITION (Google Maps)</button>
    </a>
    """, unsafe_allow_html=True)

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
    
    # Liste des étapes avec leurs types et heures
    etapes = [
        ("🏭 DÉPART DÉPÔT", "depart_depot", "heure_depot_depart"),
        ("🗑️ DÉBUT COLLECTE 1", "debut_collecte", "heure_debut_collecte1"),
        ("🗑️ FIN COLLECTE 1", "fin_collecte", "heure_fin_collecte1"),
        ("🚛 DÉPART DÉCHARGE 1", "depart_decharge", "heure_depart_decharge1"),
        ("🏭 ARRIVÉE DÉCHARGE 1", "arrivee_decharge", "heure_arrivee_decharge1"),
        ("🏭 SORTIE DÉCHARGE 1 + VOLUME", "sortie_decharge", "heure_sortie_decharge1")
    ]
    
    for titre, type_point, heure_key in etapes:
        st.markdown(f"#### {titre}")
        
        # Récupérer la position du point précédent pour centrer la carte
        dernier_point = st.session_state.derniere_position
        centre = [dernier_point['lat'], dernier_point['lon']] if dernier_point else None
        
        # Afficher la carte interactive
        col1, col2 = st.columns([2, 1])
        with col1:
            # Carte avec clic pour obtenir les coordonnées
            m = folium.Map(location=centre or [15.115, -16.635], zoom_start=14)
            m.add_child(folium.LatLngPopup())
            folium_static(m, width=500, height=300)
            st.caption("Cliquez sur la carte pour obtenir les coordonnées.")
        with col2:
            st.write("**Coordonnées du point**")
            lat = st.text_input("Latitude", key=f"lat_{type_point}", placeholder="Ex: 15.121048")
            lon = st.text_input("Longitude", key=f"lon_{type_point}", placeholder="Ex: -16.686826")
            if type_point == "sortie_decharge":
                volume = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key=f"vol_{type_point}")
            else:
                volume = None
        
        # Bouton d'enregistrement
        if st.button(f"📍 Enregistrer {titre}", key=f"btn_{type_point}", use_container_width=True):
            if lat and lon:
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
                except:
                    st.error("Coordonnées invalides")
                    continue
            else:
                st.warning("Veuillez entrer les coordonnées (cliquez sur la carte).")
                continue
            
            point = {
                "type": type_point,
                "lat": lat_f,
                "lon": lon_f,
                "heure": st.session_state[heure_key],
                "titre": titre,
                "volume": volume if volume else None
            }
            
            if type_point == "sortie_decharge" and volume and volume > 0:
                st.session_state.volume1 = volume
                st.success(f"✅ {titre} - Volume: {volume} m³")
            else:
                st.success(f"✅ {titre} enregistré")
            
            # Calcul de la distance
            if st.session_state.derniere_position:
                distance = calculer_distance(
                    st.session_state.derniere_position["lat"],
                    st.session_state.derniere_position["lon"],
                    lat_f, lon_f
                )
                st.session_state.distance_totale += distance
                st.info(f"📏 Distance depuis dernier point: {distance:.2f} km")
                point["distance_depuis_dernier"] = distance
            else:
                point["distance_depuis_dernier"] = 0
            
            st.session_state.derniere_position = point
            st.session_state.points_gps.append(point)
            st.rerun()
    
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
            st.markdown(f"#### {titre}")
            
            dernier_point = st.session_state.derniere_position
            centre = [dernier_point['lat'], dernier_point['lon']] if dernier_point else None
            
            col1, col2 = st.columns([2, 1])
            with col1:
                m = folium.Map(location=centre or [15.115, -16.635], zoom_start=14)
                m.add_child(folium.LatLngPopup())
                folium_static(m, width=500, height=300)
                st.caption("Cliquez sur la carte pour obtenir les coordonnées.")
            with col2:
                lat = st.text_input("Latitude", key=f"lat_{type_point}", placeholder="Ex: 15.121048")
                lon = st.text_input("Longitude", key=f"lon_{type_point}", placeholder="Ex: -16.686826")
                if type_point == "sortie_decharge2":
                    volume = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key=f"vol_{type_point}")
                else:
                    volume = None
            
            if st.button(f"📍 Enregistrer {titre}", key=f"btn2_{type_point}", use_container_width=True):
                if lat and lon:
                    try:
                        lat_f = float(lat)
                        lon_f = float(lon)
                    except:
                        st.error("Coordonnées invalides")
                        continue
                else:
                    st.warning("Veuillez entrer les coordonnées.")
                    continue
                
                point = {
                    "type": type_point,
                    "lat": lat_f,
                    "lon": lon_f,
                    "heure": st.session_state[heure_key],
                    "titre": titre,
                    "collecte": 2,
                    "volume": volume if volume else None
                }
                
                if type_point == "sortie_decharge2" and volume and volume > 0:
                    st.session_state.volume2 = volume
                    st.success(f"✅ {titre} - Volume: {volume} m³")
                else:
                    st.success(f"✅ {titre} enregistré")
                
                if st.session_state.derniere_position:
                    distance = calculer_distance(
                        st.session_state.derniere_position["lat"],
                        st.session_state.derniere_position["lon"],
                        lat_f, lon_f
                    )
                    st.session_state.distance_totale += distance
                    st.info(f"📏 Distance: {distance:.2f} km")
                    point["distance_depuis_dernier"] = distance
                else:
                    point["distance_depuis_dernier"] = 0
                
                st.session_state.derniere_position = point
                st.session_state.points_gps.append(point)
                st.rerun()
        
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
        hover_data={"heure": True, "distance_depuis_dernier": True},
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

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"👤 Agent: {st.session_state.agent_nom or 'Non connecté'} | 🗑️ Commune de Mékhé")
