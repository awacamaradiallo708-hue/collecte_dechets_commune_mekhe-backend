"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
VERSION COMPLÈTE AVEC :
- Saisie vocale en Wolof/Français
- Choix de toutes les équipes (A, B, C, D)
- Google Maps intégré
- Enregistrement des points vocaux
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
import speech_recognition as sr
import tempfile

load_dotenv()

st.set_page_config(
    page_title="Agent Collecte Vocal - Mékhé",
    page_icon="🎙️",
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
        st.warning(f"⚠️ Mode démo - Base non accessible: {e}")
        return None

engine = init_connection()

# ==================== DICTIONNAIRE VOCAL WOLOF/FRANÇAIS ====================
# VERSION CORRIGÉE - Plus de doublons, syntaxe correcte
COMMANDES_VOCALES = {
    # Départ
    "demm": "depart",
    "nangu": "depart",
    "je quitte": "depart",
    "depart": "depart",
    "partir": "depart",
    "magui ngéne dépot bi": "depart",
    
    # Collecte 1
    "collecte 1": "collecte1",
    "premiere collecte": "collecte1",
    "je commence à collecter": "collecte1",
    "tàbb": "collecte1",
    "tabbali na": "collecte1",
    
    # Collecte 2
    "collecte 2": "collecte2",
    "deuxieme collecte": "collecte2",
    
    # Volume
    "volume": "volume",
    "m3": "volume",
    "metre cube": "volume",
    "yendu": "volume",
    "wéttu": "volume",
    
    # Décharge
    "decharge": "decharge",
    "vidage": "decharge",
    "tògg": "decharge",
    "je vide": "decharge",
    "dechargement": "decharge",
    "sotti mbalite": "decharge",
    
    # Retour
    "retour": "retour",
    "je rentre": "retour",
    "fanan": "retour",
    "termine": "retour",
    "magui depe": "retour",
    "depe": "retour",
    
    # Fin
    "fin": "fin",
    "terminer": "fin",
    "c est fini": "fin",
    "bayyi": "fin",
    "parena": "fin",
    "diékhna": "fin",
    
    # Nombres
    "benn": 1,
    "ñaar": 2,
    "ñett": 3,
    "ñeent": 4,
    "juroom": 5,
    "juroom benn": 6,
    "juroom ñaar": 7,
    "juroom ñett": 8,
    "juroom ñeent": 9,
    "fukk": 10
}

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
    .vocal-card {
        background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 1rem 0;
    }
    .wolof-text {
        font-size: 22px;
        color: #4A148C;
        font-weight: bold;
        text-align: center;
    }
    .record-button {
        background-color: #ff4444 !important;
        color: white !important;
        font-size: 24px !important;
        padding: 20px !important;
    }
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🎙️ Agent de Collecte - Commune de Mékhé</h1>
    <p>Wax sa réew mi, nu tàbbal ! (Parlez en Wolof, on enregistre !)</p>
</div>
""", unsafe_allow_html=True)

# ==================== FONCTIONS ====================
def get_quartiers():
    return [(1, "HLM"), (2, "NDIOP"), (3, "LEBOU EST"), (4, "NGAYE DIAGNE"), (5, "MAMBARA"), (6, "NGAYE DJITTE"), (7, "LEBOU OUEST")]

def get_equipes():
    return [(1, "Équipe A"), (2, "Équipe B"), (3, "Équipe C"), (4, "Équipe D")]

def transcrire_audio(audio_bytes):
    """Transcrit l'audio en texte"""
    try:
        recognizer = sr.Recognizer()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="fr-FR")
        
        os.unlink(tmp_path)
        return text.lower()
    except:
        return None

def analyser_commande_vocale(texte):
    """Analyse la commande vocale (Wolof ou Français)"""
    if not texte:
        return None
    
    texte = texte.lower()
    resultat = {"type": None, "valeur": None}
    
    # Vérifier les commandes
    for mot, commande in COMMANDES_VOCALES.items():
        if mot in texte:
            if isinstance(commande, (int, float)):
                resultat["valeur"] = commande
            else:
                resultat["type"] = commande
            break
    
    # Extraction des nombres
    if not resultat["valeur"]:
        nombres = re.findall(r'\d+(?:[.,]\d+)?', texte)
        if nombres:
            resultat["valeur"] = float(nombres[0].replace(',', '.'))
    
    return resultat

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

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
if 'volume1' not in st.session_state:
    st.session_state.volume1 = 0.0
if 'volume2' not in st.session_state:
    st.session_state.volume2 = 0.0
if 'collecte1_faite' not in st.session_state:
    st.session_state.collecte1_faite = False
if 'collecte2_faite' not in st.session_state:
    st.session_state.collecte2_faite = False
if 'collecte2_option' not in st.session_state:
    st.session_state.collecte2_option = False
if 'points' not in st.session_state:
    st.session_state.points = []
if 'historique_vocal' not in st.session_state:
    st.session_state.historique_vocal = []
if 'heure_depart' not in st.session_state:
    st.session_state.heure_depart = ""
if 'heure_retour' not in st.session_state:
    st.session_state.heure_retour = ""
if 'derniere_position' not in st.session_state:
    st.session_state.derniere_position = {"lat": 15.11, "lon": -16.65}
if 'dernier_message_vocal' not in st.session_state:
    st.session_state.dernier_message_vocal = ""

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 L'agent / Ajentu")
    
    prenom = st.text_input("Prénom / Turu", value=st.session_state.agent_prenom, placeholder="Ex: Awa")
    nom = st.text_input("Nom / Santa", value=st.session_state.agent_nom, placeholder="Ex: Ba")
    
    if prenom:
        st.session_state.agent_prenom = prenom
    if nom:
        st.session_state.agent_nom = nom
    
    if st.session_state.agent_nom and st.session_state.agent_prenom:
        st.success(f"✅ {st.session_state.agent_prenom} {st.session_state.agent_nom}")
    
    st.markdown("---")
    st.markdown("### 🎙️ Commandes vocales / Wax yi")
    st.info("""
    **Wolof / Français :**
    - "Magui ngéne dépot bi" ou "Je quitte le dépôt"
    - "Collecte 1" ou "TABBALI NA"
    - "Volume  m3"
    - "Décharge" ou "SOTTI MBALITE"
    - "Retour" ou "magui depe"
    - "Fin" ou "paréna"
    """)

# ==================== SECTION PRINCIPALE ====================
# Choix du quartier et équipe
col1, col2 = st.columns(2)
with col1:
    quartiers = get_quartiers()
    quartier = st.selectbox("📍 Quartier", quartiers, format_func=lambda x: x[1])
    st.session_state.quartier_id = quartier[0]

with col2:
    equipes = get_equipes()
    equipe = st.selectbox("👥 Équipe / Équipe bi", equipes, format_func=lambda x: x[1])
    st.session_state.equipe_id = equipe[0]

st.markdown("---")

# ==================== SAISIE VOCALE PRINCIPALE ====================
st.markdown("""
<div class="vocal-card">
    <div class="wolof-text">🎤 Wax sa réew mi !</div>
    <p style="text-align: center;">Cliquez, parlez en Wolof ou Français, relâchez</p>
    <p style="text-align: center; font-size: 14px;">Exemples: "Demm", "Collecte 1", "Volume 5", "Décharge", "Retour"</p>
</div>
""", unsafe_allow_html=True)

# Bouton d'enregistrement vocal
audio = st.audio_input("🔴 Enregistrer", key="vocal_input")

if audio:
    with st.spinner("🔍 Nu ngi koy xam-xam..."):
        texte = transcrire_audio(audio.getvalue())
        if texte:
            st.session_state.dernier_message_vocal = texte
            st.success(f"📝 Nga wax : **{texte}**")
            
            commande = analyser_commande_vocale(texte)
            
            if commande and commande["type"]:
                # Traitement selon le type de commande
                if commande["type"] == "depart":
                    st.session_state.heure_depart = datetime.now().strftime("%H:%M:%S")
                    st.session_state.points.append({
                        "type": "depart", "titre": "🏭 Départ au dépôt / Demm ci dépôt",
                        "lat": st.session_state.derniere_position["lat"],
                        "lon": st.session_state.derniere_position["lon"],
                        "heure": st.session_state.heure_depart,
                        "message_vocal": texte
                    })
                    st.success(f"✅ Départ à {st.session_state.heure_depart}")
                    st.balloons()
                
                elif commande["type"] == "collecte1":
                    st.session_state.collecte1_faite = True
                    st.session_state.points.append({
                        "type": "collecte1", "titre": "🗑️ Début collecte 1 / TABBALI NA",
                        "lat": st.session_state.derniere_position["lat"],
                        "lon": st.session_state.derniere_position["lon"],
                        "heure": datetime.now().strftime("%H:%M:%S"),
                        "message_vocal": texte
                    })
                    st.success("✅ Collecte 1 démarrée !")
                
                elif commande["type"] == "collecte2":
                    st.session_state.collecte2_option = True
                    st.session_state.points.append({
                        "type": "collecte2", "titre": "🗑️ Collecte 2",
                        "lat": st.session_state.derniere_position["lat"],
                        "lon": st.session_state.derniere_position["lon"],
                        "heure": datetime.now().strftime("%H:%M:%S"),
                        "message_vocal": texte
                    })
                    st.success("✅ Collecte 2 activée !")
                
                elif commande["type"] == "volume" and commande["valeur"]:
                    if not st.session_state.collecte2_option:
                        st.session_state.volume1 = commande["valeur"]
                        st.success(f"✅ Volume collecte 1 : {commande['valeur']} m³")
                    else:
                        st.session_state.volume2 = commande["valeur"]
                        st.success(f"✅ Volume collecte 2 : {commande['valeur']} m³")
                
                elif commande["type"] == "decharge":
                    st.session_state.points.append({
                        "type": "decharge", "titre": "🚛 Vidage décharge / SOTTI MBALITE",
                        "lat": st.session_state.derniere_position["lat"],
                        "lon": st.session_state.derniere_position["lon"],
                        "heure": datetime.now().strftime("%H:%M:%S"),
                        "message_vocal": texte
                    })
                    st.success("✅ Vidage décharge enregistré !")
                
                elif commande["type"] == "retour":
                    st.session_state.heure_retour = datetime.now().strftime("%H:%M:%S")
                    st.session_state.points.append({
                        "type": "retour", "titre": "🏁 Retour dépôt / Depe",
                        "lat": st.session_state.derniere_position["lat"],
                        "lon": st.session_state.derniere_position["lon"],
                        "heure": st.session_state.heure_retour,
                        "message_vocal": texte
                    })
                    st.success(f"✅ Retour à {st.session_state.heure_retour}")
                
                elif commande["type"] == "fin":
                    st.success("✅ Tournée terminée !")
                
                # Historique
                st.session_state.historique_vocal.append({
                    "heure": datetime.now().strftime("%H:%M:%S"),
                    "commande": texte,
                    "action": commande["type"]
                })
                st.rerun()
            else:
                st.warning("⚠️ Commande non reconnue. Dites : Demm, Collecte 1, Volume 5, Décharge, ou Retour")
        else:
            st.error("❌ Nu nangu koo wax ! Jëflante (Non reconnu, réessayez)")

# Afficher le dernier message vocal
if st.session_state.dernier_message_vocal:
    st.info(f"🎤 Dernier message : **{st.session_state.dernier_message_vocal}**")

st.markdown("---")

# ==================== SAISIE MANUELLE SIMPLIFIÉE ====================
with st.expander("🖊️ Saisie manuelle (Si le vocal ne marche pas)"):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🚀 DÉPART / Mangi départ", use_container_width=True):
            st.session_state.heure_depart = datetime.now().strftime("%H:%M:%S")
            st.success(f"Départ à {st.session_state.heure_depart}")
    with col2:
        if st.button("🗑️ COLLECTE 1 / TABBALI NA", use_container_width=True):
            st.session_state.collecte1_faite = True
            st.success("Collecte 1 démarrée")
    with col3:
        if st.button("🚛 DÉCHARGE / SOTTI MBALITE", use_container_width=True):
            st.success("Vidage décharge")
    with col4:
        if st.button("🏁 RETOUR / DEPE", use_container_width=True):
            st.session_state.heure_retour = datetime.now().strftime("%H:%M:%S")
            st.success(f"Retour à {st.session_state.heure_retour}")

# ==================== VOLUMES ====================
col1, col2 = st.columns(2)
with col1:
    v1 = st.number_input("📦 Volume collecte 1 (m³)", 0.0, 50.0, st.session_state.volume1, 0.5)
    if v1 != st.session_state.volume1:
        st.session_state.volume1 = v1
with col2:
    if st.session_state.collecte1_faite:
        v2 = st.number_input("📦 Volume collecte 2 (m³)", 0.0, 50.0, st.session_state.volume2, 0.5)
        if v2 != st.session_state.volume2:
            st.session_state.volume2 = v2
            if v2 > 0:
                st.session_state.collecte2_option = True

# ==================== GOOGLE MAPS GPS ====================
st.markdown("---")
st.markdown("### 📍 Position GPS avec Google Maps")

st.markdown("""
<div style="background-color: #e3f2fd; padding: 1rem; border-radius: 10px; margin: 1rem 0;">
    <p>📍 <strong>Comment avoir votre position :</strong></p>
    <ol>
        <li>Cliquez sur le bouton ci-dessous</li>
        <li>Google Maps s'ouvre et montre votre position</li>
        <li>Copiez les coordonnées (latitude, longitude)</li>
        <li>Collez-les dans les champs</li>
    </ol>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("""
    <a href="https://www.google.com/maps/search/ma+position" target="_blank">
        <button style="background-color: #4285F4; color: white; padding: 12px 24px; border: none; border-radius: 8px; font-size: 18px; width: 100%;">
            🗺️ OUVRIR GOOGLE MAPS - MA POSITION
        </button>
    </a>
    """, unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    gps_lat = st.text_input("Latitude", placeholder="Ex: 15.121048")
with col2:
    gps_lon = st.text_input("Longitude", placeholder="Ex: -16.686826")

if st.button("📍 ENREGISTRER MA POSITION", use_container_width=True):
    if gps_lat and gps_lon:
        try:
            lat = float(gps_lat)
            lon = float(gps_lon)
            st.session_state.derniere_position = {"lat": lat, "lon": lon}
            st.session_state.points.append({
                "type": "position", "titre": f"📍 Position de {st.session_state.agent_prenom}",
                "lat": lat, "lon": lon,
                "heure": datetime.now().strftime("%H:%M:%S")
            })
            st.success(f"✅ Position enregistrée : {lat}, {lon}")
        except:
            st.error("Format invalide")

# ==================== CARTE ====================
st.markdown("---")
st.markdown("### 🗺️ Carte des points")

points_valides = [p for p in st.session_state.points if p.get("lat") is not None and p.get("lon") is not None]

if points_valides:
    m = folium.Map(location=[points_valides[0]["lat"], points_valides[0]["lon"]], zoom_start=14)
    
    couleurs = {"depart": "green", "collecte1": "blue", "collecte2": "purple", "decharge": "red", "retour": "brown", "position": "orange"}
    
    for p in points_valides:
        color = couleurs.get(p.get("type", "position"), "gray")
        folium.Marker(
            [p["lat"], p["lon"]],
            popup=f"<b>{p['titre']}</b><br>Heure: {p.get('heure', '')}",
            icon=folium.Icon(color=color)
        ).add_to(m)
    
    if len(points_valides) > 1:
        coords = [[p["lat"], p["lon"]] for p in points_valides]
        folium.PolyLine(coords, color="blue", weight=3).add_to(m)
    
    folium_static(m, width=800, height=500)
else:
    st.info("📍 Aucun point GPS. Enregistrez votre position avec Google Maps")

# ==================== TERMINER ====================
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("✅ TERMINER LA TOURNÉE", type="primary", use_container_width=True):
        if st.session_state.collecte1_faite:
            total_volume = st.session_state.volume1 + st.session_state.volume2
            nom_complet = f"{st.session_state.agent_prenom} {st.session_state.agent_nom}"
            
            st.balloons()
            st.success(f"""
            ✅ Tournée terminée avec succès !
            
            📊 **Récapitulatif / Xam-xamu jéeréem**
            - Agent : {nom_complet}
            - Quartier : {quartier[1]}
            - Équipe : {equipe[1]}
            - Volume total : {total_volume} m³
            - Points GPS : {len(points_valides)}
            - Commandes vocales : {len(st.session_state.historique_vocal)}
            
            **Jërëjëf !** 🙏
            """)
            
            # Enregistrement dans la base
            if engine:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO tournees (date_tournee, quartier_id, equipe_id, agent_nom, 
                                                  volume_collecte1, volume_collecte2, statut)
                            VALUES (:date, :qid, :eid, :agent, :vol1, :vol2, 'termine')
                        """), {
                            "date": st.session_state.date_tournee,
                            "qid": st.session_state.quartier_id,
                            "eid": st.session_state.equipe_id,
                            "agent": nom_complet,
                            "vol1": st.session_state.volume1,
                            "vol2": st.session_state.volume2
                        })
                        conn.commit()
                        st.success("✅ Données enregistrées dans la base Neon.tech !")
                except Exception as e:
                    st.warning(f"⚠️ Base: {e}")
        else:
            st.warning("⚠️ Veuillez faire la collecte 1 d'abord")

# ==================== HISTORIQUE VOCAL ====================
if st.session_state.historique_vocal:
    with st.expander("📜 Historique des commandes vocales"):
        for h in st.session_state.historique_vocal[-10:]:
            st.write(f"🕐 {h['heure']} - {h['commande']}")

# ==================== CONSIGNES SÉCURITÉ ====================
with st.expander("🛡️ Consignes de sécurité / Làppu sécurité"):
    st.markdown("""
    ### ⚠️ RAPPEL QUOTIDIEN / LÀPPU BU BÉS BI
    
    1. **Gestes et postures** / Baal sa bànqaas - Pliez les jambes
    2. **Protection** / Jar gi ak noppal - Gants et masque
    3. **Ne montez pas sur le tracteur** / Bul wàcc ci tracteur bu ngi faj
    4. **Éloignez-vous lors du vidage** / Bul def ci diggante bu yendu remorque
    5. **Circulation** / Bul koom ci ndaw - Ne restez pas au milieu
    """)

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"👤 {st.session_state.agent_prenom} {st.session_state.agent_nom or 'Non connecté'} | 🗑️ Commune de Mékhé | 🎙️ Vocal Wolof/Français | 📍 Google Maps")
