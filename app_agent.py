"""
APPLICATION AGENT DE COLLECTE - COMMUNE DE MÉKHÉ
Version simplifiée avec saisie des heures, volumes, distance
Ajout d'un champ unique pour enregistrer des points GPS (copier-coller depuis Google Maps)
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from io import BytesIO
import re

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

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte</h1><p>Commune de Mékhé | Saisie des collectes</p></div>', unsafe_allow_html=True)

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

def enregistrer_point_gps(tournee_id, lat, lon, description, collecte_numero=None):
    """Enregistre un point GPS dans la table points_arret"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description, collecte_numero)
                VALUES (:tid, :heure, :type, :lat, :lon, :desc, :collecte)
            """), {
                "tid": tournee_id,
                "heure": datetime.now(),
                "type": "point_saisi",
                "lat": lat,
                "lon": lon,
                "desc": description,
                "collecte": collecte_numero
            })
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur enregistrement point: {e}")
        return False

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
if 'distance_totale' not in st.session_state:
    st.session_state.distance_totale = 0.0
if 'temps_debut_tournee' not in st.session_state:
    st.session_state.temps_debut_tournee = None
if 'tournee_id' not in st.session_state:
    st.session_state.tournee_id = None
if 'points_saisis' not in st.session_state:
    st.session_state.points_saisis = []   # pour stocker temporairement les points avant enregistrement final

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
    st.markdown("### 📍 Points GPS (optionnel)")
    st.markdown("""
    Pour ajouter un point de repère :
    1. Cliquez sur le lien ci‑dessous pour ouvrir Google Maps.
    2. Activez votre position (icône de localisation).
    3. Copiez les coordonnées affichées (ex: `15.121048, -16.686826`).
    4. Collez‑les dans le champ ci‑dessous.
    """)
    st.markdown("""
    <a href="https://www.google.com/maps/search/ma+position" target="_blank">
        <button style="background:#2196F3; color:white; border:none; padding:10px; border-radius:8px; width:100%; margin-bottom:10px;">📍 OBTENIR MA POSITION (Google Maps)</button>
    </a>
    """, unsafe_allow_html=True)
    
    coords = st.text_input("Coordonnées (latitude, longitude)", placeholder="Ex: 15.121048, -16.686826")
    description = st.text_input("Description (optionnel)", placeholder="Ex: Entrée du quartier")
    if st.button("➕ Enregistrer ce point", use_container_width=True):
        if coords.strip():
            # Essayer d'extraire latitude et longitude
            match = re.search(r"([-+]?\d+\.\d+)\s*,\s*([-+]?\d+\.\d+)", coords)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                st.session_state.points_saisis.append({
                    "lat": lat,
                    "lon": lon,
                    "description": description or "Point saisi",
                    "heure": datetime.now().strftime("%H:%M:%S")
                })
                st.success(f"✅ Point enregistré temporairement : {lat}, {lon}")
            else:
                st.error("Format invalide. Utilisez 'latitude, longitude' (ex: 15.121048, -16.686826)")
        else:
            st.warning("Veuillez entrer des coordonnées")
    
    if st.session_state.points_saisis:
        st.markdown("**Points enregistrés dans cette tournée :**")
        for i, p in enumerate(st.session_state.points_saisis):
            st.write(f"{i+1}. {p['lat']:.6f}, {p['lon']:.6f} - {p['description']} ({p['heure']})")
        if st.button("🗑️ Effacer tous les points", use_container_width=True):
            st.session_state.points_saisis = []
            st.rerun()
    
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
    
    st.markdown("---")
    # Bouton pour exporter les collectes du jour de cet agent
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

# ==================== SAISIE DES HEURES ET DISTANCE ====================
st.markdown("---")
st.markdown("### 🕐 SAISIE DES HEURES ET DISTANCE")

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

st.markdown("---")
st.markdown("### 📏 DISTANCE PARCOURUE")
st.session_state.distance_totale = st.number_input("Distance totale (km)", min_value=0.0, step=0.5, value=st.session_state.distance_totale)

# ==================== COLLECTE 1 ====================
st.markdown("---")
st.markdown('<div class="collecte-card">🚛 COLLECTE 1</div>', unsafe_allow_html=True)

if not st.session_state.collecte1_validee:
    
    st.markdown("#### 🏭 DÉPART DÉPÔT")
    st.caption(f"Heure: {st.session_state.heure_depot_depart}")
    
    st.markdown("#### 🗑️ DÉBUT COLLECTE 1")
    st.caption(f"Heure: {st.session_state.heure_debut_collecte1}")
    
    st.markdown("#### 🗑️ FIN COLLECTE 1")
    st.caption(f"Heure: {st.session_state.heure_fin_collecte1}")
    
    st.markdown("#### 🚛 DÉPART DÉCHARGE 1")
    st.caption(f"Heure: {st.session_state.heure_depart_decharge1}")
    
    st.markdown("#### 🏭 ARRIVÉE DÉCHARGE 1")
    st.caption(f"Heure: {st.session_state.heure_arrivee_decharge1}")
    
    st.markdown("#### 🏭 SORTIE DÉCHARGE 1 + VOLUME")
    col1, col2 = st.columns(2)
    with col1:
        volume1 = st.number_input("Volume déchargé (m³)", min_value=0.0, step=0.5, key="vol1", value=st.session_state.volume1)
    with col2:
        if st.button("💾 Enregistrer volume", key="save_vol1", use_container_width=True):
            if volume1 > 0:
                st.session_state.volume1 = volume1
                st.success(f"✅ Volume enregistré : {volume1} m³")
            else:
                st.warning("⚠️ Veuillez saisir un volume positif")
    
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
        
        st.markdown("#### 🗑️ DÉBUT COLLECTE 2")
        st.caption(f"Heure: {st.session_state.heure_debut_collecte2}")
        
        st.markdown("#### 🗑️ FIN COLLECTE 2")
        st.caption(f"Heure: {st.session_state.heure_fin_collecte2}")
        
        st.markdown("#### 🚛 DÉPART DÉCHARGE 2")
        st.caption(f"Heure: {st.session_state.heure_depart_decharge2}")
        
        st.markdown("#### 🏭 ARRIVÉE DÉCHARGE 2")
        st.caption(f"Heure: {st.session_state.heure_arrivee_decharge2}")
        
        st.markdown("#### 🏭 SORTIE DÉCHARGE 2 + VOLUME")
        col1, col2 = st.columns(2)
        with col1:
            volume2 = st.number_input("Volume déchargé (m³)", min_value=0.0, step=0.5, key="vol2", value=st.session_state.volume2)
        with col2:
            if st.button("💾 Enregistrer volume", key="save_vol2", use_container_width=True):
                if volume2 > 0:
                    st.session_state.volume2 = volume2
                    st.success(f"✅ Volume enregistré : {volume2} m³")
                else:
                    st.warning("⚠️ Veuillez saisir un volume positif")
        
        st.markdown("#### 🏁 RETOUR DÉPÔT")
        st.caption(f"Heure: {st.session_state.heure_retour_depot}")
        
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
        st.metric("📏 Distance", f"{st.session_state.distance_totale:.2f} km")
    
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
                    
                    # Enregistrer les points GPS temporaires
                    for point in st.session_state.points_saisis:
                        enregistrer_point_gps(tournee_id, point['lat'], point['lon'], point['description'], None)
                    
                    conn.commit()
                
                st.balloons()
                st.success("✅ Tournée enregistrée !")
                
                # Réinitialiser pour une nouvelle tournée
                if st.button("🔄 NOUVELLE TOURNÉE", use_container_width=True):
                    st.session_state.collecte1_validee = False
                    st.session_state.collecte2_validee = False
                    st.session_state.collecte2_optionnelle = False
                    st.session_state.volume1 = 0.0
                    st.session_state.volume2 = 0.0
                    st.session_state.distance_totale = 0.0
                    st.session_state.temps_debut_tournee = None
                    st.session_state.points_saisis = []
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erreur lors de l'enregistrement: {e}")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"👤 Agent: {st.session_state.agent_nom or 'Non connecté'} | 🗑️ Commune de Mékhé")
