"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version finale avec :
- Volume enregistré à la décharge (quand le camion vide)
- Points de collecte sans volume
- 2 collectes, 2 décharges
- GPS intégré
- Photos par point
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime, time, timedelta
from sqlalchemy import create_engine, text
import os
from io import BytesIO
import json

st.set_page_config(
    page_title="Agent Collecte - Mékhé",
    page_icon="🗑️",
    layout="wide",
    initial_sidebar_state="collapsed"
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
    .decharge-card {
        background: #fff3e0;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 4px solid #FF9800;
    }
    .point-card {
        background: #f8f9fa;
        padding: 0.8rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border-left: 3px solid #2E7D32;
    }
    .point-numero {
        font-weight: bold;
        background: #2E7D32;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        display: inline-block;
        margin-right: 8px;
    }
    .gps-active {
        background: #4CAF50;
        color: white;
        padding: 0.5rem;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
    }
    .success-box {
        background: #d4edda;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #2196F3;
        margin: 1rem 0;
    }
    .volume-box {
        background: #fff8e7;
        padding: 1rem;
        border-radius: 10px;
        border: 2px dashed #FF9800;
        text-align: center;
        margin: 1rem 0;
    }
    .horaires-box {
        background: #f5f5f5;
        padding: 0.8rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border: 1px solid #ddd;
    }
    .stButton button {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte - Suivi de Tournée</h1><p>Commune de Mékhé | Volume enregistré à la décharge | GPS | Photos</p></div>', unsafe_allow_html=True)

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

def enregistrer_point_collecte(tournee_id, point_data):
    """Enregistre un point de collecte (sans volume)"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO points_collecte (
                    tournee_id, point_numero, heure_passage, 
                    latitude, longitude, precision_gps, photo_data, 
                    description, collecte_numero
                ) VALUES (
                    :tid, :numero, :heure, 
                    :lat, :lon, :precision, :photo, 
                    :desc, :collecte
                )
            """), {
                "tid": tournee_id,
                "numero": point_data["numero"],
                "heure": point_data["heure"],
                "lat": point_data.get("lat"),
                "lon": point_data.get("lon"),
                "precision": point_data.get("precision", 0),
                "photo": point_data.get("photo"),
                "desc": point_data.get("description", ""),
                "collecte": point_data.get("collecte_numero", 1)
            })
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur: {e}")
        return False

def enregistrer_volume_decharge(tournee_id, collecte_numero, volume, observations=""):
    """Enregistre le volume déchargé à la décharge"""
    try:
        with engine.connect() as conn:
            if collecte_numero == 1:
                conn.execute(text("""
                    UPDATE tournees SET volume_collecte1 = :volume WHERE id = :tid
                """), {"volume": volume, "tid": tournee_id})
            else:
                conn.execute(text("""
                    UPDATE tournees SET volume_collecte2 = :volume WHERE id = :tid
                """), {"volume": volume, "tid": tournee_id})
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur: {e}")
        return False

def exporter_excel(tournee_id):
    """Exporte une tournée en Excel"""
    try:
        with engine.connect() as conn:
            tournee = conn.execute(text("""
                SELECT 
                    t.*,
                    q.nom as quartier,
                    e.nom as equipe
                FROM tournees t
                JOIN quartiers q ON t.quartier_id = q.id
                JOIN equipes e ON t.equipe_id = e.id
                WHERE t.id = :tid
            """), {"tid": tournee_id}).first()
            
            points = conn.execute(text("""
                SELECT * FROM points_collecte 
                WHERE tournee_id = :tid 
                ORDER BY collecte_numero, point_numero
            """), {"tid": tournee_id}).fetchall()
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                resume = pd.DataFrame({
                    "Information": ["Date", "Quartier", "Équipe", "Agent",
                                   "Départ dépôt",
                                   "Collecte 1 - Début", "Collecte 1 - Fin",
                                   "Décharge 1 - Départ", "Décharge 1 - Arrivée", "Décharge 1 - Sortie", "Décharge 1 - Volume",
                                   "Collecte 2 - Début", "Collecte 2 - Fin",
                                   "Décharge 2 - Départ", "Décharge 2 - Arrivée", "Décharge 2 - Sortie", "Décharge 2 - Volume",
                                   "Retour dépôt", "Distance totale"],
                    "Valeur": [
                        tournee.date_tournee,
                        tournee.quartier,
                        tournee.equipe,
                        tournee.agent_nom,
                        tournee.heure_depot_depart,
                        tournee.heure_debut_collecte1,
                        tournee.heure_fin_collecte1,
                        tournee.heure_depart_decharge1,
                        tournee.heure_arrivee_decharge1,
                        tournee.heure_sortie_decharge1,
                        tournee.volume_collecte1 or 0,
                        tournee.heure_debut_collecte2,
                        tournee.heure_fin_collecte2,
                        tournee.heure_depart_decharge2,
                        tournee.heure_arrivee_decharge2,
                        tournee.heure_sortie_decharge2,
                        tournee.volume_collecte2 or 0,
                        tournee.heure_retour_depot,
                        tournee.distance_parcourue_km
                    ]
                })
                resume.to_excel(writer, sheet_name="Résumé", index=False)
                
                if points:
                    points_data = []
                    for p in points:
                        points_data.append({
                            "Collecte": p.collecte_numero,
                            "N° Point": p.point_numero,
                            "Heure": p.heure_passage,
                            "Latitude": p.latitude,
                            "Longitude": p.longitude,
                            "Description": p.description
                        })
                    df_points = pd.DataFrame(points_data)
                    df_points.to_excel(writer, sheet_name="Points de collecte", index=False)
            
            return output.getvalue()
    except Exception as e:
        st.error(f"Erreur export: {e}")
        return None

# ==================== SESSION STATE ====================
if 'points_collecte1' not in st.session_state:
    st.session_state.points_collecte1 = []
if 'points_collecte2' not in st.session_state:
    st.session_state.points_collecte2 = []
if 'gps_actif' not in st.session_state:
    st.session_state.gps_actif = False
if 'position_actuelle' not in st.session_state:
    st.session_state.position_actuelle = None
if 'tournee_en_cours' not in st.session_state:
    st.session_state.tournee_en_cours = None
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'etape_actuelle' not in st.session_state:
    st.session_state.etape_actuelle = "depart"
if 'volume_collecte1' not in st.session_state:
    st.session_state.volume_collecte1 = 0.0
if 'volume_collecte2' not in st.session_state:
    st.session_state.volume_collecte2 = 0.0

# Stockage des horaires
if 'heure_depot_depart' not in st.session_state:
    st.session_state.heure_depot_depart = time(7, 0)
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
if 'heure_retour_depot' not in st.session_state:
    st.session_state.heure_retour_depot = time(14, 45)
if 'distance_totale' not in st.session_state:
    st.session_state.distance_totale = 25.0

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
    
    st.metric("📦 Volume Collecte 1 (déchargé)", f"{st.session_state.volume_collecte1:.1f} m³")
    st.metric("📦 Volume Collecte 2 (déchargé)", f"{st.session_state.volume_collecte2:.1f} m³")
    
    total_volume = st.session_state.volume_collecte1 + st.session_state.volume_collecte2
    st.metric("📊 Volume total déchargé", f"{total_volume:.1f} m³")
    
    st.metric("📍 Points Collecte 1", len(st.session_state.points_collecte1))
    st.metric("📍 Points Collecte 2", len(st.session_state.points_collecte2))
    
    st.markdown("---")
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF</div>', unsafe_allow_html=True)
        if st.session_state.position_actuelle:
            st.write(f"Lat: {st.session_state.position_actuelle['lat']:.6f}")
            st.write(f"Lon: {st.session_state.position_actuelle['lon']:.6f}")

# ==================== ONGLETS ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚛 Configuration", 
    "📍 Collecte 1 & Décharge 1", 
    "📍 Collecte 2 & Décharge 2",
    "📸 Photos",
    "📊 Résumé & Export"
])

# ==================== ONGLET 1 : CONFIGURATION ====================
with tab1:
    st.subheader("🚛 Configuration de la tournée")
    
    if not st.session_state.agent_nom:
        st.warning("⚠️ Veuillez entrer votre nom dans la barre latérale")
    
    col1, col2 = st.columns(2)
    with col1:
        date_tournee = st.date_input("📅 Date", value=date.today())
        equipe_nom = st.selectbox("👥 Équipe", [e[1] for e in get_equipes()])
    with col2:
        quartier_nom = st.selectbox("📍 Quartier", [q[1] for q in get_quartiers()])
        nombre_voyages = st.number_input("🚛 Nombre de voyages", min_value=1, value=1, step=1)
    
    # GPS
    st.markdown("---")
    st.markdown("### 📍 GÉOLOCALISATION")
    
    if st.button("📍 ACTIVER LE GPS", key="gps_activate", use_container_width=True):
        st.session_state.gps_actif = True
        quartier_coords = {
            "NDIOP": (15.121048, -16.686826),
            "Lébou Est": (15.109558, -16.628958),
            "Lébou Ouest": (15.098159, -16.619668),
            "Ngaye Djitté": (15.115900, -16.632128),
            "HLM": (15.117350, -16.635411),
            "Mbambara": (15.115765, -16.632181),
            "Ngaye Diagne": (15.120364, -16.635608)
        }
        if quartier_nom in quartier_coords:
            lat, lon = quartier_coords[quartier_nom]
            st.session_state.position_actuelle = {"lat": lat, "lon": lon, "precision": 10}
        st.success("✅ GPS activé")
    
    # ==================== HORAIRES COMPLETS ====================
    st.markdown("---")
    st.markdown("### 🕐 HORAIRES DE LA TOURNÉE")
    
    # Départ dépôt
    st.markdown("#### 🏭 DÉPART DU DÉPÔT")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_depot_depart = st.time_input("Heure de départ du dépôt", value=st.session_state.heure_depot_depart)
    with col2:
        st.session_state.distance_totale = st.number_input("📏 Distance totale (km)", min_value=0.0, step=0.5, value=st.session_state.distance_totale)
    
    # Collecte 1
    st.markdown("#### 🗑️ COLLECTE 1")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_debut_collecte1 = st.time_input("Début collecte 1", value=st.session_state.heure_debut_collecte1)
    with col2:
        st.session_state.heure_fin_collecte1 = st.time_input("Fin collecte 1", value=st.session_state.heure_fin_collecte1)
    
    # Décharge 1
    st.markdown("#### 🏭 DÉCHARGE 1")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.heure_depart_decharge1 = st.time_input("Départ vers décharge 1", value=st.session_state.heure_depart_decharge1)
    with col2:
        st.session_state.heure_arrivee_decharge1 = st.time_input("Arrivée décharge 1", value=st.session_state.heure_arrivee_decharge1)
    with col3:
        st.session_state.heure_sortie_decharge1 = st.time_input("Sortie décharge 1", value=st.session_state.heure_sortie_decharge1)
    
    # Collecte 2
    st.markdown("#### 🗑️ COLLECTE 2")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.heure_debut_collecte2 = st.time_input("Début collecte 2", value=st.session_state.heure_debut_collecte2)
    with col2:
        st.session_state.heure_fin_collecte2 = st.time_input("Fin collecte 2", value=st.session_state.heure_fin_collecte2)
    
    # Décharge 2
    st.markdown("#### 🏭 DÉCHARGE 2")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.heure_depart_decharge2 = st.time_input("Départ vers décharge 2", value=st.session_state.heure_depart_decharge2)
    with col2:
        st.session_state.heure_arrivee_decharge2 = st.time_input("Arrivée décharge 2", value=st.session_state.heure_arrivee_decharge2)
    with col3:
        st.session_state.heure_sortie_decharge2 = st.time_input("Sortie décharge 2", value=st.session_state.heure_sortie_decharge2)
    
    # Retour dépôt
    st.markdown("#### 🏁 RETOUR AU DÉPÔT")
    st.session_state.heure_retour_depot = st.time_input("Heure de retour au dépôt", value=st.session_state.heure_retour_depot)
    
    observations = st.text_area("📝 Observations générales", height=80)
    
    # Calcul des durées
    st.markdown("---")
    st.markdown("### ⏱️ RÉCAPITULATIF DES DURÉES")
    
    def calc_duree(debut, fin):
        if debut and fin:
            return (fin.hour - debut.hour) * 60 + (fin.minute - debut.minute)
        return 0
    
    duree_collecte1 = calc_duree(st.session_state.heure_debut_collecte1, st.session_state.heure_fin_collecte1)
    duree_trajet_decharge1 = calc_duree(st.session_state.heure_fin_collecte1, st.session_state.heure_arrivee_decharge1)
    duree_decharge1 = calc_duree(st.session_state.heure_arrivee_decharge1, st.session_state.heure_sortie_decharge1)
    duree_collecte2 = calc_duree(st.session_state.heure_debut_collecte2, st.session_state.heure_fin_collecte2)
    duree_trajet_decharge2 = calc_duree(st.session_state.heure_fin_collecte2, st.session_state.heure_arrivee_decharge2)
    duree_decharge2 = calc_duree(st.session_state.heure_arrivee_decharge2, st.session_state.heure_sortie_decharge2)
    duree_retour = calc_duree(st.session_state.heure_sortie_decharge2, st.session_state.heure_retour_depot)
    duree_totale = calc_duree(st.session_state.heure_depot_depart, st.session_state.heure_retour_depot)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("⏱️ Collecte 1", f"{duree_collecte1} min")
        st.metric("🚚 Trajet décharge 1", f"{duree_trajet_decharge1} min")
        st.metric("🏭 Décharge 1", f"{duree_decharge1} min")
    with col2:
        st.metric("⏱️ Collecte 2", f"{duree_collecte2} min")
        st.metric("🚚 Trajet décharge 2", f"{duree_trajet_decharge2} min")
        st.metric("🏭 Décharge 2", f"{duree_decharge2} min")
    with col3:
        st.metric("🏁 Retour", f"{duree_retour} min")
        st.metric("⏰ Temps total", f"{duree_totale} min")
        if st.session_state.volume_collecte1 + st.session_state.volume_collecte2 > 0:
            efficacite = st.session_state.distance_totale / (st.session_state.volume_collecte1 + st.session_state.volume_collecte2)
            st.metric("⚡ Efficacité", f"{efficacite:.1f} km/m³")
    
    # Bouton démarrer
    if st.button("🚀 DÉMARRER LA TOURNÉE", type="primary", use_container_width=True):
        if not st.session_state.agent_nom:
            st.error("❌ Veuillez entrer votre nom")
        else:
            equipe_id = None
            quartier_id = None
            
            with engine.connect() as conn:
                equipe_result = conn.execute(text("SELECT id FROM equipes WHERE nom = :nom"), {"nom": equipe_nom}).first()
                if equipe_result:
                    equipe_id = equipe_result[0]
                quartier_result = conn.execute(text("SELECT id FROM quartiers WHERE nom = :nom"), {"nom": quartier_nom}).first()
                if quartier_result:
                    quartier_id = quartier_result[0]
            
            if equipe_id and quartier_id:
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text("""
                            INSERT INTO tournees (
                                date_tournee, equipe_id, quartier_id,
                                heure_depot_depart,
                                heure_debut_collecte1, heure_fin_collecte1,
                                heure_depart_decharge1, heure_arrivee_decharge1, heure_sortie_decharge1,
                                heure_debut_collecte2, heure_fin_collecte2,
                                heure_depart_decharge2, heure_arrivee_decharge2, heure_sortie_decharge2,
                                heure_retour_depot,
                                distance_parcourue_km, nombre_voyages, observations,
                                agent_nom, statut
                            ) VALUES (
                                :date, :equipe_id, :quartier_id,
                                :h_depart,
                                :h_debut1, :h_fin1,
                                :h_depart_dech1, :h_arrivee_dech1, :h_sortie_dech1,
                                :h_debut2, :h_fin2,
                                :h_depart_dech2, :h_arrivee_dech2, :h_sortie_dech2,
                                :h_retour,
                                :distance, :voyages, :obs,
                                :agent, 'en_cours'
                            )
                            RETURNING id
                        """), {
                            "date": date_tournee,
                            "equipe_id": equipe_id,
                            "quartier_id": quartier_id,
                            "h_depart": st.session_state.heure_depot_depart.strftime("%H:%M:%S"),
                            "h_debut1": st.session_state.heure_debut_collecte1.strftime("%H:%M:%S"),
                            "h_fin1": st.session_state.heure_fin_collecte1.strftime("%H:%M:%S"),
                            "h_depart_dech1": st.session_state.heure_depart_decharge1.strftime("%H:%M:%S"),
                            "h_arrivee_dech1": st.session_state.heure_arrivee_decharge1.strftime("%H:%M:%S"),
                            "h_sortie_dech1": st.session_state.heure_sortie_decharge1.strftime("%H:%M:%S"),
                            "h_debut2": st.session_state.heure_debut_collecte2.strftime("%H:%M:%S"),
                            "h_fin2": st.session_state.heure_fin_collecte2.strftime("%H:%M:%S"),
                            "h_depart_dech2": st.session_state.heure_depart_decharge2.strftime("%H:%M:%S"),
                            "h_arrivee_dech2": st.session_state.heure_arrivee_decharge2.strftime("%H:%M:%S"),
                            "h_sortie_dech2": st.session_state.heure_sortie_decharge2.strftime("%H:%M:%S"),
                            "h_retour": st.session_state.heure_retour_depot.strftime("%H:%M:%S"),
                            "distance": st.session_state.distance_totale,
                            "voyages": nombre_voyages,
                            "obs": observations,
                            "agent": st.session_state.agent_nom
                        })
                        
                        st.session_state.tournee_en_cours = result.fetchone()[0]
                        st.session_state.etape_actuelle = "collecte1"
                        st.session_state.points_collecte1 = []
                        st.session_state.points_collecte2 = []
                        st.session_state.volume_collecte1 = 0.0
                        st.session_state.volume_collecte2 = 0.0
                        
                        conn.commit()
                    
                    st.markdown('<div class="success-box">✅ Tournée démarrée ! Commencez la COLLECTE 1</div>', unsafe_allow_html=True)
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Erreur: {e}")
            else:
                st.error("❌ Équipe ou quartier non trouvé")
    
    if st.session_state.tournee_en_cours:
        st.info(f"🟢 Tournée en cours - ID: {st.session_state.tournee_en_cours}")
        st.info(f"📍 Étape: {st.session_state.etape_actuelle}")

# ==================== ONGLET 2 : COLLECTE 1 & DÉCHARGE 1 ====================
with tab2:
    st.subheader("📍 COLLECTE 1 - Points de collecte")
    
    if not st.session_state.tournee_en_cours:
        st.warning("⚠️ Veuillez d'abord configurer et démarrer une tournée")
    else:
        # Afficher les horaires de la collecte 1
        st.markdown(f"""
        <div class="horaires-box">
        <strong>⏰ Horaires de la COLLECTE 1 :</strong><br>
        🗑️ Début: {st.session_state.heure_debut_collecte1.strftime('%H:%M')}<br>
        🗑️ Fin: {st.session_state.heure_fin_collecte1.strftime('%H:%M')}<br>
        🏭 Départ décharge 1: {st.session_state.heure_depart_decharge1.strftime('%H:%M')}<br>
        🏭 Arrivée décharge 1: {st.session_state.heure_arrivee_decharge1.strftime('%H:%M')}<br>
        🏭 Sortie décharge 1: {st.session_state.heure_sortie_decharge1.strftime('%H:%M')}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="collecte-card">📍 Enregistrez tous les points d\'arrêt de la COLLECTE 1</div>', unsafe_allow_html=True)
        
        # Formulaire d'ajout de point
        with st.form("form_point1", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                if st.session_state.gps_actif and st.session_state.position_actuelle:
                    lat = st.number_input("Latitude", value=st.session_state.position_actuelle["lat"], format="%.6f")
                    lon = st.number_input("Longitude", value=st.session_state.position_actuelle["lon"], format="%.6f")
                else:
                    lat = st.number_input("Latitude", value=15.115000, format="%.6f")
                    lon = st.number_input("Longitude", value=-16.635000, format="%.6f")
                st.caption(f"🕐 Heure du point: {datetime.now().strftime('%H:%M:%S')}")
            with col2:
                description = st.text_area("Description du point", placeholder="Ex: Devant la mosquée, devant l'école...", height=100)
            
            photo_file = st.file_uploader("📸 Photo (optionnel)", type=["jpg", "jpeg", "png"])
            
            submitted = st.form_submit_button("✅ AJOUTER CE POINT", use_container_width=True)
            
            if submitted:
                point_data = {
                    "numero": len(st.session_state.points_collecte1) + 1,
                    "heure": datetime.now(),
                    "lat": lat,
                    "lon": lon,
                    "description": description,
                    "photo": photo_file.getvalue() if photo_file else None,
                    "collecte_numero": 1
                }
                if enregistrer_point_collecte(st.session_state.tournee_en_cours, point_data):
                    st.session_state.points_collecte1.append(point_data)
                    st.success(f"✅ Point {len(st.session_state.points_collecte1)} ajouté à la COLLECTE 1")
                    st.rerun()
        
        # Afficher les points
        if st.session_state.points_collecte1:
            st.markdown("---")
            st.markdown("### 📋 Points de collecte 1")
            for p in st.session_state.points_collecte1:
                st.markdown(f"""
                <div class="point-card">
                    <div>
                        <span class="point-numero">Point {p['numero']}</span>
                        <strong>{p['heure'].strftime('%H:%M:%S')}</strong>
                    </div>
                    <div>📍 {p['lat']:.6f}, {p['lon']:.6f}</div>
                    <div>📝 {p['description'][:100] if p['description'] else 'Pas de description'}</div>
                </div>
                """, unsafe_allow_html=True)
        
        # ==================== SECTION DÉCHARGE 1 ====================
        st.markdown("---")
        st.markdown('<div class="decharge-card">🏭 DÉCHARGE 1 - Enregistrez votre passage et le volume déchargé</div>', unsafe_allow_html=True)
        
        # Volume à décharger
        col1, col2 = st.columns(2)
        with col1:
            volume_decharge1 = st.number_input("📦 Volume déchargé à la décharge 1 (m³)", min_value=0.0, step=0.5, value=0.0, key="volume_decharge1")
        with col2:
            if st.button("💾 ENREGISTRER VOLUME DÉCHARGE 1", use_container_width=True, key="save_decharge1"):
                if volume_decharge1 > 0:
                    if enregistrer_volume_decharge(st.session_state.tournee_en_cours, 1, volume_decharge1):
                        st.session_state.volume_collecte1 = volume_decharge1
                        st.success(f"✅ Volume déchargé enregistré: {volume_decharge1:.1f} m³")
                        st.session_state.etape_actuelle = "collecte2"
                        st.info("📍 Passez maintenant à la COLLECTE 2")
                        st.rerun()
                else:
                    st.warning("⚠️ Veuillez saisir le volume déchargé")
        
        # Enregistrement GPS du passage à la décharge
        if st.button("📍 ENREGISTRER PASSAGE DÉCHARGE 1 (GPS)", use_container_width=True, key="gps_decharge1"):
            if st.session_state.gps_actif and st.session_state.position_actuelle:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description)
                        VALUES (:tid, :heure, 'decharge_1', :lat, :lon, :desc)
                    """), {
                        "tid": st.session_state.tournee_en_cours,
                        "heure": datetime.now(),
                        "lat": st.session_state.position_actuelle["lat"],
                        "lon": st.session_state.position_actuelle["lon"],
                        "desc": f"Passage décharge 1 - Volume: {volume_decharge1:.1f} m³"
                    })
                    conn.commit()
                st.success("✅ Passage décharge 1 enregistré avec GPS")
            else:
                st.warning("⚠️ Activez le GPS pour enregistrer la position")

# ==================== ONGLET 3 : COLLECTE 2 & DÉCHARGE 2 ====================
with tab3:
    st.subheader("📍 COLLECTE 2 - Points de collecte")
    
    if not st.session_state.tournee_en_cours:
        st.warning("⚠️ Veuillez d'abord configurer et démarrer une tournée")
    elif st.session_state.etape_actuelle not in ["collecte2", "decharge2"]:
        st.info("ℹ️ Terminez d'abord la COLLECTE 1 et la DÉCHARGE 1")
    else:
        # Afficher les horaires de la collecte 2
        st.markdown(f"""
        <div class="horaires-box">
        <strong>⏰ Horaires de la COLLECTE 2 :</strong><br>
        🗑️ Début: {st.session_state.heure_debut_collecte2.strftime('%H:%M')}<br>
        🗑️ Fin: {st.session_state.heure_fin_collecte2.strftime('%H:%M')}<br>
        🏭 Départ décharge 2: {st.session_state.heure_depart_decharge2.strftime('%H:%M')}<br>
        🏭 Arrivée décharge 2: {st.session_state.heure_arrivee_decharge2.strftime('%H:%M')}<br>
        🏭 Sortie décharge 2: {st.session_state.heure_sortie_decharge2.strftime('%H:%M')}<br>
        🏁 Retour dépôt: {st.session_state.heure_retour_depot.strftime('%H:%M')}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="collecte-card">📍 Enregistrez tous les points d\'arrêt de la COLLECTE 2</div>', unsafe_allow_html=True)
        
        # Formulaire d'ajout de point
        with st.form("form_point2", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                if st.session_state.gps_actif and st.session_state.position_actuelle:
                    lat = st.number_input("Latitude", value=st.session_state.position_actuelle["lat"], format="%.6f")
                    lon = st.number_input("Longitude", value=st.session_state.position_actuelle["lon"], format="%.6f")
                else:
                    lat = st.number_input("Latitude", value=15.115000, format="%.6f")
                    lon = st.number_input("Longitude", value=-16.635000, format="%.6f")
                st.caption(f"🕐 Heure du point: {datetime.now().strftime('%H:%M:%S')}")
            with col2:
                description = st.text_area("Description du point", placeholder="Ex: Devant le marché, place centrale...", height=100)
            
            photo_file = st.file_uploader("📸 Photo (optionnel)", type=["jpg", "jpeg", "png"])
            
            submitted = st.form_submit_button("✅ AJOUTER CE POINT", use_container_width=True)
            
            if submitted:
                point_data = {
                    "numero": len(st.session_state.points_collecte2) + 1,
                    "heure": datetime.now(),
                    "lat": lat,
                    "lon": lon,
                    "description": description,
                    "photo": photo_file.getvalue() if photo_file else None,
                    "collecte_numero": 2
                }
                if enregistrer_point_collecte(st.session_state.tournee_en_cours, point_data):
                    st.session_state.points_collecte2.append(point_data)
                    st.success(f"✅ Point {len(st.session_state.points_collecte2)} ajouté à la COLLECTE 2")
                    st.rerun()
        
        # Afficher les points
        if st.session_state.points_collecte2:
            st.markdown("---")
            st.markdown("### 📋 Points de collecte 2")
            for p in st.session_state.points_collecte2:
                st.markdown(f"""
                <div class="point-card">
                    <div>
                        <span class="point-numero">Point {p['numero']}</span>
                        <strong>{p['heure'].strftime('%H:%M:%S')}</strong>
                    </div>
                    <div>📍 {p['lat']:.6f}, {p['lon']:.6f}</div>
                    <div>📝 {p['description'][:100] if p['description'] else 'Pas de description'}</div>
                </div>
                """, unsafe_allow_html=True)
        
        # ==================== SECTION DÉCHARGE 2 ====================
        st.markdown("---")
        st.markdown('<div class="decharge-card">🏭 DÉCHARGE 2 - Enregistrez votre passage et le volume déchargé</div>', unsafe_allow_html=True)
        
        # Volume à décharger
        col1, col2 = st.columns(2)
        with col1:
            volume_decharge2 = st.number_input("📦 Volume déchargé à la décharge 2 (m³)", min_value=0.0, step=0.5, value=0.0, key="volume_decharge2")
        with col2:
            if st.button("💾 ENREGISTRER VOLUME DÉCHARGE 2", use_container_width=True, key="save_decharge2"):
                if volume_decharge2 > 0:
                    if enregistrer_volume_decharge(st.session_state.tournee_en_cours, 2, volume_decharge2):
                        st.session_state.volume_collecte2 = volume_decharge2
                        st.success(f"✅ Volume déchargé enregistré: {volume_decharge2:.1f} m³")
                        st.session_state.etape_actuelle = "retour"
                        
                        # Terminer la tournée
                        volume_total = st.session_state.volume_collecte1 + st.session_state.volume_collecte2
                        with engine.connect() as conn:
                            conn.execute(text("""
                                UPDATE tournees 
                                SET volume_m3 = :volume, statut = 'termine'
                                WHERE id = :tid
                            """), {"volume": volume_total, "tid": st.session_state.tournee_en_cours})
                            conn.commit()
                        
                        st.markdown(f'<div class="success-box">✅ Tournée terminée ! Volume total déchargé: {volume_total:.1f} m³</div>', unsafe_allow_html=True)
                        st.balloons()
                        st.rerun()
                else:
                    st.warning("⚠️ Veuillez saisir le volume déchargé")
        
        # Enregistrement GPS du passage à la décharge
        if st.button("📍 ENREGISTRER PASSAGE DÉCHARGE 2 (GPS)", use_container_width=True, key="gps_decharge2"):
            if st.session_state.gps_actif and st.session_state.position_actuelle:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description)
                        VALUES (:tid, :heure, 'decharge_2', :lat, :lon, :desc)
                    """), {
                        "tid": st.session_state.tournee_en_cours,
                        "heure": datetime.now(),
                        "lat": st.session_state.position_actuelle["lat"],
                        "lon": st.session_state.position_actuelle["lon"],
                        "desc": f"Passage décharge 2 - Volume: {volume_decharge2:.1f} m³"
                    })
                    conn.commit()
                st.success("✅ Passage décharge 2 enregistré avec GPS")
            else:
                st.warning("⚠️ Activez le GPS pour enregistrer la position")

# ==================== ONGLET 4 : PHOTOS ====================
with tab4:
    st.subheader("📸 Photos des points de collecte")
    
    st.markdown("### 🗑️ COLLECTE 1")
    for p in st.session_state.points_collecte1:
        if p.get("photo"):
            st.image(p["photo"], caption=f"Point {p['numero']} - {p['description'][:50] if p['description'] else 'Sans description'}", width=300)
    
    st.markdown("### 🗑️ COLLECTE 2")
    for p in st.session_state.points_collecte2:
        if p.get("photo"):
            st.image(p["photo"], caption=f"Point {p['numero']} - {p['description'][:50] if p['description'] else 'Sans description'}", width=300)

# ==================== ONGLET 5 : RÉSUMÉ & EXPORT ====================
with tab5:
    st.subheader("📊 Résumé de la tournée")
    
    if st.session_state.tournee_en_cours:
        total_volume = st.session_state.volume_collecte1 + st.session_state.volume_collecte2
        
        # Résumé des horaires
        st.markdown("### ⏰ RÉSUMÉ DES HORAIRES")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🏭 DÉPART**")
            st.write(f"Départ dépôt: {st.session_state.heure_depot_depart.strftime('%H:%M')}")
            
            st.markdown("**🗑️ COLLECTE 1**")
            st.write(f"Début: {st.session_state.heure_debut_collecte1.strftime('%H:%M')}")
            st.write(f"Fin: {st.session_state.heure_fin_collecte1.strftime('%H:%M')}")
            
            st.markdown("**🏭 DÉCHARGE 1**")
            st.write(f"Départ: {st.session_state.heure_depart_decharge1.strftime('%H:%M')}")
            st.write(f"Arrivée: {st.session_state.heure_arrivee_decharge1.strftime('%H:%M')}")
            st.write(f"Sortie: {st.session_state.heure_sortie_decharge1.strftime('%H:%M')}")
            st.write(f"**Volume déchargé: {st.session_state.volume_collecte1:.1f} m³**")
        
        with col2:
            st.markdown("**🗑️ COLLECTE 2**")
            st.write(f"Début: {st.session_state.heure_debut_collecte2.strftime('%H:%M')}")
            st.write(f"Fin: {st.session_state.heure_fin_collecte2.strftime('%H:%M')}")
            
            st.markdown("**🏭 DÉCHARGE 2**")
            st.write(f"Départ: {st.session_state.heure_depart_decharge2.strftime('%H:%M')}")
            st.write(f"Arrivée: {st.session_state.heure_arrivee_decharge2.strftime('%H:%M')}")
            st.write(f"Sortie: {st.session_state.heure_sortie_decharge2.strftime('%H:%M')}")
            st.write(f"**Volume déchargé: {st.session_state.volume_collecte2:.1f} m³**")
            
            st.markdown("**🏁 RETOUR**")
            st.write(f"Retour dépôt: {st.session_state.heure_retour_depot.strftime('%H:%M')}")
        
        st.markdown("---")
        st.markdown("### 📊 STATISTIQUES")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📦 Volume déchargé 1", f"{st.session_state.volume_collecte1:.1f} m³")
        with col2:
            st.metric("📦 Volume déchargé 2", f"{st.session_state.volume_collecte2:.1f} m³")
        with col3:
            st.metric("📊 Volume total déchargé", f"{total_volume:.1f} m³")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📍 Points Collecte 1", len(st.session_state.points_collecte1))
        with col2:
            st.metric("📍 Points Collecte 2", len(st.session_state.points_collecte2))
        
        st.metric("📏 Distance totale", f"{st.session_state.distance_totale:.1f} km")
        
        if total_volume > 0:
            efficacite = st.session_state.distance_totale / total_volume
            st.metric("⚡ Efficacité (km/m³)", f"{efficacite:.2f}")
        
        if st.button("📥 EXPORTER CETTE TOURNÉE EN EXCEL", use_container_width=True):
            excel_data = exporter_excel(st.session_state.tournee_en_cours)
            if excel_data:
                st.download_button(
                    label="Télécharger Excel",
                    data=excel_data,
                    file_name=f"tournee_{st.session_state.tournee_en_cours}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    # Historique
    st.markdown("---")
    st.subheader("📁 Historique des tournées")
    
    col1, col2 = st.columns(2)
    with col1:
        date_debut = st.date_input("Date début", value=date.today() - timedelta(days=30))
    with col2:
        date_fin = st.date_input("Date fin", value=date.today())
    
    with engine.connect() as conn:
        tournees = conn.execute(text("""
            SELECT 
                t.id, t.date_tournee, q.nom as quartier, e.nom as equipe,
                t.volume_collecte1, t.volume_collecte2,
                (t.volume_collecte1 + t.volume_collecte2) as volume_total,
                t.agent_nom,
                t.heure_depot_depart,
                t.heure_retour_depot,
                (SELECT COUNT(*) FROM points_collecte WHERE tournee_id = t.id) as nb_points
            FROM tournees t
            JOIN quartiers q ON t.quartier_id = q.id
            JOIN equipes e ON t.equipe_id = e.id
            WHERE t.date_tournee BETWEEN :debut AND :fin
            ORDER BY t.date_tournee DESC
        """), {"debut": date_debut, "fin": date_fin}).fetchall()
        
        if tournees:
            df = pd.DataFrame(tournees, columns=['ID', 'Date', 'Quartier', 'Équipe', 
                                                  'Vol Déch 1 (m³)', 'Vol Déch 2 (m³)', 'Total (m³)', 
                                                  'Agent', 'Départ', 'Retour', 'Nb points'])
            st.dataframe(df, use_container_width=True)

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📱 Interface agent - Commune de Mékhé | Agent: {st.session_state.agent_nom or 'Non connecté'} | Volume enregistré à la décharge | GPS intégré")

# ==================== API DE SYNCHRONISATION ====================
query_params = st.query_params

if "sync" in query_params:
    try:
        st.subheader("🔄 Synchronisation des données")
        st.info("Traitement des données envoyées par l'application mobile...")
        
        data_str = query_params.get("data", "")
        if data_str:
            data = json.loads(data_str)
            collecte = data.get('collecte')
            points = data.get('points', [])
            
            if collecte:
                quartier_id = get_quartier_id(collecte.get('quartier'))
                equipe_id = get_equipe_id(collecte.get('equipe'))
                
                if quartier_id and equipe_id:
                    with engine.connect() as conn:
                        result = conn.execute(text("""
                            INSERT INTO tournees (
                                date_tournee, quartier_id, equipe_id, agent_nom,
                                volume_collecte1, volume_collecte2, observations,
                                heure_depot_depart, heure_retour_depot, statut
                            ) VALUES (
                                :date, :qid, :eid, :agent,
                                :vol1, :vol2, :obs,
                                :depart, :retour, 'termine'
                            )
                            RETURNING id
                        """), {
                            "date": collecte.get('date'),
                            "qid": quartier_id,
                            "eid": equipe_id,
                            "agent": collecte.get('agent', 'Agent PWA'),
                            "vol1": collecte.get('volume1', 0),
                            "vol2": collecte.get('volume2', 0),
                            "obs": collecte.get('observations', ''),
                            "depart": collecte.get('heureDepart', '07:00:00'),
                            "retour": collecte.get('heureRetour', '14:00:00')
                        })
                        
                        tournee_id = result.fetchone()[0]
                        
                        for i, point in enumerate(points):
                            conn.execute(text("""
                                INSERT INTO points_collecte (
                                    tournee_id, point_numero, heure_passage,
                                    latitude, longitude, description, collecte_numero
                                ) VALUES (
                                    :tid, :num, :heure, :lat, :lon, :desc, :collecte_num
                                )
                            """), {
                                "tid": tournee_id,
                                "num": i + 1,
                                "heure": datetime.now(),
                                "lat": point.get('lat'),
                                "lon": point.get('lon'),
                                "desc": point.get('description', ''),
                                "collecte_num": 1 if point.get('type') == 'collecte1' else 2
                            })
                        
                        conn.commit()
                    
                    st.success(f"✅ Synchronisation réussie ! {len(points)} points enregistrés")
                    st.balloons()
                else:
                    st.error("❌ Quartier ou équipe non trouvé")
            else:
                st.error("❌ Données de collecte manquantes")
        else:
            st.warning("⚠️ Aucune donnée à synchroniser")
            
    except Exception as e:
        st.error(f"❌ Erreur: {e}")
    
    st.stop()