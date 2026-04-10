"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
VERSION BOUTONS VOCAUX (fiable sur cloud)
- Toutes les heures (départ, collecte1, décharge1, collecte2, décharge2, retour)
- Collecte 2 optionnelle
- Boutons en Wolof/Français
- Google Maps intégré
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from io import BytesIO
import folium
from streamlit_folium import folium_static
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Agent Collecte - Mékhé",
    page_icon="🗑️",
    layout="wide"
)

# ==================== CONNEXION BASE NEON.TECH ====================
DATABASE_URL = "postgresql://neondb_owner:npg_43LqPNrhlzWo@ep-misty-mode-al5c7s4f-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

@st.cache_resource
def init_connection():
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.warning(f"⚠️ Mode démo: {e}")
        return None

engine = init_connection()

# ==================== STYLE ====================
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
    .btn-vocal {
        font-size: 18px !important;
        font-weight: bold !important;
        padding: 12px !important;
    }
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
        border-radius: 10px;
    }
    .horaire-row {
        background-color: #f5f5f5;
        padding: 0.5rem;
        border-radius: 8px;
        margin: 0.2rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🗑️ Agent de Collecte - Commune de Mékhé</h1>
    <p>Cliquez sur les boutons pour enregistrer | Wax sa réew mi</p>
</div>
""", unsafe_allow_html=True)

# ==================== FONCTIONS ====================
def get_quartiers():
    return [(1, "HLM"), (2, "NDIOP"), (3, "LEBOU EST"), (4, "NGAYE DIAGNE"), (5, "MAMBARA"), (6, "NGAYE DJITTE"), (7, "LEBOU OUEST")]

def get_equipes():
    return [(1, "Équipe A"), (2, "Équipe B"), (3, "Équipe C"), (4, "Équipe D")]

def init_base_donnees():
    """Initialise la base avec les données par défaut"""
    if not engine:
        return
    with engine.connect() as conn:
        # Vérifier et créer les quartiers
        result = conn.execute(text("SELECT COUNT(*) FROM quartiers"))
        if result.fetchone()[0] == 0:
            for qid, nom in get_quartiers():
                conn.execute(text("INSERT INTO quartiers (id, nom, actif) VALUES (:id, :nom, true)"), {"id": qid, "nom": nom})
        # Vérifier et créer les équipes
        result = conn.execute(text("SELECT COUNT(*) FROM equipes"))
        if result.fetchone()[0] == 0:
            for eid, nom in get_equipes():
                conn.execute(text("INSERT INTO equipes (id, nom, actif) VALUES (:id, :nom, true)"), {"id": eid, "nom": nom})
        conn.commit()

# ==================== SESSION STATE ====================
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'agent_prenom' not in st.session_state:
    st.session_state.agent_prenom = ""
if 'date_tournee' not in st.session_state:
    st.session_state.date_tournee = date.today()
if 'quartier_id' not in st.session_state:
    st.session_state.quartier_id = 1
if 'equipe_id' not in st.session_state:
    st.session_state.equipe_id = 1

# Volumes
if 'volume1' not in st.session_state:
    st.session_state.volume1 = 0.0
if 'volume2' not in st.session_state:
    st.session_state.volume2 = 0.0

# Horaires collecte 1
if 'heure_depot_depart' not in st.session_state:
    st.session_state.heure_depot_depart = ""
if 'heure_debut_collecte1' not in st.session_state:
    st.session_state.heure_debut_collecte1 = ""
if 'heure_fin_collecte1' not in st.session_state:
    st.session_state.heure_fin_collecte1 = ""
if 'heure_depart_decharge1' not in st.session_state:
    st.session_state.heure_depart_decharge1 = ""
if 'heure_arrivee_decharge1' not in st.session_state:
    st.session_state.heure_arrivee_decharge1 = ""
if 'heure_sortie_decharge1' not in st.session_state:
    st.session_state.heure_sortie_decharge1 = ""

# Horaires collecte 2
if 'heure_debut_collecte2' not in st.session_state:
    st.session_state.heure_debut_collecte2 = ""
if 'heure_fin_collecte2' not in st.session_state:
    st.session_state.heure_fin_collecte2 = ""
if 'heure_depart_decharge2' not in st.session_state:
    st.session_state.heure_depart_decharge2 = ""
if 'heure_arrivee_decharge2' not in st.session_state:
    st.session_state.heure_arrivee_decharge2 = ""
if 'heure_sortie_decharge2' not in st.session_state:
    st.session_state.heure_sortie_decharge2 = ""

if 'heure_retour_depot' not in st.session_state:
    st.session_state.heure_retour_depot = ""

# Statuts
if 'collecte1_validee' not in st.session_state:
    st.session_state.collecte1_validee = False
if 'collecte2_optionnelle' not in st.session_state:
    st.session_state.collecte2_optionnelle = False
if 'collecte2_validee' not in st.session_state:
    st.session_state.collecte2_validee = False

if 'points' not in st.session_state:
    st.session_state.points = []
if 'derniere_position' not in st.session_state:
    st.session_state.derniere_position = {"lat": 15.11, "lon": -16.65}

# Initialiser la base
if engine:
    init_base_donnees()

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent")
    
    prenom = st.text_input("Prénom / Turu", value=st.session_state.agent_prenom, placeholder="Ex: Awa")
    nom = st.text_input("Nom / Santa", value=st.session_state.agent_nom, placeholder="Ex: Ba")
    
    if prenom:
        st.session_state.agent_prenom = prenom
    if nom:
        st.session_state.agent_nom = nom
    
    if st.session_state.agent_nom and st.session_state.agent_prenom:
        st.success(f"✅ {st.session_state.agent_prenom} {st.session_state.agent_nom}")
    else:
        st.warning("⚠️ Entrez prénom et nom")
    
    st.markdown("---")
    st.markdown("### 🎤 Commandes (boutons)")
    st.info("""
    **Cliquez sur les boutons :**
    - 🚀 DEMM / DÉPART
    - 🗑️ COLLECTE 1 / TÀBB
    - 🚛 DÉCHARGE / TÒGG
    - 🏁 RETOUR / FANAN
    """)
    
    st.markdown("---")
    st.markdown("### 📊 Récapitulatif")
    if st.session_state.collecte1_validee:
        st.success("✅ Collecte 1 terminée")
    else:
        st.warning("⏳ Collecte 1 en attente")
    st.metric("📦 Volume 1", f"{st.session_state.volume1:.1f} m³")
    if st.session_state.collecte2_optionnelle:
        st.metric("📦 Volume 2", f"{st.session_state.volume2:.1f} m³")

# ==================== QUARTIER ET ÉQUIPE ====================
col1, col2 = st.columns(2)
with col1:
    quartiers = get_quartiers()
    quartier = st.selectbox("📍 Quartier", quartiers, format_func=lambda x: x[1])
    st.session_state.quartier_id = quartier[0]
with col2:
    equipes = get_equipes()
    equipe = st.selectbox("👥 Équipe", equipes, format_func=lambda x: x[1])
    st.session_state.equipe_id = equipe[0]

st.markdown("---")

# ==================== BOUTONS VOCAUX ====================
st.markdown("### 🎤 Cliquez sur ce que vous voulez dire")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("🚀 DEMM\nDÉPART", use_container_width=True, type="primary"):
        st.session_state.heure_depot_depart = datetime.now().strftime("%H:%M:%S")
        st.session_state.points.append({
            "type": "depart", "titre": "🏭 Départ dépôt",
            "lat": st.session_state.derniere_position["lat"],
            "lon": st.session_state.derniere_position["lon"],
            "heure": st.session_state.heure_depot_depart
        })
        st.success(f"✅ Départ à {st.session_state.heure_depot_depart}")
        st.balloons()

with col2:
    if st.button("🗑️ TÀBB\nCOLLECTE 1", use_container_width=True):
        st.session_state.heure_debut_collecte1 = datetime.now().strftime("%H:%M:%S")
        st.session_state.points.append({
            "type": "collecte1", "titre": "🗑️ Début collecte 1",
            "lat": st.session_state.derniere_position["lat"],
            "lon": st.session_state.derniere_position["lon"],
            "heure": st.session_state.heure_debut_collecte1
        })
        st.success(f"✅ Début collecte 1 à {st.session_state.heure_debut_collecte1}")

with col3:
    if st.button("🏁 FIN\nCOLLECTE 1", use_container_width=True):
        st.session_state.heure_fin_collecte1 = datetime.now().strftime("%H:%M:%S")
        st.success(f"✅ Fin collecte 1 à {st.session_state.heure_fin_collecte1}")

with col4:
    if st.button("🚛 TÒGG\nDÉCHARGE 1", use_container_width=True):
        st.session_state.heure_arrivee_decharge1 = datetime.now().strftime("%H:%M:%S")
        st.session_state.points.append({
            "type": "decharge1", "titre": "🚛 Arrivée décharge 1",
            "lat": st.session_state.derniere_position["lat"],
            "lon": st.session_state.derniere_position["lon"],
            "heure": st.session_state.heure_arrivee_decharge1
        })
        st.success(f"✅ Arrivée décharge 1 à {st.session_state.heure_arrivee_decharge1}")

with col5:
    if st.button("✅ SORTIE\nDÉCHARGE 1", use_container_width=True):
        st.session_state.heure_sortie_decharge1 = datetime.now().strftime("%H:%M:%S")
        st.success(f"✅ Sortie décharge 1 à {st.session_state.heure_sortie_decharge1}")

st.markdown("---")

# ==================== VOLUME COLLECTE 1 ====================
col1, col2 = st.columns([2, 1])
with col1:
    v1 = st.number_input("📦 Volume collecte 1 (m³)", 0.0, 50.0, st.session_state.volume1, 0.5)
    if v1 != st.session_state.volume1:
        st.session_state.volume1 = v1
with col2:
    if st.button("✅ VALIDER COLLECTE 1", type="primary", use_container_width=True):
        if st.session_state.volume1 > 0 and st.session_state.heure_depot_depart:
            st.session_state.collecte1_validee = True
            st.success("✅ Collecte 1 validée !")
            st.balloons()
        else:
            st.warning("⚠️ Entrez le volume et l'heure de départ")

# ==================== COLLECTE 2 (OPTIONNELLE) ====================
st.markdown("---")
st.markdown("""
<div class="collecte2-card">
    <h3>🚛 COLLECTE 2 (OPTIONNELLE)</h3>
    <p>Cliquez sur "ACTIVER" si vous faites une deuxième tournée</p>
</div>
""", unsafe_allow_html=True)

if st.session_state.collecte1_validee and not st.session_state.collecte2_validee:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ ACTIVER COLLECTE 2", use_container_width=True):
            st.session_state.collecte2_optionnelle = True
            st.success("✅ Collecte 2 activée")
    with col2:
        if st.button("⏭️ PASSER COLLECTE 2", use_container_width=True):
            st.session_state.collecte2_validee = True
            st.success("Collecte 2 ignorée")

if st.session_state.collecte2_optionnelle and not st.session_state.collecte2_validee:
    st.markdown("#### 🗑️ BOUTONS COLLECTE 2")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🗑️ DÉBUT\nCOLLECTE 2", use_container_width=True):
            st.session_state.heure_debut_collecte2 = datetime.now().strftime("%H:%M:%S")
            st.success(f"✅ Début collecte 2 à {st.session_state.heure_debut_collecte2}")
    
    with col2:
        if st.button("🏁 FIN\nCOLLECTE 2", use_container_width=True):
            st.session_state.heure_fin_collecte2 = datetime.now().strftime("%H:%M:%S")
            st.success(f"✅ Fin collecte 2 à {st.session_state.heure_fin_collecte2}")
    
    with col3:
        if st.button("🚛 DÉCHARGE 2", use_container_width=True):
            st.session_state.heure_arrivee_decharge2 = datetime.now().strftime("%H:%M:%S")
            st.success(f"✅ Arrivée décharge 2 à {st.session_state.heure_arrivee_decharge2}")
    
    with col4:
        if st.button("✅ SORTIE\nDÉCHARGE 2", use_container_width=True):
            st.session_state.heure_sortie_decharge2 = datetime.now().strftime("%H:%M:%S")
            st.success(f"✅ Sortie décharge 2 à {st.session_state.heure_sortie_decharge2}")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        v2 = st.number_input("📦 Volume collecte 2 (m³)", 0.0, 50.0, st.session_state.volume2, 0.5)
        if v2 != st.session_state.volume2:
            st.session_state.volume2 = v2
    with col2:
        if st.button("✅ VALIDER COLLECTE 2", type="primary", use_container_width=True):
            if st.session_state.volume2 > 0:
                st.session_state.collecte2_validee = True
                st.success("✅ Collecte 2 validée !")
                st.balloons()
            else:
                st.warning("⚠️ Entrez le volume")

# ==================== RETOUR DÉPÔT ====================
st.markdown("---")
st.markdown("### 🏁 RETOUR AU DÉPÔT")

if st.session_state.collecte1_validee:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🏁 FANAN / RETOUR", type="primary", use_container_width=True):
            st.session_state.heure_retour_depot = datetime.now().strftime("%H:%M:%S")
            st.session_state.points.append({
                "type": "retour", "titre": "🏁 Retour dépôt",
                "lat": st.session_state.derniere_position["lat"],
                "lon": st.session_state.derniere_position["lon"],
                "heure": st.session_state.heure_retour_depot
            })
            st.success(f"✅ Retour à {st.session_state.heure_retour_depot}")
            st.balloons()

# ==================== TABLEAU DES HEURES ====================
st.markdown("---")
st.markdown("### 📋 Récapitulatif des horaires")

horaires = [
    ("🏭 Départ dépôt", st.session_state.heure_depot_depart),
    ("🗑️ Début collecte 1", st.session_state.heure_debut_collecte1),
    ("🏁 Fin collecte 1", st.session_state.heure_fin_collecte1),
    ("🚛 Arrivée décharge 1", st.session_state.heure_arrivee_decharge1),
    ("✅ Sortie décharge 1", st.session_state.heure_sortie_decharge1),
]

if st.session_state.collecte2_optionnelle:
    horaires.extend([
        ("🗑️ Début collecte 2", st.session_state.heure_debut_collecte2),
        ("🏁 Fin collecte 2", st.session_state.heure_fin_collecte2),
        ("🚛 Arrivée décharge 2", st.session_state.heure_arrivee_decharge2),
        ("✅ Sortie décharge 2", st.session_state.heure_sortie_decharge2),
    ])

horaires.append(("🏁 Retour dépôt", st.session_state.heure_retour_depot))

df_horaires = pd.DataFrame(horaires, columns=["Étape", "Heure"])
st.dataframe(df_horaires, use_container_width=True)

# ==================== GOOGLE MAPS ====================
st.markdown("---")
st.markdown("### 📍 Position GPS")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("""
    <a href="https://www.google.com/maps/search/ma+position" target="_blank">
        <button style="background-color: #4285F4; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%;">
            🗺️ OUVRIR GOOGLE MAPS
        </button>
    </a>
    """, unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    gps_lat = st.text_input("Latitude", placeholder="15.121048")
with col2:
    gps_lon = st.text_input("Longitude", placeholder="-16.686826")

if st.button("📍 Enregistrer position", use_container_width=True):
    if gps_lat and gps_lon:
        try:
            lat = float(gps_lat)
            lon = float(gps_lon)
            st.session_state.derniere_position = {"lat": lat, "lon": lon}
            st.session_state.points.append({
                "type": "position", "titre": f"Position {st.session_state.agent_prenom}",
                "lat": lat, "lon": lon, "heure": datetime.now().strftime("%H:%M:%S")
            })
            st.success(f"✅ Position enregistrée")
        except:
            st.error("Format invalide")

# ==================== CARTE ====================
points_valides = [p for p in st.session_state.points if p.get("lat")]
if points_valides:
    st.markdown("### 🗺️ Carte des points")
    m = folium.Map(location=[points_valides[0]["lat"], points_valides[0]["lon"]], zoom_start=14)
    for p in points_valides:
        folium.Marker([p["lat"], p["lon"]], popup=f"{p['titre']}<br>{p.get('heure', '')}", icon=folium.Icon(color="blue")).add_to(m)
    folium_static(m, width=800, height=400)

# ==================== TERMINER ====================
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("✅ TERMINER LA TOURNÉE", type="primary", use_container_width=True):
        if st.session_state.collecte1_validee and st.session_state.heure_retour_depot:
            total_volume = st.session_state.volume1 + st.session_state.volume2
            nom_complet = f"{st.session_state.agent_prenom} {st.session_state.agent_nom}"
            
            st.balloons()
            st.success(f"""
            ✅ Tournée terminée !
            
            📊 Récapitulatif
            - Agent : {nom_complet}
            - Quartier : {quartier[1]}
            - Équipe : {equipe[1]}
            - Volume total : {total_volume} m³
            - Collecte 2 : {'Oui' if st.session_state.collecte2_optionnelle else 'Non'}
            """)
            
            if engine:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO tournees (date_tournee, quartier_id, equipe_id, agent_nom, 
                                                  volume_collecte1, volume_collecte2, statut,
                                                  heure_depot_depart, heure_retour_depot,
                                                  heure_debut_collecte1, heure_fin_collecte1,
                                                  heure_arrivee_decharge1, heure_sortie_decharge1)
                            VALUES (:date, :qid, :eid, :agent, :vol1, :vol2, 'termine',
                                    :h_depart, :h_retour, :h_debut1, :h_fin1, :h_arr_dech1, :h_sort_dech1)
                        """), {
                            "date": st.session_state.date_tournee,
                            "qid": st.session_state.quartier_id,
                            "eid": st.session_state.equipe_id,
                            "agent": nom_complet,
                            "vol1": st.session_state.volume1,
                            "vol2": st.session_state.volume2,
                            "h_depart": st.session_state.heure_depot_depart,
                            "h_retour": st.session_state.heure_retour_depot,
                            "h_debut1": st.session_state.heure_debut_collecte1,
                            "h_fin1": st.session_state.heure_fin_collecte1,
                            "h_arr_dech1": st.session_state.heure_arrivee_decharge1,
                            "h_sort_dech1": st.session_state.heure_sortie_decharge1
                        })
                        conn.commit()
                        st.success("✅ Enregistré dans la base Neon.tech !")
                except Exception as e:
                    st.warning(f"⚠️ Base: {e}")
        else:
            st.warning("⚠️ Validez collecte 1 et retour")

# ==================== CONSIGNES SÉCURITÉ ====================
with st.expander("🛡️ Consignes de sécurité / Làppu sécurité"):
    st.markdown("""
    1. **Baal sa bànqaas** - Pliez les jambes pour soulever
    2. **Jar gi ak noppal** - Portez gants et masque
    3. **Bul wàcc ci tracteur** - Ne montez pas sur le tracteur
    4. **Bul def ci diggante** - Éloignez-vous lors du vidage
    5. **Bul koom ci ndaw** - Ne restez pas au milieu de la route
    """)

st.markdown("---")
st.caption(f"👤 {st.session_state.agent_prenom} {st.session_state.agent_nom or 'Non connecté'} | 🗑️ Commune de Mékhé | 🎤 Boutons vocaux")
