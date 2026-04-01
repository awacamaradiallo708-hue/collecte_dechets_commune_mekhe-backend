"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec saisie des heures, volumes, champ unique pour les coordonnées,
affichage des points, carte interactive et calcul automatique de la distance.
Export Excel des collectes du jour.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from io import BytesIO
import re
from math import radians, sin, cos, sqrt, atan2

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
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte</h1><p>Commune de Mékhé | Saisie des collectes | Carte interactive</p></div>', unsafe_allow_html=True)

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

def haversine(lat1, lon1, lat2, lon2):
    """Distance en km entre deux points GPS"""
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

def exporter_collectes_agent(date_filter, agent_nom):
    """Exporte toutes les collectes de l'agent pour une date donnée"""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    t.date_tournee,
                    t.agent_nom,
                    q.nom as quartier,
                    e.nom as equipe,
                    t.volume_collecte1,
                    t.volume_collecte2,
                    t.volume_m3,
                    t.heure_depot_depart,
                    t.heure_retour_depot,
                    t.distance_parcourue_km
                FROM tournees t
                JOIN quartiers q ON t.quartier_id = q.id
                JOIN equipes e ON t.equipe_id = e.id
                WHERE t.statut = 'termine'
                  AND t.date_tournee = :date
                  AND t.agent_nom = :agent
                ORDER BY t.created_at
            """)
            df = pd.read_sql(query, conn, params={"date": date_filter, "agent": agent_nom})
            if df.empty:
                return None
            def calc_duree(row):
                try:
                    depart = datetime.strptime(row['heure_depot_depart'], "%H:%M:%S") if row['heure_depot_depart'] else None
                    retour = datetime.strptime(row['heure_retour_depot'], "%H:%M:%S") if row['heure_retour_depot'] else None
                    if depart and retour:
                        minutes = (retour - depart).total_seconds() / 60
                        return formater_duree(minutes)
                except:
                    pass
                return "N/A"
            df['durée'] = df.apply(calc_duree, axis=1)
            df['heure_depot_depart'] = df['heure_depot_depart'].str[:5]
            df['heure_retour_depot'] = df['heure_retour_depot'].str[:5]
            return df
    except Exception as e:
        st.error(f"Erreur export: {e}")
        return None

# ==================== SESSION STATE ====================
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'date_tournee' not in st.session_state:
    st.session_state.date_tournee = date.today()
if 'quartier_nom' not in st.session_state:
    st.session_state.quartier_nom = ""
if 'volume1' not in st.session_state:
    st.session_state.volume1 = 0.0
if 'volume2' not in st.session_state:
    st.session_state.volume2 = 0.0
if 'collecte1_validee' not in st.session_state:
    st.session_state.collecte1_validee = False
if 'collecte2_validee' not in st.session_state:
    st.session_state.collecte2_validee = False
if 'collecte2_optionnelle' not in st.session_state:
    st.session_state.collecte2_optionnelle = False
if 'temps_debut_tournee' not in st.session_state:
    st.session_state.temps_debut_tournee = None
if 'tournee_id' not in st.session_state:
    st.session_state.tournee_id = None
if 'points_etape' not in st.session_state:
    st.session_state.points_etape = []      # points des étapes
if 'points_ajoutes' not in st.session_state:
    st.session_state.points_ajoutes = []    # points libres
if 'distance_totale' not in st.session_state:
    st.session_state.distance_totale = 0.0

# Heures par défaut (saisie manuelle)
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
    agent_nom_input = st.text_input("✍️ Votre nom", value=st.session_state.agent_nom, placeholder="Ex: Alioune Diop")
    if agent_nom_input:
        st.session_state.agent_nom = agent_nom_input
        st.success(f"✅ Connecté: {agent_nom_input}")
    
    st.markdown("---")
    st.markdown("### 📍 Points supplémentaires (optionnel)")
    st.markdown("""
    Pour ajouter un point libre (ex: dépôt sauvage) :
    1. Ouvrez [Google Maps](https://www.google.com/maps/search/ma+position) et copiez les coordonnées.
    2. Collez-les ci‑dessous.
    """)
    coords_libre = st.text_input("Coordonnées (latitude, longitude)", key="coords_libre", placeholder="Ex: 15.121048, -16.686826")
    desc_libre = st.text_input("Description", placeholder="Ex: Dépôt sauvage")
    if st.button("➕ Ajouter ce point", use_container_width=True):
        if coords_libre.strip():
            match = re.search(r"([-+]?\d+\.\d+)\s*,\s*([-+]?\d+\.\d+)", coords_libre)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                st.session_state.points_ajoutes.append({
                    "type": "point_libre",
                    "titre": desc_libre or "Point libre",
                    "lat": lat,
                    "lon": lon,
                    "heure": datetime.now().strftime("%H:%M:%S"),
                    "collecte": None
                })
                st.success(f"✅ Point ajouté : {lat}, {lon}")
            else:
                st.error("Format invalide. Utilisez 'latitude, longitude'")
        else:
            st.warning("Veuillez entrer des coordonnées")
    
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
    st.metric("📏 Distance totale", f"{st.session_state.distance_totale:.2f} km")
    
    st.markdown("---")
    # Export Excel des collectes de l'agent pour la date sélectionnée
    if st.button("📥 EXPORTER MES COLLECTES DU JOUR", use_container_width=True):
        if st.session_state.agent_nom:
            df = exporter_collectes_agent(st.session_state.date_tournee, st.session_state.agent_nom)
            if df is not None and not df.empty:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name="Mes collectes", index=False)
                st.download_button(
                    label="📊 Télécharger Excel",
                    data=output.getvalue(),
                    file_name=f"collectes_{st.session_state.agent_nom}_{st.session_state.date_tournee.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Aucune collecte enregistrée pour cette date.")
        else:
            st.warning("Veuillez saisir votre nom d'abord.")

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
    st.session_state.heure_depot_depart = st.text_input("Heure de départ du dépôt", value=st.session_state.heure_depot_depart)
    
    st.markdown("**🗑️ COLLECTE 1**")
    st.session_state.heure_debut_collecte1 = st.text_input("Heure début collecte 1", value=st.session_state.heure_debut_collecte1)
    st.session_state.heure_fin_collecte1 = st.text_input("Heure fin collecte 1", value=st.session_state.heure_fin_collecte1)
    
    st.markdown("**🚛 DÉCHARGE 1**")
    st.session_state.heure_depart_decharge1 = st.text_input("Heure départ décharge 1", value=st.session_state.heure_depart_decharge1)
    st.session_state.heure_arrivee_decharge1 = st.text_input("Heure arrivée décharge 1", value=st.session_state.heure_arrivee_decharge1)
    st.session_state.heure_sortie_decharge1 = st.text_input("Heure sortie décharge 1", value=st.session_state.heure_sortie_decharge1)

with col2:
    st.markdown("**🗑️ COLLECTE 2** (optionnel)")
    st.session_state.heure_debut_collecte2 = st.text_input("Heure début collecte 2", value=st.session_state.heure_debut_collecte2)
    st.session_state.heure_fin_collecte2 = st.text_input("Heure fin collecte 2", value=st.session_state.heure_fin_collecte2)
    
    st.markdown("**🚛 DÉCHARGE 2**")
    st.session_state.heure_depart_decharge2 = st.text_input("Heure départ décharge 2", value=st.session_state.heure_depart_decharge2)
    st.session_state.heure_arrivee_decharge2 = st.text_input("Heure arrivée décharge 2", value=st.session_state.heure_arrivee_decharge2)
    st.session_state.heure_sortie_decharge2 = st.text_input("Heure sortie décharge 2", value=st.session_state.heure_sortie_decharge2)
    
    st.markdown("**🏁 RETOUR**")
    st.session_state.heure_retour_depot = st.text_input("Heure retour dépôt", value=st.session_state.heure_retour_depot)

# ==================== COLLECTE 1 ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 COLLECTE 1</div>', unsafe_allow_html=True)

if not st.session_state.collecte1_validee:
    
    points_etapes1 = [
        ("🏭 DÉPART DÉPÔT", "depart_depot", "heure_depot_depart"),
        ("🗑️ DÉBUT COLLECTE 1", "debut_collecte", "heure_debut_collecte1"),
        ("🗑️ FIN COLLECTE 1", "fin_collecte", "heure_fin_collecte1"),
        ("🚛 DÉPART DÉCHARGE 1", "depart_decharge", "heure_depart_decharge1"),
        ("🏭 ARRIVÉE DÉCHARGE 1", "arrivee_decharge", "heure_arrivee_decharge1"),
        ("🏭 SORTIE DÉCHARGE 1 + VOLUME", "sortie_decharge", "heure_sortie_decharge1")
    ]
    
    for titre, type_point, heure_key in points_etapes1:
        st.markdown(f"#### {titre}")
        heure = st.session_state[heure_key]
        
        if type_point == "sortie_decharge":
            col1, col2 = st.columns([2, 1])
            with col1:
                st.caption(f"Heure: {heure}")
            with col2:
                volume1 = st.number_input("Volume déchargé (m³)", min_value=0.0, step=0.5, key="vol1", value=st.session_state.volume1)
            if st.button(f"💾 Enregistrer {titre}", key=f"btn_vol_{type_point}", use_container_width=True):
                if volume1 > 0:
                    st.session_state.volume1 = volume1
                    st.success(f"✅ Volume enregistré : {volume1} m³")
                else:
                    st.warning("⚠️ Veuillez saisir un volume")
        else:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"Heure: {heure}")
                coords_input = st.text_input("Coordonnées (latitude, longitude)", key=f"coords_{type_point}", placeholder="Ex: 15.121048, -16.686826")
            with col2:
                if st.button(f"📍 Enregistrer", key=f"btn_{type_point}", use_container_width=True):
                    if coords_input.strip():
                        match = re.search(r"([-+]?\d+\.\d+)\s*,\s*([-+]?\d+\.\d+)", coords_input)
                        if match:
                            lat = float(match.group(1))
                            lon = float(match.group(2))
                            # Vérifier si ce point existe déjà pour éviter les doublons
                            existing = any(p.get("type") == type_point for p in st.session_state.points_etape)
                            if not existing:
                                st.session_state.points_etape.append({
                                    "type": type_point,
                                    "titre": titre,
                                    "lat": lat,
                                    "lon": lon,
                                    "heure": heure,
                                    "collecte": 1
                                })
                                st.success(f"✅ Point enregistré : {lat}, {lon}")
                            else:
                                st.warning("Ce point a déjà été enregistré.")
                        else:
                            st.error("Format invalide. Utilisez 'latitude, longitude'")
                    else:
                        st.warning("Veuillez entrer les coordonnées")
    
    # Validation Collecte 1
    st.markdown("---")
    if st.button("✅ VALIDER COLLECTE 1", type="primary", use_container_width=True):
        if st.session_state.volume1 > 0:
            # On vérifie que tous les points obligatoires sont présents
            points_obligatoires = ["depart_depot", "debut_collecte", "fin_collecte", "depart_decharge", "arrivee_decharge"]
            manquants = [p for p in points_obligatoires if not any(pt["type"] == p for pt in st.session_state.points_etape)]
            if manquants:
                st.warning(f"Points manquants : {', '.join(manquants)}")
            else:
                st.session_state.collecte1_validee = True
                # Calcul de la distance totale après validation
                points_ordonnes = sorted(st.session_state.points_etape, key=lambda x: (
                    x["collecte"], 
                    ["depart_depot","debut_collecte","fin_collecte","depart_decharge","arrivee_decharge","sortie_decharge"].index(x["type"])
                ))
                distance = 0.0
                for i in range(1, len(points_ordonnes)):
                    p1 = points_ordonnes[i-1]
                    p2 = points_ordonnes[i]
                    distance += haversine(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
                st.session_state.distance_totale = distance
                st.success("✅ Collecte 1 validée")
                st.rerun()
        else:
            st.warning("⚠️ Veuillez enregistrer le volume")

else:
    st.success("✅ Collecte 1 terminée")
    st.write(f"📦 Volume: {st.session_state.volume1:.1f} m³")

# ==================== COLLECTE 2 ====================
st.markdown("---")
st.markdown('<div class="collecte2-card">🚛 COLLECTE 2 (OPTIONNELLE)</div>', unsafe_allow_html=True)

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
        
        points_etapes2 = [
            ("🗑️ DÉBUT COLLECTE 2", "debut_collecte2", "heure_debut_collecte2"),
            ("🗑️ FIN COLLECTE 2", "fin_collecte2", "heure_fin_collecte2"),
            ("🚛 DÉPART DÉCHARGE 2", "depart_decharge2", "heure_depart_decharge2"),
            ("🏭 ARRIVÉE DÉCHARGE 2", "arrivee_decharge2", "heure_arrivee_decharge2"),
            ("🏭 SORTIE DÉCHARGE 2 + VOLUME", "sortie_decharge2", "heure_sortie_decharge2"),
            ("🏁 RETOUR DÉPÔT", "retour_depot", "heure_retour_depot")
        ]
        
        for titre, type_point, heure_key in points_etapes2:
            st.markdown(f"#### {titre}")
            heure = st.session_state[heure_key]
            
            if type_point == "sortie_decharge2":
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.caption(f"Heure: {heure}")
                with col2:
                    volume2 = st.number_input("Volume déchargé (m³)", min_value=0.0, step=0.5, key="vol2", value=st.session_state.volume2)
                if st.button(f"💾 Enregistrer {titre}", key=f"btn_vol_{type_point}", use_container_width=True):
                    if volume2 > 0:
                        st.session_state.volume2 = volume2
                        st.success(f"✅ Volume enregistré : {volume2} m³")
                    else:
                        st.warning("⚠️ Veuillez saisir un volume")
            else:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"Heure: {heure}")
                    coords_input = st.text_input("Coordonnées (latitude, longitude)", key=f"coords_{type_point}", placeholder="Ex: 15.121048, -16.686826")
                with col2:
                    if st.button(f"📍 Enregistrer", key=f"btn_{type_point}", use_container_width=True):
                        if coords_input.strip():
                            match = re.search(r"([-+]?\d+\.\d+)\s*,\s*([-+]?\d+\.\d+)", coords_input)
                            if match:
                                lat = float(match.group(1))
                                lon = float(match.group(2))
                                existing = any(p.get("type") == type_point for p in st.session_state.points_etape)
                                if not existing:
                                    st.session_state.points_etape.append({
                                        "type": type_point,
                                        "titre": titre,
                                        "lat": lat,
                                        "lon": lon,
                                        "heure": heure,
                                        "collecte": 2
                                    })
                                    st.success(f"✅ Point enregistré : {lat}, {lon}")
                                else:
                                    st.warning("Ce point a déjà été enregistré.")
                            else:
                                st.error("Format invalide. Utilisez 'latitude, longitude'")
                        else:
                            st.warning("Veuillez entrer les coordonnées")
        
        st.markdown("---")
        if st.button("✅ VALIDER COLLECTE 2", type="primary", use_container_width=True):
            if st.session_state.volume2 > 0:
                # Recalcul de la distance totale après la collecte 2
                points_ordonnes = sorted(st.session_state.points_etape, key=lambda x: (
                    x["collecte"], 
                    ["depart_depot","debut_collecte","fin_collecte","depart_decharge","arrivee_decharge","sortie_decharge",
                     "debut_collecte2","fin_collecte2","depart_decharge2","arrivee_decharge2","sortie_decharge2","retour_depot"].index(x["type"])
                ))
                distance = 0.0
                for i in range(1, len(points_ordonnes)):
                    p1 = points_ordonnes[i-1]
                    p2 = points_ordonnes[i]
                    distance += haversine(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
                st.session_state.distance_totale = distance
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
    
    if st.button("💾 ENREGISTRER LA TOURNÉE", type="primary", use_container_width=True):
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
                    
                    # Sauvegarder tous les points (étapes + libres)
                    tous_points = st.session_state.points_etape + st.session_state.points_ajoutes
                    for point in tous_points:
                        conn.execute(text("""
                            INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description, collecte_numero)
                            VALUES (:tid, :heure, :type, :lat, :lon, :desc, :collecte)
                        """), {
                            "tid": tournee_id,
                            "heure": datetime.now(),
                            "type": point["type"],
                            "lat": point["lat"],
                            "lon": point["lon"],
                            "desc": f"{point['titre']} - {point['heure']}",
                            "collecte": point.get("collecte")
                        })
                    conn.commit()
                
                st.balloons()
                st.success("✅ Tournée enregistrée !")
                
                # Réinitialiser pour une nouvelle tournée
                if st.button("🔄 NOUVELLE TOURNÉE", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key not in ['agent_nom']:
                            del st.session_state[key]
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erreur lors de l'enregistrement: {e}")

# ==================== AFFICHAGE DES POINTS ET CARTE ====================
st.markdown("---")
st.markdown("### 📍 Points enregistrés")

if st.session_state.points_etape or st.session_state.points_ajoutes:
    tous_points = st.session_state.points_etape + st.session_state.points_ajoutes
    df_points = pd.DataFrame(tous_points)
    
    # Tableau récapitulatif
    st.dataframe(df_points[["titre", "heure", "lat", "lon"]], use_container_width=True)
    
    # Carte interactive
    st.markdown("### 🗺️ Carte interactive")
    
    couleurs = {
        "depart_depot": "green",
        "debut_collecte": "blue",
        "fin_collecte": "blue",
        "depart_decharge": "orange",
        "arrivee_decharge": "red",
        "sortie_decharge": "purple",
        "debut_collecte2": "blue",
        "fin_collecte2": "blue",
        "depart_decharge2": "orange",
        "arrivee_decharge2": "red",
        "sortie_decharge2": "purple",
        "retour_depot": "brown",
        "point_libre": "gray"
    }
    
    noms_pour_legende = {
        "depart_depot": "🏭 Départ dépôt",
        "debut_collecte": "🗑️ Début collecte 1",
        "fin_collecte": "🗑️ Fin collecte 1",
        "depart_decharge": "🚛 Départ décharge 1",
        "arrivee_decharge": "🏭 Arrivée décharge 1",
        "sortie_decharge": "🏭 Sortie décharge 1",
        "debut_collecte2": "🗑️ Début collecte 2",
        "fin_collecte2": "🗑️ Fin collecte 2",
        "depart_decharge2": "🚛 Départ décharge 2",
        "arrivee_decharge2": "🏭 Arrivée décharge 2",
        "sortie_decharge2": "🏭 Sortie décharge 2",
        "retour_depot": "🏁 Retour dépôt",
        "point_libre": "📍 Point libre"
    }
    df_points["nom_affichage"] = df_points["type"].map(noms_pour_legende)
    
    fig = px.scatter_mapbox(
        df_points,
        lat="lat",
        lon="lon",
        color="type",
        hover_name="nom_affichage",
        hover_data={"heure": True, "collecte": True},
        color_discrete_map=couleurs,
        zoom=13,
        center={"lat": 15.11, "lon": -16.65},
        title="Itinéraire de la tournée",
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
        mapbox_zoom=13,
        margin={"r": 0, "t": 40, "l": 0, "b": 0}
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Détail des distances entre points
    if len(df_points) > 1:
        st.markdown("### 📏 Distances entre points")
        distances = []
        for i in range(1, len(df_points)):
            p1 = df_points.iloc[i-1]
            p2 = df_points.iloc[i]
            d = haversine(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
            distances.append({
                "De": p1["nom_affichage"],
                "À": p2["nom_affichage"],
                "Distance (km)": round(d, 2)
            })
        st.dataframe(pd.DataFrame(distances), use_container_width=True)
        st.info(f"Distance totale : **{st.session_state.distance_totale:.2f} km**")

else:
    st.info("Aucun point enregistré pour l'instant.")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"👤 Agent: {st.session_state.agent_nom or 'Non connecté'} | 🗑️ Commune de Mékhé")
