"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec carte interactive et tracé d'itinéraire
- Collecte 1 et Collecte 2 séparées
- Carte avec points GPS
- Tracé du trajet en temps réel
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, time, timedelta
from sqlalchemy import create_engine, text
import os
from io import BytesIO
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

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte - Suivi de Tournée</h1><p>Commune de Mékhé | Carte interactive | GPS temps réel</p></div>', unsafe_allow_html=True)

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
    """Simule la récupération de la position GPS"""
    # Dans une vraie application, on utiliserait st_js
    # Pour l'instant, coordonnées par défaut du quartier
    return {"lat": 15.115000, "lon": -16.635000, "accuracy": 10}

# ==================== SESSION STATE ====================
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'tournee_id' not in st.session_state:
    st.session_state.tournee_id = None
if 'collecte1_validee' not in st.session_state:
    st.session_state.collecte1_validee = False
if 'collecte2_validee' not in st.session_state:
    st.session_state.collecte2_validee = False
if 'points_gps' not in st.session_state:
    st.session_state.points_gps = []
if 'gps_actif' not in st.session_state:
    st.session_state.gps_actif = False

# ==================== BARRE LATÉRALE - IDENTIFICATION ====================
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
    
    st.markdown("---")
    
    # Activation GPS
    if st.button("📍 ACTIVER LE GPS", use_container_width=True):
        st.session_state.gps_actif = True
        st.success("✅ GPS activé")
    
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF</div>', unsafe_allow_html=True)

# ==================== SECTION COMMUNE ====================
col1, col2 = st.columns(2)
with col1:
    date_tournee = st.date_input("📅 Date", value=date.today())
with col2:
    quartier_nom = st.selectbox("📍 Quartier", [q[1] for q in get_quartiers()])

# ==================== COLLECTE 1 ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 <strong>COLLECTE 1</strong> - Premier tour</div>', unsafe_allow_html=True)

if not st.session_state.collecte1_validee:
    
    # ========== ÉTAPES COLLECTE 1 ==========
    
    # 1. Départ dépôt
    st.markdown("#### 🏭 1. DÉPART DU DÉPÔT")
    col1, col2 = st.columns(2)
    with col1:
        heure_depot_depart = st.time_input("Heure de départ", value=time(7, 0), key="depart1")
    with col2:
        if st.button("📍 Enregistrer départ", key="btn_depart1"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_depot", "Départ du dépôt - Collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "depart_depot", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1})
                st.success("✅ Départ enregistré")
    
    # 2. Début collecte 1
    st.markdown("#### 🗑️ 2. DÉBUT DE LA COLLECTE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_debut_collecte1 = st.time_input("Heure début collecte", value=time(7, 30), key="debut_collecte1")
    with col2:
        if st.button("📍 Enregistrer début collecte", key="btn_debut1"):
            pos = get_position()
            if enregistrer_point_gps(None, "debut_collecte", "Début de la collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "debut_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1})
                st.success("✅ Début collecte enregistré")
    
    # 3. Fin collecte 1
    st.markdown("#### 🗑️ 3. FIN DE LA COLLECTE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_fin_collecte1 = st.time_input("Heure fin collecte", value=time(9, 30), key="fin_collecte1")
    with col2:
        if st.button("📍 Enregistrer fin collecte", key="btn_fin1"):
            pos = get_position()
            if enregistrer_point_gps(None, "fin_collecte", "Fin de la collecte 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "fin_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1})
                st.success("✅ Fin collecte enregistrée")
    
    # 4. Départ vers décharge 1
    st.markdown("#### 🚛 4. DÉPART VERS LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_depart_decharge1 = st.time_input("Heure départ décharge", value=time(9, 45), key="depart_decharge1")
    with col2:
        if st.button("📍 Enregistrer départ décharge", key="btn_depart_decharge1"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_decharge", "Départ vers décharge 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "depart_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1})
                st.success("✅ Départ décharge enregistré")
    
    # 5. Arrivée décharge 1
    st.markdown("#### 🏭 5. ARRIVÉE À LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_arrivee_decharge1 = st.time_input("Heure arrivée décharge", value=time(10, 15), key="arrivee_decharge1")
    with col2:
        if st.button("📍 Enregistrer arrivée décharge", key="btn_arrivee_decharge1"):
            pos = get_position()
            if enregistrer_point_gps(None, "arrivee_decharge", "Arrivée décharge 1", pos["lat"], pos["lon"], 1):
                st.session_state.points_gps.append({"type": "arrivee_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1})
                st.success("✅ Arrivée décharge enregistrée")
    
    # 6. Sortie décharge 1 + Volume
    st.markdown("#### 🏭 6. SORTIE DE LA DÉCHARGE 1")
    col1, col2 = st.columns(2)
    with col1:
        heure_sortie_decharge1 = st.time_input("Heure sortie décharge", value=time(10, 45), key="sortie_decharge1")
        volume1 = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key="volume1")
    with col2:
        if st.button("📍 Enregistrer sortie + Volume", key="btn_sortie1"):
            pos = get_position()
            if volume1 > 0:
                if enregistrer_point_gps(None, "sortie_decharge", f"Sortie décharge 1 - Volume: {volume1} m³", pos["lat"], pos["lon"], 1):
                    st.session_state.points_gps.append({"type": "sortie_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 1})
                    st.session_state.volume1 = volume1
                    st.success(f"✅ Sortie décharge enregistrée - Volume: {volume1} m³")
            else:
                st.warning("⚠️ Veuillez saisir le volume déchargé")
    
    # 7. Valider Collecte 1
    st.markdown("---")
    if st.button("✅ VALIDER LA COLLECTE 1", type="primary", use_container_width=True):
        if volume1 > 0:
            st.session_state.collecte1_validee = True
            st.success("✅ Collecte 1 validée ! Passez à la Collecte 2")
            st.rerun()
        else:
            st.warning("⚠️ Veuillez enregistrer le volume déchargé")

else:
    st.success("✅ Collecte 1 terminée et validée")
    if st.button("📝 Modifier Collecte 1", use_container_width=True):
        st.session_state.collecte1_validee = False
        st.rerun()

# ==================== COLLECTE 2 ====================
st.markdown("---")
st.markdown('<div class="collecte2-card">🚛 <strong>COLLECTE 2</strong> - Deuxième tour</div>', unsafe_allow_html=True)

if st.session_state.collecte1_validee and not st.session_state.collecte2_validee:
    
    # ========== ÉTAPES COLLECTE 2 ==========
    
    # 1. Début collecte 2
    st.markdown("#### 🗑️ 1. DÉBUT DE LA COLLECTE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_debut_collecte2 = st.time_input("Heure début collecte 2", value=time(11, 0), key="debut_collecte2")
    with col2:
        if st.button("📍 Enregistrer début collecte 2", key="btn_debut2"):
            pos = get_position()
            if enregistrer_point_gps(None, "debut_collecte", "Début de la collecte 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "debut_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2})
                st.success("✅ Début collecte 2 enregistré")
    
    # 2. Fin collecte 2
    st.markdown("#### 🗑️ 2. FIN DE LA COLLECTE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_fin_collecte2 = st.time_input("Heure fin collecte 2", value=time(13, 0), key="fin_collecte2")
    with col2:
        if st.button("📍 Enregistrer fin collecte 2", key="btn_fin2"):
            pos = get_position()
            if enregistrer_point_gps(None, "fin_collecte", "Fin de la collecte 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "fin_collecte", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2})
                st.success("✅ Fin collecte 2 enregistrée")
    
    # 3. Départ vers décharge 2
    st.markdown("#### 🚛 3. DÉPART VERS LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_depart_decharge2 = st.time_input("Heure départ décharge 2", value=time(13, 15), key="depart_decharge2")
    with col2:
        if st.button("📍 Enregistrer départ décharge 2", key="btn_depart_decharge2"):
            pos = get_position()
            if enregistrer_point_gps(None, "depart_decharge", "Départ vers décharge 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "depart_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2})
                st.success("✅ Départ décharge 2 enregistré")
    
    # 4. Arrivée décharge 2
    st.markdown("#### 🏭 4. ARRIVÉE À LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_arrivee_decharge2 = st.time_input("Heure arrivée décharge 2", value=time(13, 45), key="arrivee_decharge2")
    with col2:
        if st.button("📍 Enregistrer arrivée décharge 2", key="btn_arrivee_decharge2"):
            pos = get_position()
            if enregistrer_point_gps(None, "arrivee_decharge", "Arrivée décharge 2", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "arrivee_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2})
                st.success("✅ Arrivée décharge 2 enregistrée")
    
    # 5. Sortie décharge 2 + Volume
    st.markdown("#### 🏭 5. SORTIE DE LA DÉCHARGE 2")
    col1, col2 = st.columns(2)
    with col1:
        heure_sortie_decharge2 = st.time_input("Heure sortie décharge 2", value=time(14, 15), key="sortie_decharge2")
        volume2 = st.number_input("📦 Volume déchargé (m³)", min_value=0.0, step=0.5, key="volume2")
    with col2:
        if st.button("📍 Enregistrer sortie + Volume 2", key="btn_sortie2"):
            pos = get_position()
            if volume2 > 0:
                if enregistrer_point_gps(None, "sortie_decharge", f"Sortie décharge 2 - Volume: {volume2} m³", pos["lat"], pos["lon"], 2):
                    st.session_state.points_gps.append({"type": "sortie_decharge", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2})
                    st.session_state.volume2 = volume2
                    st.success(f"✅ Sortie décharge 2 enregistrée - Volume: {volume2} m³")
            else:
                st.warning("⚠️ Veuillez saisir le volume déchargé")
    
    # 6. Retour dépôt
    st.markdown("#### 🏁 6. RETOUR AU DÉPÔT")
    col1, col2 = st.columns(2)
    with col1:
        heure_retour_depot = st.time_input("Heure retour dépôt", value=time(14, 45), key="retour")
    with col2:
        if st.button("📍 Enregistrer retour", key="btn_retour"):
            pos = get_position()
            if enregistrer_point_gps(None, "retour_depot", "Retour au dépôt", pos["lat"], pos["lon"], 2):
                st.session_state.points_gps.append({"type": "retour_depot", "lat": pos["lat"], "lon": pos["lon"], "collecte": 2})
                st.success("✅ Retour dépôt enregistré")
    
    # 7. Valider Collecte 2
    st.markdown("---")
    if st.button("✅ VALIDER LA COLLECTE 2", type="primary", use_container_width=True):
        if volume2 > 0:
            st.session_state.collecte2_validee = True
            st.success("✅ Collecte 2 validée ! Tournée terminée")
            
            # Enregistrer dans la base de données
            quartier_id = get_quartier_id(quartier_nom)
            equipe_id = get_equipe_id("Équipe A")  # À adapter
            
            if quartier_id and equipe_id:
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
                        "date": date_tournee,
                        "qid": quartier_id,
                        "eid": equipe_id,
                        "agent": st.session_state.agent_nom,
                        "vol1": st.session_state.volume1,
                        "vol2": st.session_state.volume2,
                        "vol_total": st.session_state.volume1 + st.session_state.volume2,
                        "depart": heure_depot_depart.strftime("%H:%M:%S"),
                        "retour": heure_retour_depot.strftime("%H:%M:%S")
                    })
                    tournee_id = result.fetchone()[0]
                    
                    # Enregistrer tous les points GPS
                    for point in st.session_state.points_gps:
                        conn.execute(text("""
                            INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, collecte_numero)
                            VALUES (:tid, :heure, :type, :lat, :lon, :collecte)
                        """), {
                            "tid": tournee_id,
                            "heure": datetime.now(),
                            "type": point["type"],
                            "lat": point["lat"],
                            "lon": point["lon"],
                            "collecte": point["collecte"]
                        })
                    conn.commit()
                
                st.balloons()
            st.rerun()
        else:
            st.warning("⚠️ Veuillez enregistrer le volume déchargé")

elif st.session_state.collecte2_validee:
    st.success("✅ Tournée complète terminée !")
    if st.button("🔄 DÉMARRER UNE NOUVELLE TOURNÉE", use_container_width=True):
        st.session_state.collecte1_validee = False
        st.session_state.collecte2_validee = False
        st.session_state.points_gps = []
        st.rerun()

# ==================== CARTE INTERACTIVE ====================
st.markdown("---")
st.markdown("### 🗺️ Carte interactive du trajet")

if st.session_state.points_gps:
    # Préparer les données pour la carte
    df_points = pd.DataFrame(st.session_state.points_gps)
    
    # Définir les couleurs par type de point
    couleurs = {
        "depart_depot": "green",
        "debut_collecte": "blue",
        "fin_collecte": "blue",
        "depart_decharge": "orange",
        "arrivee_decharge": "red",
        "sortie_decharge": "purple",
        "retour_depot": "brown"
    }
    
    # Créer la carte
    fig = px.scatter_mapbox(
        df_points,
        lat="lat",
        lon="lon",
        color="type",
        hover_name="type",
        hover_data={"collecte": True},
        color_discrete_map=couleurs,
        zoom=13,
        center={"lat": 15.11, "lon": -16.65},
        title="Trajet de la tournée - Points GPS enregistrés",
        height=500
    )
    
    # Ajouter les lignes pour tracer le trajet
    if len(df_points) > 1:
        fig.add_trace(go.Scattermapbox(
            lat=df_points["lat"].tolist(),
            lon=df_points["lon"].tolist(),
            mode='lines',
            line=dict(width=2, color='blue'),
            name='Trajet',
            showlegend=True
        ))
    
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=12,
        margin={"r": 0, "t": 40, "l": 0, "b": 0}
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Légende
    st.markdown("""
    <div class="info-box">
    <strong>📊 Légende des points :</strong><br>
    🟢 Vert - Départ dépôt<br>
    🔵 Bleu - Points de collecte (début/fin)<br>
    🟠 Orange - Départ vers décharge<br>
    🔴 Rouge - Arrivée décharge<br>
    🟣 Violet - Sortie décharge<br>
    🟤 Marron - Retour dépôt<br>
    📏 Ligne bleue - Trajet effectué
    </div>
    """, unsafe_allow_html=True)
    
else:
    st.info("ℹ️ Aucun point GPS enregistré pour le moment. Utilisez les boutons 'Enregistrer' pendant votre tournée.")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📱 Agent: {st.session_state.agent_nom or 'Non connecté'} | GPS: {'Actif' if st.session_state.gps_actif else 'Inactif'}")
