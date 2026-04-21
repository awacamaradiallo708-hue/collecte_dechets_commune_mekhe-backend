"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version avec GPS via composant HTML/JS personnalisé
"""

import streamlit as st
import pandas as pd
import json
from datetime import date, datetime
from sqlalchemy import create_engine, text
import folium
from streamlit_folium import folium_static
from io import BytesIO
import re
import os
from math import radians, sin, cos, sqrt, atan2

# ==================== CONNEXION BASE NEON.TECH ====================
# Note: Il est recommandé de stocker ceci dans des variables d'environnement
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_43LqPNrhlzWo@ep-misty-mode-al5c7s4f-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require")

@st.cache_resource
def init_connection():
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.error(f"❌ Base non accessible: {e}")
        return None

engine = init_connection()

# ==================== CONFIGURATION PAGE ====================
st.set_page_config(
    page_title="Collecte Déchets - Mékhé",
    page_icon="🗑️",
    layout="wide"
)

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
    .stButton button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
        border-radius: 10px;
    }
    .gps-card {
        background-color: #e3f2fd;
        padding: 0.5rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }
    .gps-button {
        background-color: #2196F3;
        color: white;
        padding: 10px;
        border: none;
        border-radius: 8px;
        width: 100%;
        cursor: pointer;
        font-size: 16px;
        font-weight: bold;
    }
    .lang-box {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== TRADUCTIONS ====================
LANGS = {
    "Français": {
        "title": "Agent de Collecte - Mékhé",
        "info_tournee": "📍 Informations tournée",
        "nom": "✍️ Votre nom",
        "quartier": "Quartier",
        "equipe": "Équipe",
        "tracteur": "Type tracteur",
        "n_parc": "N° Parc",
        "gps_help": "Ouvrez Google Maps, copiez votre position (appui long sur le point bleu) et collez-la ci-dessous.",
        "open_maps": "📍 Ouvrir Google Maps",
        "step_depart": "🏭 DÉPART DU DÉPÔT",
        "step_debut1": "🗑️ DÉBUT COLLECTE 1",
        "step_fin1": "🏁 FIN COLLECTE 1",
        "step_vidage1": "🚛 VIDAGE DÉCHARGE 1",
        "step_debut2": "🗑️ DÉBUT COLLECTE 2",
        "step_fin2": "🏁 FIN COLLECTE 2",
        "step_vidage2": "🚛 VIDAGE DÉCHARGE 2",
        "add_collecte2": "➕ ACTIVER COLLECTE 2",
        "skip_collecte2": "⏭️ PASSER COLLECTE 2",
        "step_retour": "🏁 RETOUR AU DÉPÔT",
        "save": "Enregistrer cette étape",
        "success_save": "Étape enregistrée à",
        "vol": "Volume (m³)",
        "incident": "⚠️ Incident / Problème rencontré",
        "incidents_list": ["Aucun", "Retard", "Panne", "Problème technique", "Route barrée", "Autre"],
        "finish": "✅ TERMINER ET ENREGISTRER",
        "export": "📥 EXPORTER EN EXCEL",
        "new_tournee": "🔄 NOUVELLE TOURNÉE",
        "error_gps": "Format invalide. Utilisez 'latitude, longitude' (ex: 15.11, -16.63)"
    },
    "Wolof": {
        "title": "Liggeeykatu Mbalit - Meexee",
        "info_tournee": "📍 Xibaari liggeey bi",
        "nom": "✍️ Sa tur",
        "quartier": "Gox bi",
        "equipe": "Àndandoo bi",
        "tracteur": "Traktoer bi",
        "n_parc": "N° Parc",
        "gps_help": "Ubbi Google Maps, koppi sa bërëb, sotti ko fii.",
        "open_maps": "📍 Ubbi Google Maps",
        "step_depart": "🏭 GÀDDAAY",
        "step_debut1": "🗑️ TAMBALI WECCI 1",
        "step_fin1": "🏁 JEEXAL WECCI 1",
        "step_vidage1": "🚛 SOTTI 1",
        "step_debut2": "🗑️ TAMBALI WECCI 2",
        "step_fin2": "🏁 JEEXAL WECCI 2",
        "step_vidage2": "🚛 SOTTI 2",
        "add_collecte2": "➕ YOKKU WECCI 2",
        "skip_collecte2": "⏭️ TUKKI WECCI 2",
        "step_retour": "🏁 ÑIBI",
        "save": "Bind li am",
        "success_save": "Bind nañ ko ci",
        "vol": "Mbalit wi (m³)",
        "incident": "⚠️ Jafe-jafe bu am",
        "incidents_list": ["Amul", "Xar", "Yàqu", "Jafe-jafe teknik", "Yoon bu tëju", "Leneen"],
        "finish": "✅ JEEXAL LIGGEEY BI",
        "export": "📥 WÀCCI FATU EXCEL BI",
        "new_tournee": "🔄 TAMBALI LENEEN",
        "error_gps": "Mbind mi baaxul. Sotti ko ni: 'latitude, longitude'"
    }
}

# ==================== INITIALISATION SESSION ====================
if 'lang' not in st.session_state:
    st.session_state.lang = "Français"
if 'agent_nom' not in st.session_state:
    st.session_state.agent_nom = ""
if 'role' not in st.session_state:
    st.session_state.role = "agent"
if 'quartier' not in st.session_state:
    st.session_state.quartier = "HLM"
if 'equipe' not in st.session_state:
    st.session_state.equipe = "Équipe A"
if 'type_tracteur' not in st.session_state:
    st.session_state.type_tracteur = "TAFE"
if 'numero_parc' not in st.session_state:
    st.session_state.numero_parc = ""
if 'incident' not in st.session_state:
    st.session_state.incident = "Aucun"

# Points et horaires
if 'points' not in st.session_state:
    st.session_state.points = []
if 'horaires' not in st.session_state:
    st.session_state.horaires = {}
if 'volumes' not in st.session_state:
    st.session_state.volumes = {"collecte1": 0.0, "collecte2": 0.0}
if 'collecte2_active' not in st.session_state:
    st.session_state.collecte2_active = False
if 'collecte1_terminee' not in st.session_state:
    st.session_state.collecte1_terminee = False

# ==================== FONCTIONS UTILES ====================
def exporter_excel(session):
    output = BytesIO()
    df_points = pd.DataFrame(session.points)
    df_resume = pd.DataFrame([{
        "Agent": session.agent_nom,
        "Quartier": session.quartier,
        "Equipe": session.equipe,
        "Incident": session.incident,
        "Volume 1": session.volumes["collecte1"],
        "Volume 2": session.volumes["collecte2"],
        "Date": date.today()
    }])
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_resume.to_excel(writer, sheet_name="Résumé", index=False)
        df_points.to_excel(writer, sheet_name="Points et Horaires", index=False)
    return output.getvalue()

# ==================== SIDEBAR ====================
with st.sidebar:
    st.session_state.lang = st.selectbox("🌍 Langue / Kàllaama", ["Français", "Wolof"])
    t = LANGS[st.session_state.lang]

    st.markdown(f"### 🗑️ {t['title']}")

    mode = st.radio("🔐 Mode", ["🧑‍🌾 Agent de terrain", "📊 Responsable / Dashboard"])
    
    if mode == "🧑‍🌾 Agent de terrain":
        st.session_state.role = "agent"
        st.markdown("---")
        st.session_state.agent_nom = st.text_input(t["nom"], value=st.session_state.agent_nom)
        
        st.markdown("---")
        st.markdown(f"### {t['info_tournee']}")
        st.session_state.quartier = st.selectbox(t["quartier"], ["HLM", "NDIOP", "LEBOU EST", "NGAYE DIAGNE", "MAMBARA", "NGAYE DJITTE", "LEBOU OUEST"])
        st.session_state.equipe = st.selectbox(t["equipe"], ["Équipe A", "Équipe B", "Équipe C", "Équipe D"])
        st.session_state.type_tracteur = st.selectbox(t["tracteur"], ["TAFE", "New Holland", "Massey Ferguson", "John Deere"])
        st.session_state.numero_parc = st.text_input(t["n_parc"], value=st.session_state.numero_parc)
        
    else:
        st.session_state.role = "dashboard"

# ==================== MODE AGENT ====================
if st.session_state.role == "agent":
    
    st.markdown(f"""
    <div class="main-header">
        <h1>🗑️ {t.get('title')}</h1>
        <p>{t.get('gps_help')}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<a href="https://www.google.com/maps/search/ma+position" target="_blank" class="gps-button" style="text-decoration:none; display:block; text-align:center;">{t["open_maps"]}</a>', unsafe_allow_html=True)

    # Affichage des infos
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"👤 **{t['nom'].split(' ')[1]}:** {st.session_state.agent_nom}")
    with col2:
        st.info(f"📍 **{t['quartier']}:** {st.session_state.quartier}")
    with col3:
        st.info(f"👥 **{t['equipe']}:** {st.session_state.equipe}")

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🚜 **{t['tracteur']}:** {st.session_state.type_tracteur}")
    with col2:
        st.info(f"🔢 **{t['n_parc']}:** {st.session_state.numero_parc or '---'}")

    st.markdown("---")

    # ==================== ÉTAPES DE COLLECTE ====================
    etapes = [
        ("depart", t["step_depart"]),
        ("debut_collecte1", t["step_debut1"]),
        ("fin_collecte1", t["step_fin1"]),
        ("decharge1", t["step_vidage1"]),
    ]

    # Ajout de la collecte 2 si activée
    if st.session_state.collecte1_terminee and not st.session_state.collecte2_active:
        st.markdown("### 🚛 COLLECTE 2 (OPTIONNELLE)")
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t["add_collecte2"], use_container_width=True):
                st.session_state.collecte2_active = True
                st.rerun()
        with col2:
            if st.button(t["skip_collecte2"], use_container_width=True):
                st.session_state.collecte2_active = True
                st.info("Collecte 2 ignorée")
                st.rerun()
    
    if st.session_state.collecte2_active and "fin_collecte2" not in st.session_state.horaires:
        st.markdown("---")
        st.markdown("## 🚛 COLLECTE 2")
        
        # DÉBUT COLLECTE 2
        st.markdown(f"### {t['step_debut2']}")
        if st.button("✅ Enregistrer DÉBUT COLLECTE 2", key="btn_debut2", use_container_width=True):
            if enregistrer_etape("debut_collecte2", t['step_debut2']):
                st.rerun()
        if "debut_collecte2" in st.session_state.horaires:
            st.success(f"✅ DÉBUT COLLECTE 2 à {st.session_state.horaires['debut_collecte2']}")
        
        # FIN COLLECTE 2
        st.markdown(f"### {t['step_fin2']}")
        if st.button("✅ Enregistrer FIN COLLECTE 2", key="btn_fin2", use_container_width=True):
            if enregistrer_etape("fin_collecte2", t['step_fin2']):
                st.rerun()
        if "fin_collecte2" in st.session_state.horaires:
            st.success(f"✅ FIN COLLECTE 2 à {st.session_state.horaires['fin_collecte2']}")
        
        # VIDAGE DÉCHARGE 2
        st.markdown(f"### {t['step_vidage2']}")
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("✅ Enregistrer VIDAGE 2", key="btn_vidage2", use_container_width=True):
                if enregistrer_etape("decharge2", t['step_vidage2']):
                    st.rerun()
        with col2:
            v2 = st.number_input(t['vol'], 0.0, 30.0, st.session_state.volumes["collecte2"], 0.5, key="vol2")
            if v2 != st.session_state.volumes["collecte2"]:
                st.session_state.volumes["collecte2"] = v2
        if "decharge2" in st.session_state.horaires:
            st.success(f"✅ VIDAGE 2 à {st.session_state.horaires['decharge2']}")
    
    st.markdown("---")
    
    # Incident et Export
    st.session_state.incident = st.selectbox(t["incident"], t["incidents_list"])

    col1, col2 = st.columns(2)
    with col1:
        excel_data = exporter_excel(st.session_state)
        st.download_button(t["export"], excel_data, f"collecte_{date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    
    # ==================== RÉCAPITULATIF ====================
    with st.expander("📋 Voir le récapitulatif"):
        if st.session_state.horaires:
            st.markdown("**Horaires enregistrés :**")
            for key, value in st.session_state.horaires.items():
                st.write(f"- {key}: {value}")
        
        if st.session_state.points:
            st.markdown("**Points GPS enregistrés :**")
            for p in st.session_state.points:
                st.write(f"- {p['titre']} à {p['heure']} → ({p['lat']:.6f}, {p['lon']:.6f})")
    
    # ==================== CARTE ====================
    points_valides = [p for p in st.session_state.points if p.get("lat") and p.get("lon")]
    if len(points_valides) >= 1:
        st.markdown("### 🗺️ Carte des points GPS")
        
        center_lat = points_valides[0]["lat"]
        center_lon = points_valides[0]["lon"]
        m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
        
        couleurs = {
            "depart": "green",
            "debut_collecte1": "blue",
            "fin_collecte1": "lightblue",
            "decharge1": "red",
            "debut_collecte2": "purple",
            "fin_collecte2": "lightpurple",
            "decharge2": "darkred",
            "retour": "brown"
        }
        
        for p in points_valides:
            color = couleurs.get(p["type"], "gray")
            folium.Marker(
                [p["lat"], p["lon"]],
                popup=f"<b>{p['titre']}</b><br>{p['heure']}",
                icon=folium.Icon(color=color)
            ).add_to(m)
        
        if len(points_valides) > 1:
            coords = [[p["lat"], p["lon"]] for p in points_valides]
            folium.PolyLine(coords, color="blue", weight=3, opacity=0.7).add_to(m)
            
            # Calculer distance
            distance_totale = 0
            for i in range(1, len(coords)):
                R = 6371
                lat1, lon1, lat2, lon2 = map(radians, [coords[i-1][0], coords[i-1][1], coords[i][0], coords[i][1]])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                distance_totale += R * c
            st.caption(f"📏 Distance totale parcourue : {distance_totale:.2f} km")
        
        folium_static(m, width=800, height=400)
    
    # ==================== TERMINER ====================
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(t["finish"], type="primary", use_container_width=True):
            if not st.session_state.horaires.get("depart"):
                st.error("❌ Veuillez enregistrer le DÉPART")
            elif st.session_state.volumes["collecte1"] == 0:
                st.error("❌ Veuillez entrer le volume de la collecte 1")
            else:
                st.balloons()
                
                # Calcul distance totale
                dist_total = 0
                pts = st.session_state.points
                if len(pts) > 1:
                    for i in range(1, len(pts)):
                        lat1, lon1, lat2, lon2 = map(radians, [pts[i-1]["lat"], pts[i-1]["lon"], pts[i]["lat"], pts[i]["lon"]])
                        dlat = lat2 - lat1
                        dlon = lon2 - lon1
                        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                        c = 2 * atan2(sqrt(a), sqrt(1-a))
                        dist_total += 6371 * c

                # Enregistrement dans la base
                if engine:
                    try:
                        with engine.connect() as conn:
                            vol_total = st.session_state.volumes["collecte1"] + st.session_state.volumes["collecte2"]
                            result = conn.execute(text("""
                                INSERT INTO tournees (
                                    date_tournee, agent_nom,
                                    volume_collecte1, volume_collecte2, volume_m3, distance_parcourue_km,
                                    heure_depot_depart, heure_retour_depot,
                                    heure_debut_collecte1, heure_fin_collecte1,
                                    heure_arrivee_decharge1, 
                                    heure_debut_collecte2, heure_fin_collecte2, heure_arrivee_decharge2,
                                    statut
                                ) VALUES (
                                    :date, :agent, 
                                    :vol1, :vol2, :vol_t, :dist,
                                    :depart, :retour, :debut1, :fin1, :decharge1, :debut2, :fin2, :decharge2, 'termine'
                                ) RETURNING id
                            """), {
                                "date": date.today(),
                                "agent": st.session_state.agent_nom,
                                "vol1": st.session_state.volumes["collecte1"],
                                "vol2": st.session_state.volumes["collecte2"],
                                "vol_t": vol_total,
                                "dist": dist_total,
                                "depart": st.session_state.horaires.get("depart"),
                                "retour": st.session_state.horaires.get("retour"),
                                "debut1": st.session_state.horaires.get("debut_collecte1"),
                                "fin1": st.session_state.horaires.get("fin_collecte1"),
                                "decharge1": st.session_state.horaires.get("decharge1")
                            })
                            tournee_id = result.fetchone()[0]
                            
                            for point in st.session_state.points:
                                conn.execute(text("""
                                    INSERT INTO points_arret (tournee_id, type_point, lat, lon, heure)
                                    VALUES (:tid, :type, :p_lat, :p_lon, :heure)
                                """), {
                                    "tid": tournee_id,
                                    "type": point["type"],
                                    "lat": point["lat"],
                                    "lon": point["lon"],
                                    "heure": point["heure"]
                                })
                            conn.commit()
                    except Exception as e:
                        st.warning(f"⚠️ Base: {e}")
                
                st.success("✅ Tournée terminée !")

                # Réinitialisation
                if st.button(t["new_tournee"], use_container_width=True):
                    st.session_state.points = []
                    st.session_state.horaires = {}
                    st.session_state.volumes = {"collecte1": 0.0, "collecte2": 0.0}
                    st.session_state.collecte2_active = False
                    st.session_state.collecte1_terminee = False
                    st.rerun()

# ==================== MODE DASHBOARD ====================
else:
    st.markdown("""
    <div class="main-header">
        <h1>📊 Tableau de bord - Collecte des déchets</h1>
        <p>Commune de Mékhé</p>
    </div>
    """, unsafe_allow_html=True)
    
    if engine:
        try:
            df_tournees = pd.read_sql("SELECT * FROM tournees ORDER BY date_tournee DESC LIMIT 100", engine)
            df_points = pd.read_sql("SELECT * FROM points_arret WHERE lat IS NOT NULL ORDER BY id DESC LIMIT 500", engine)
            
            if df_tournees.empty:
                st.info("📭 Aucune collecte enregistrée")
            else:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📋 Collectes", len(df_tournees))
                with col2:
                    total_volume = df_tournees["volume_collecte1"].sum() + df_tournees["volume_collecte2"].sum()
                    st.metric("📦 Volume total", f"{total_volume:.1f} m³")
                with col3:
                    st.metric("📍 Points GPS", len(df_points))
                with col4:
                    st.metric("👤 Dernier agent", df_tournees.iloc[0]["agent_nom"] if not df_tournees.empty else "-")
                
                if not df_points.empty:
                    st.subheader("🗺️ Carte des points GPS")
                    points_map = df_points.dropna(subset=["lat", "lon"])
                    if not points_map.empty:
                        m = folium.Map(location=[points_map["lat"].mean(), points_map["lon"].mean()], zoom_start=13)
                        for _, p in points_map.iterrows():
                            folium.Marker([p["lat"], p["lon"]], popup=p["type_point"], icon=folium.Icon(color="blue")).add_to(m)
                        folium_static(m, width=800, height=400)
                
                st.subheader("📋 Liste des collectes")
                st.dataframe(df_tournees[["date_tournee", "agent_nom", "volume_collecte1", "volume_collecte2"]], use_container_width=True)
                
                if st.button("📥 EXPORTER EN EXCEL"):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_tournees.to_excel(writer, sheet_name="Collectes", index=False)
                        if not df_points.empty:
                            df_points.to_excel(writer, sheet_name="Points GPS", index=False)
                    st.download_button("📥 Télécharger", output.getvalue(), f"dashboard_mekhe_{date.today()}.xlsx")
        except Exception as e:
            st.info(f"📭 Base en attente: {e}")

# ==================== CONSIGNES SÉCURITÉ ====================
with st.expander("🛡️ Consignes de sécurité"):
    st.markdown("""
    1. **Gestes et postures** : Pliez les jambes pour soulever
    2. **Protection** : Portez gants et masque
    3. **Ne montez pas sur le tracteur**
    4. **Éloignez-vous lors du vidage**
    5. **Circulation** : Ne restez pas au milieu de la route
    """)

st.caption(f"📍 GPS via composant HTML | {'Agent: ' + st.session_state.agent_nom if st.session_state.role == 'agent' else 'Dashboard'} | 🗑️ Commune de Mékhé")
