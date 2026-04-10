"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
VERSION COMPLÈTE avec Google Maps et nom agent
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
import requests

load_dotenv()

st.set_page_config(
    page_title="Agent Collecte - Mékhé",
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
        st.warning(f"⚠️ Mode démo - Base non accessible")
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
    .agent-card {
        background: #e8f5e9;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .gps-card {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #2196F3;
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
    <h1>🗑️ Agent de Collecte - Commune de Mékhé</h1>
    <p>Saisie des collectes | Points GPS | Carte interactive</p>
</div>
""", unsafe_allow_html=True)

# ==================== FONCTIONS ====================
def get_quartiers():
    if not engine:
        return [(1, "HLM"), (2, "NDIOP"), (3, "LEBOU EST"), (4, "NGAYE DIAGNE"), (5, "MAMBARA"), (6, "NGAYE DJITTE"), ("LEBOU OUEST")]
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, nom FROM quartiers WHERE actif = true ORDER BY nom")).fetchall()
            return [(r[0], r[1]) for r in result] if result else [(1, "HLM")]
    except:
        return [(1, "HLM"), (2, "NDIOP"), (3, "LEBOU EST"), (4, "NGAYE DIAGNE"), (5, "MAMBARA"), (6, "NGAYE DJITTE"), ("LEBOU OUEST")]

def get_equipes():
    if not engine:
        return [(1, "Équipe A"), (2, "Équipe B")]
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, nom FROM equipes WHERE actif = true ORDER BY nom")).fetchall()
            return [(r[0], r[1]) for r in result] if result else [(1, "Équipe A")]
    except:
        return [(1, "Équipe A"), (2, "Équipe B")]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def get_current_location():
    """Récupère la position GPS via l'API du navigateur"""
    # Cette fonction sera appelée par le JS
    return None

# ==================== SESSION STATE ====================
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'agent_prenom' not in st.session_state:
    st.session_state.agent_prenom = ""
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
    st.session_state.heure_depart = ""
if 'heure_retour' not in st.session_state:
    st.session_state.heure_retour = ""
if 'derniere_position' not in st.session_state:
    st.session_state.derniere_position = {"lat": 15.11, "lon": -16.65}

# ==================== SECTION AGENT (NOM OBLIGATOIRE) ====================
st.markdown("### 👤 Identification de l'agent")

col1, col2 = st.columns(2)
with col1:
    prenom = st.text_input("📝 Prénom", value=st.session_state.agent_prenom, placeholder="Ex: Alioune")
    if prenom:
        st.session_state.agent_prenom = prenom
with col2:
    nom = st.text_input("📝 Nom", value=st.session_state.agent_nom, placeholder="Ex: Diop")
    if nom:
        st.session_state.agent_nom = nom

if st.session_state.agent_nom and st.session_state.agent_prenom:
    nom_complet = f"{st.session_state.agent_prenom} {st.session_state.agent_nom}"
    st.success(f"✅ Agent connecté : {nom_complet}")
else:
    st.warning("⚠️ Veuillez entrer votre prénom et nom pour continuer")

st.markdown("---")

# ==================== SECTION GOOGLE MAPS POUR GPS ====================
st.markdown("### 📍 Localisation GPS - Google Maps")

st.markdown("""
<div class="gps-card">
    <p>📌 <strong>Comment obtenir vos coordonnées GPS :</strong></p>
    <ol>
        <li>Cliquez sur le lien ci-dessous pour ouvrir Google Maps</li>
        <li>Google Maps vous montrera votre position actuelle</li>
        <li>Copiez les coordonnées (latitude, longitude)</li>
        <li>Collez-les dans le champ ci-dessous</li>
    </ol>
</div>
""", unsafe_allow_html=True)

# Lien direct vers Google Maps pour obtenir la position
st.markdown("""
<div style="text-align: center; margin: 10px 0;">
    <a href="https://www.google.com/maps/search/ma+position" target="_blank">
        <button style="background-color: #4285F4; color: white; padding: 12px 24px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer;">
            🗺️ OUVRIRE GOOGLE MAPS - MA POSITION
        </button>
    </a>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    gps_lat = st.text_input("🌐 Latitude", placeholder="Ex: 15.121048", value=str(st.session_state.derniere_position["lat"]) if st.session_state.derniere_position else "")
with col2:
    gps_lon = st.text_input("🌐 Longitude", placeholder="Ex: -16.686826", value=str(st.session_state.derniere_position["lon"]) if st.session_state.derniere_position else "")

# Bouton pour enregistrer la position
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("📍 ENREGISTRER MA POSITION", use_container_width=True):
        if gps_lat and gps_lon:
            try:
                lat = float(gps_lat)
                lon = float(gps_lon)
                st.session_state.derniere_position = {"lat": lat, "lon": lon}
                st.session_state.points.append({
                    "type": "point_agent",
                    "titre": f"📍 Position de {st.session_state.agent_prenom}",
                    "lat": lat,
                    "lon": lon,
                    "heure": datetime.now().strftime("%H:%M:%S"),
                    "description": f"Position de l'agent {st.session_state.agent_prenom} {st.session_state.agent_nom}"
                })
                st.success(f"✅ Position enregistrée : {lat}, {lon}")
                st.balloons()
            except ValueError:
                st.error("❌ Format invalide. Utilisez des nombres avec des points (ex: 15.121048)")
        else:
            st.warning("⚠️ Veuillez entrer la latitude et la longitude")

st.markdown("---")

# ==================== SECTION PRINCIPALE ====================
col1, col2 = st.columns(2)
with col1:
    st.session_state.date_tournee = st.date_input("📅 Date de la tournée", st.session_state.date_tournee)
with col2:
    quartiers = get_quartiers()
    quartier = st.selectbox("📍 Quartier", [q[1] for q in quartiers])
    st.session_state.quartier_nom = quartier

col1, col2 = st.columns(2)
with col1:
    equipes = get_equipes()
    equipe = st.selectbox("👥 Équipe", [e[1] for e in equipes])
    st.session_state.equipe_nom = equipe
with col2:
    if st.button("🚀 DÉMARRER LA TOURNÉE", type="primary", use_container_width=True):
        if st.session_state.agent_nom and st.session_state.agent_prenom:
            st.session_state.heure_depart = datetime.now().strftime("%H:%M:%S")
            st.session_state.points.append({
                "type": "depart",
                "titre": "🏭 Départ du dépôt",
                "lat": st.session_state.derniere_position["lat"] if st.session_state.derniere_position else None,
                "lon": st.session_state.derniere_position["lon"] if st.session_state.derniere_position else None,
                "heure": st.session_state.heure_depart
            })
            st.success(f"✅ Tournée démarrée à {st.session_state.heure_depart}")
        else:
            st.warning("⚠️ Veuillez entrer votre nom d'abord")

# ==================== SAISIE DES VOLUMES ====================
st.markdown("---")
st.markdown("### 📦 Volumes collectés")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**🗑️ Collecte 1**")
    v1 = st.number_input("Volume (m³)", 0.0, 50.0, st.session_state.volume1, 0.5)
    if v1 != st.session_state.volume1:
        st.session_state.volume1 = v1
    if st.button("✅ VALIDER COLLECTE 1", use_container_width=True):
        if st.session_state.volume1 > 0:
            st.session_state.collecte1_validee = True
            st.session_state.points.append({
                "type": "fin_collecte1",
                "titre": "🗑️ Fin collecte 1",
                "lat": st.session_state.derniere_position["lat"] if st.session_state.derniere_position else None,
                "lon": st.session_state.derniere_position["lon"] if st.session_state.derniere_position else None,
                "heure": datetime.now().strftime("%H:%M:%S"),
                "volume": st.session_state.volume1
            })
            st.success(f"✅ Collecte 1 validée - {st.session_state.volume1} m³")
        else:
            st.warning("⚠️ Entrez un volume > 0")

with col2:
    if st.session_state.collecte1_validee:
        st.markdown("**🗑️ Collecte 2 (optionnelle)**")
        v2 = st.number_input("Volume (m³)", 0.0, 50.0, st.session_state.volume2, 0.5)
        if v2 != st.session_state.volume2:
            st.session_state.volume2 = v2
            if v2 > 0:
                st.session_state.collecte2_optionnelle = True
        if st.session_state.collecte2_optionnelle and st.button("✅ VALIDER COLLECTE 2", use_container_width=True):
            if st.session_state.volume2 > 0:
                st.session_state.collecte2_validee = True
                st.session_state.points.append({
                    "type": "fin_collecte2",
                    "titre": "🗑️ Fin collecte 2",
                    "lat": st.session_state.derniere_position["lat"] if st.session_state.derniere_position else None,
                    "lon": st.session_state.derniere_position["lon"] if st.session_state.derniere_position else None,
                    "heure": datetime.now().strftime("%H:%M:%S"),
                    "volume": st.session_state.volume2
                })
                st.success(f"✅ Collecte 2 validée - {st.session_state.volume2} m³")

# ==================== POINTS SUPPLÉMENTAIRES ====================
st.markdown("---")
st.markdown("### 📌 Ajouter un point (dépôt sauvage, incident, etc.)")

with st.expander("➕ Ajouter un point manuellement"):
    col1, col2 = st.columns(2)
    with col1:
        point_lat = st.text_input("Latitude", placeholder="Ex: 15.121048")
        point_lon = st.text_input("Longitude", placeholder="Ex: -16.686826")
    with col2:
        point_desc = st.text_input("Description", placeholder="Ex: Dépôt sauvage, Encombrant, etc.")
        point_type = st.selectbox("Type de point", ["Dépôt sauvage", "Incident", "Point de contrôle", "Autre"])
    
    if st.button("📌 AJOUTER CE POINT", use_container_width=True):
        if point_lat and point_lon:
            try:
                lat = float(point_lat)
                lon = float(point_lon)
                st.session_state.points.append({
                    "type": "point_manuel",
                    "titre": f"📍 {point_type}",
                    "lat": lat,
                    "lon": lon,
                    "heure": datetime.now().strftime("%H:%M:%S"),
                    "description": point_desc
                })
                st.success(f"✅ Point ajouté : {lat}, {lon}")
            except ValueError:
                st.error("❌ Format de coordonnées invalide")
        else:
            st.warning("⚠️ Entrez la latitude et la longitude")

# ==================== CARTE FOLIUM ====================
st.markdown("---")
st.markdown("### 🗺️ Carte des points enregistrés")

# Filtrer les points avec coordonnées
points_avec_coords = [p for p in st.session_state.points if p.get("lat") is not None and p.get("lon") is not None]

if points_avec_coords:
    # Créer la carte
    center_lat = points_avec_coords[0]["lat"]
    center_lon = points_avec_coords[0]["lon"]
    m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
    
    # Ajouter les points
    couleurs = {"depart": "green", "fin_collecte1": "blue", "fin_collecte2": "purple", 
                "point_agent": "orange", "point_manuel": "red"}
    
    for p in points_avec_coords:
        color = couleurs.get(p.get("type", "point_manuel"), "gray")
        popup_text = f"""
        <b>{p.get('titre', 'Point')}</b><br>
        Heure: {p.get('heure', '')}<br>
        """
        if p.get('volume'):
            popup_text += f"Volume: {p['volume']} m³<br>"
        if p.get('description'):
            popup_text += f"Description: {p['description']}<br>"
        
        folium.Marker(
            [p["lat"], p["lon"]],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color=color, icon="info-sign")
        ).add_to(m)
    
    # Tracer le trajet
    if len(points_avec_coords) > 1:
        coords = [[p["lat"], p["lon"]] for p in points_avec_coords]
        folium.PolyLine(coords, color="blue", weight=3, opacity=0.7).add_to(m)
    
    folium_static(m, width=800, height=500)
    
    # Tableau des points
    with st.expander("📋 Détail des points enregistrés"):
        df_points = pd.DataFrame(points_avec_coords)
        st.dataframe(df_points[["titre", "heure", "lat", "lon", "description"]], use_container_width=True)
else:
    st.info("📍 Aucun point GPS enregistré. Utilisez Google Maps pour ajouter votre position.")

# ==================== TERMINER ====================
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("🏁 TERMINER LA TOURNÉE", type="primary", use_container_width=True):
        if st.session_state.collecte1_validee:
            st.session_state.heure_retour = datetime.now().strftime("%H:%M:%S")
            total_volume = st.session_state.volume1 + st.session_state.volume2
            nom_agent = f"{st.session_state.agent_prenom} {st.session_state.agent_nom}"
            
            st.balloons()
            st.success(f"""
            ✅ Tournée terminée avec succès !
            
            📊 **Récapitulatif :**
            - Agent : {nom_agent}
            - Date : {st.session_state.date_tournee}
            - Quartier : {st.session_state.quartier_nom}
            - Équipe : {st.session_state.equipe_nom}
            - Volume total : {total_volume} m³
            - Points GPS : {len(points_avec_coords)}
            - Départ : {st.session_state.heure_depart}
            - Retour : {st.session_state.heure_retour}
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
                            "agent": nom_agent,
                            "vol": total_volume
                        })
                        conn.commit()
                        st.success("✅ Données enregistrées dans la base Neon.tech !")
                except Exception as e:
                    st.warning(f"⚠️ Base de données: {e}")
        else:
            st.warning("⚠️ Veuillez valider la collecte 1 avant de terminer")

# ==================== EXPORT EXCEL ====================
if points_avec_coords:
    with st.expander("📊 Exporter les données en Excel"):
        df_export = pd.DataFrame(points_avec_coords)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, sheet_name="Points GPS", index=False)
            pd.DataFrame([{
                "Agent": f"{st.session_state.agent_prenom} {st.session_state.agent_nom}",
                "Date": st.session_state.date_tournee,
                "Quartier": st.session_state.quartier_nom,
                "Équipe": st.session_state.equipe_nom,
                "Volume total": st.session_state.volume1 + st.session_state.volume2,
                "Heure départ": st.session_state.heure_depart,
                "Heure retour": st.session_state.heure_retour
            }]).to_excel(writer, sheet_name="Récapitulatif", index=False)
        
        st.download_button(
            "📥 Télécharger Excel",
            output.getvalue(),
            f"collecte_{st.session_state.agent_prenom}_{st.session_state.date_tournee}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==================== CONSIGNES SÉCURITÉ ====================
with st.expander("🛡️ Consignes de sécurité (à lire chaque matin)"):
    st.markdown("""
    ### ⚠️ RAPPEL DES CONSIGNES DE SÉCURITÉ
    
    1. **Gestes et postures** : Pliez les jambes pour soulever les charges lourdes
    2. **Protection individuelle** : Portez toujours vos gants et votre masque
    3. **Ne montez jamais sur le tracteur en marche**
    4. **Lors du vidage à la décharge** : Éloignez-vous de la remorque
    5. **Sur la route** : Ne restez pas au milieu pour charger
    6. **Hydratation** : Buvez de l'eau régulièrement
    
    🔔 **En cas de problème, contactez immédiatement votre responsable**
    """)

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"👤 Agent: {st.session_state.agent_prenom} {st.session_state.agent_nom or 'Non connecté'} | 🗑️ Commune de Mékhé | 📍 GPS via Google Maps")
