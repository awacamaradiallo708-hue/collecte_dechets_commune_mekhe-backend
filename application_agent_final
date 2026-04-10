"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
VERSION WOLOF + VOCAL + FOLIUM
Dépendances : streamlit, pandas, plotly, sqlalchemy, psycopg2-binary, 
              python-dotenv, openpyxl, folium, streamlit-folium
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
import folium
from streamlit_folium import folium_static
from dotenv import load_dotenv
import json

# Chargement des variables d'environnement
load_dotenv()

st.set_page_config(
    page_title="Agent Collecte - Mékhé (Wolof)",
    page_icon="🎙️",
    layout="wide"
)

# ==================== CONNEXION BASE NEON.TECH ====================
# Ta base Neon.tech
DATABASE_URL = "postgresql://neondb_owner:npg_43LqPNrhlzWo@ep-misty-mode-al5c7s4f-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

@st.cache_resource
def init_connection():
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        st.success("✅ Base de données connectée !")
        return engine
    except Exception as e:
        st.warning(f"⚠️ Mode démo - Base non accessible: {e}")
        return None

engine = init_connection()

# ==================== DICTIONNAIRE WOLOF ====================
COMMANDES_WOLOF = {
    "demm": "depart", "nangu": "depart", "demm ci dépôt": "depart",
    "fanan": "retour", "retour": "retour", "rentrer": "retour",
    "volume": "volume", "metere kuubik": "volume", "m3": "volume", "yendu": "volume",
    "tàbb": "collecte", "collecte": "collecte", "bayyi": "fin",
    "fin collecte": "fin", "terminer": "fin",
    "décharge": "decharge", "vidage": "decharge", "tògg": "decharge",
    "point": "gps", "gps": "gps", "fànne": "gps", "coord": "gps",
    "équipe": "equipe", "quartier": "quartier",
    "benn": 1, "ñaar": 2, "ñett": 3, "ñeent": 4, "juroom": 5,
    "juroom-benn": 6, "juroom-ñaar": 7, "juroom-ñett": 8, "juroom-ñeent": 9, "fukk": 10
}

TEXTE = {
    "title": "🎙️ Agent Collecte - Mbootaayu Mékhé",
    "subtitle": "Wax sa réew mi, nu tàbbal ! (Parlez, on enregistre !)",
    "connecte": "✅ Connecté :",
    "votre_nom": "✍️ Votre nom / Turu jàppaleekat",
    "depart": "🔊 'Demm' ou 'Nangu' - Démarrer",
    "volume_ex": "🔊 'Volume 5' ou '5 m3'",
    "fin": "🔊 'Fin collecte' ou 'Bayyi'",
    "decharge_ex": "🔊 'Décharge' ou 'Tògg'",
    "retour_ex": "🔊 'Retour' ou 'Fanan'",
    "gps_ex": "🔊 'Point 15.12, -16.68'",
    "recap": "📊 Récapitulatif / Xam-xamu jéeréem",
    "collecte1_terminee": "✅ Collecte 1 terminée / Tàbb bi",
    "collecte1_attente": "⏳ Collecte 1 en attente / Làngeen nañu",
    "volume": "📦 Volume / Wéttu",
    "distance": "📏 Distance / Diggante",
    "points": "📍 Points enregistrés / Fànne yi wépp",
    "carte": "🗺️ Carte / Kartu diggante",
    "terminer": "✅ Terminer la tournée / Wax sa jéeréem",
    "securite": "🛡️ Consignes de sécurité / Làppu sécurité"
}

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
    .vocal-card {
        background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 1rem 0;
    }
    .wolof-text {
        font-size: 20px;
        color: #4A148C;
        font-weight: bold;
    }
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="main-header">
    <h1>{TEXTE['title']}</h1>
    <p>{TEXTE['subtitle']}</p>
</div>
""", unsafe_allow_html=True)

# ==================== FONCTIONS ====================
def get_quartiers():
    if not engine:
        return [(1, "Mékhé Centre"), (2, "Mékhé Nord"), (3, "Mékhé Sud"), (4, "Mékhé Est"), (5, "Mékhé Ouest")]
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, nom FROM quartiers WHERE actif = true ORDER BY nom")).fetchall()
            if result:
                return [(r[0], r[1]) for r in result]
    except:
        pass
    return [(1, "Mékhé Centre"), (2, "Mékhé Nord"), (3, "Mékhé Sud")]

def get_equipes():
    if not engine:
        return [(1, "Équipe A"), (2, "Équipe B"), (3, "Équipe C")]
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, nom FROM equipes WHERE actif = true ORDER BY nom")).fetchall()
            if result:
                return [(r[0], r[1]) for r in result]
    except:
        pass
    return [(1, "Équipe A"), (2, "Équipe B")]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def create_folium_map(points):
    """Crée une carte Folium avec les points"""
    if not points:
        return None
    
    # Centre sur le premier point ou Mékhé
    center_lat = points[0].get("lat", 15.11)
    center_lon = points[0].get("lon", -16.65)
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    # Couleurs par type
    colors = {
        "depart_depot": "green",
        "debut_collecte": "blue",
        "fin_collecte": "blue",
        "decharge": "red",
        "point_libre": "purple",
        "retour_depot": "brown"
    }
    
    # Ajout des points
    for i, point in enumerate(points):
        if point.get("lat") and point.get("lon"):
            color = colors.get(point.get("type", "point_libre"), "gray")
            folium.Marker(
                [point["lat"], point["lon"]],
                popup=f"{point.get('titre', 'Point')}<br>Heure: {point.get('heure', '')}",
                icon=folium.Icon(color=color, icon="info-sign")
            ).add_to(m)
    
    # Tracer la ligne du trajet
    coords = [[p["lat"], p["lon"]] for p in points if p.get("lat") and p.get("lon")]
    if len(coords) > 1:
        folium.PolyLine(coords, color="blue", weight=3, opacity=0.7).add_to(m)
    
    return m

# ==================== SESSION STATE ====================
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'date_tournee' not in st.session_state:
    st.session_state.date_tournee = date.today()
if 'quartier_nom' not in st.session_state:
    st.session_state.quartier_nom = ""
if 'equipe_nom' not in st.session_state:
    st.session_state.equipe_nom = ""
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
if 'points' not in st.session_state:
    st.session_state.points = []
if 'historique_vocal' not in st.session_state:
    st.session_state.historique_vocal = []
if 'heure_depart' not in st.session_state:
    st.session_state.heure_depart = datetime.now().strftime("%H:%M")
if 'heure_retour' not in st.session_state:
    st.session_state.heure_retour = ""

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent")
    
    agent_nom = st.text_input(TEXTE["votre_nom"], value=st.session_state.agent_nom)
    if agent_nom:
        st.session_state.agent_nom = agent_nom
        st.success(f"{TEXTE['connecte']} {agent_nom}")
    
    st.markdown("---")
    st.markdown("### 🎙️ Commandes vocales")
    st.info(f"""
    {TEXTE['depart']}
    {TEXTE['volume_ex']}
    {TEXTE['fin']}
    {TEXTE['decharge_ex']}
    {TEXTE['retour_ex']}
    {TEXTE['gps_ex']}
    """)
    
    st.markdown("---")
    st.markdown(f"### {TEXTE['recap']}")
    
    if st.session_state.collecte1_validee:
        st.success(TEXTE["collecte1_terminee"])
    else:
        st.warning(TEXTE["collecte1_attente"])
    
    st.metric(f"{TEXTE['volume']} 1", f"{st.session_state.volume1:.1f} m³")
    if st.session_state.collecte2_optionnelle:
        st.metric(f"{TEXTE['volume']} 2", f"{st.session_state.volume2:.1f} m³")

# ==================== SECTION PRINCIPALE ====================
# Date et quartier
col1, col2 = st.columns(2)
with col1:
    st.session_state.date_tournee = st.date_input("📅 Date", st.session_state.date_tournee)
with col2:
    quartiers = get_quartiers()
    quartier = st.selectbox("📍 Quartier", [q[1] for q in quartiers])
    st.session_state.quartier_nom = quartier

# Bouton départ
if st.button("🚀 DÉMARRER / DEMN", type="primary", use_container_width=True):
    st.session_state.heure_depart = datetime.now().strftime("%H:%M")
    st.session_state.points.append({
        "type": "depart_depot", "titre": "🏭 Départ dépôt",
        "lat": None, "lon": None, "heure": st.session_state.heure_depart
    })
    st.success(f"Départ à {st.session_state.heure_depart}")

st.markdown("---")

# ==================== SAISIE VOCALE ====================
st.markdown("""
<div class="vocal-card">
    <div style="font-size: 50px;">🎤</div>
    <div class="wolof-text">Wax sa réew mi !</div>
    <p>Cliquez, parlez, relâchez</p>
</div>
""", unsafe_allow_html=True)

audio = st.audio_input("🎙️ Enregistrer", key="vocal")

if audio:
    st.info("🔍 Traitement en cours...")
    # Simuler la reconnaissance (à remplacer par votre API)
    st.success("📝 Commande reconnue !")
    
    # Interface simple pour la démo
    commande = st.selectbox("Qu'avez-vous dit ?", [
        "Demm (Départ)", "Volume 5 m3", "Fin collecte", "Tògg (Décharge)", 
        "Fanan (Retour)", "Point GPS"
    ])
    
    if commande == "Demm (Départ)":
        st.session_state.heure_depart = datetime.now().strftime("%H:%M")
        st.success(f"✅ Départ à {st.session_state.heure_depart}")
    elif commande == "Volume 5 m3":
        if not st.session_state.collecte1_validee:
            st.session_state.volume1 = 5
            st.success("✅ Volume collecte 1 : 5 m³")
        else:
            st.session_state.volume2 = 5
            st.session_state.collecte2_optionnelle = True
            st.success("✅ Volume collecte 2 : 5 m³")
    elif commande == "Fin collecte":
        st.session_state.collecte1_validee = True
        st.success("✅ Collecte 1 terminée / Tàbb bi dem na !")
    elif commande == "Tògg (Décharge)":
        st.success("✅ Vidage décharge enregistré")
    elif commande == "Fanan (Retour)":
        st.session_state.heure_retour = datetime.now().strftime("%H:%M")
        st.success(f"✅ Retour à {st.session_state.heure_retour}")
    elif commande == "Point GPS":
        lat = st.text_input("Latitude", "15.12")
        lon = st.text_input("Longitude", "-16.68")
        if st.button("Ajouter"):
            st.session_state.points.append({
                "type": "point_libre", "titre": "📍 Point",
                "lat": float(lat), "lon": float(lon),
                "heure": datetime.now().strftime("%H:%M")
            })
            st.success("✅ Point ajouté !")

# ==================== VOLUMES ====================
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    v1 = st.number_input(f"{TEXTE['volume']} 1 (m³)", 0.0, 50.0, st.session_state.volume1, 0.5)
    if v1 != st.session_state.volume1:
        st.session_state.volume1 = v1
with col2:
    if st.session_state.collecte1_validee:
        v2 = st.number_input(f"{TEXTE['volume']} 2 (m³)", 0.0, 50.0, st.session_state.volume2, 0.5)
        if v2 != st.session_state.volume2:
            st.session_state.volume2 = v2
            if v2 > 0:
                st.session_state.collecte2_optionnelle = True

# ==================== CARTE FOLIUM ====================
if st.session_state.points:
    st.markdown(f"### {TEXTE['carte']}")
    folium_map = create_folium_map(st.session_state.points)
    if folium_map:
        folium_static(folium_map, width=800, height=500)

# ==================== POINTS ENREGISTRÉS ====================
with st.expander(f"📍 {TEXTE['points']}"):
    if st.session_state.points:
        df = pd.DataFrame(st.session_state.points)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aucun point pour l'instant")

# ==================== TERMINER ====================
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button(f"✅ {TEXTE['terminer']}", type="primary", use_container_width=True):
        if st.session_state.volume1 > 0:
            total_volume = st.session_state.volume1 + st.session_state.volume2
            st.balloons()
            st.success(f"""
            ✅ Tournée terminée avec succès !
            
            📊 **Récapitulatif / Xam-xamu jéeréem**
            - Volume total : {total_volume} m³
            - Points enregistrés : {len(st.session_state.points)}
            - Quartier : {st.session_state.quartier_nom}
            - Agent : {st.session_state.agent_nom}
            
            **Jërëjëf !** 🙏
            """)
            
            # Enregistrement dans la base
            if engine:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO tournees (date_tournee, quartier_id, agent_nom, volume_m3, statut)
                            VALUES (:date, 1, :agent, :vol, 'termine')
                        """), {
                            "date": st.session_state.date_tournee,
                            "agent": st.session_state.agent_nom,
                            "vol": total_volume
                        })
                        conn.commit()
                        st.success("✅ Données enregistrées dans la base Neon.tech !")
                except Exception as e:
                    st.warning(f"⚠️ Base: {e}")
        else:
            st.warning("⚠️ Veuillez entrer un volume avant de terminer")

# ==================== SÉCURITÉ ====================
with st.expander(f"🛡️ {TEXTE['securite']}"):
    st.markdown("""
    ### ⚠️ RAPPEL QUOTIDIEN / LÀPPU BU BÉS BI
    
    1. **Gestes et postures** - Pliez les jambes, pas le dos / Baal sa bànqaas
    2. **Protection** - Portez gants et masque / Jar gi ak noppal
    3. **Ne montez pas sur le tracteur en marche** / Bul wàcc ci tracteur bu ngi faj
    4. **Éloignez-vous lors du vidage** / Bul def ci diggante bu yendu remorque
    5. **Circulation** - Ne restez pas au milieu de la route
    
    🔔 **En cas de problème, contactez votre responsable !**
    """)

# ==================== EXPORT EXCEL ====================
if st.session_state.points:
    with st.expander("📊 Exporter les données"):
        df_export = pd.DataFrame(st.session_state.points)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, sheet_name="Collecte", index=False)
            pd.DataFrame([{
                "Agent": st.session_state.agent_nom,
                "Date": st.session_state.date_tournee,
                "Quartier": st.session_state.quartier_nom,
                "Volume total": st.session_state.volume1 + st.session_state.volume2
            }]).to_excel(writer, sheet_name="Récap", index=False)
        
        st.download_button(
            "📥 Télécharger Excel",
            output.getvalue(),
            f"collecte_{st.session_state.agent_nom}_{st.session_state.date_tournee}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"👤 {st.session_state.agent_nom or 'Non connecté'} | 🗑️ Commune de Mékhé | 🎙️ Wolof - Jërëjëf")
