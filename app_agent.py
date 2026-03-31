import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from streamlit_js_eval import get_geolocation
import io

# Config
st.set_page_config(page_title="Mékhé Propre - Agent", layout="wide")

# CSS - Style Vert Commune de Mékhé
st.markdown("""
    <style>
    .main-header { background: #1b5e20; padding: 20px; color: white; text-align: center; border-radius: 10px; margin-bottom: 20px; }
    .stButton button { height: 70px; font-size: 20px !important; border-radius: 12px !important; font-weight: bold !important; margin-bottom: 10px; }
    .card { background: #f1f8e9; padding: 20px; border-radius: 15px; border-left: 10px solid #43a047; margin-bottom: 20px; }
    .alert-card { background: #ffebee; padding: 15px; border-radius: 10px; border-left: 10px solid #f44336; }
    .success-msg { color: #2e7d32; font-weight: bold; font-size: 18px; padding: 10px; background: #e8f5e9; border-radius: 5px; border: 1px solid #2e7d32; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

# Connexion Neon
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Initialisation de l'état
if 'tid' not in st.session_state: st.session_state.tid = None
if 'gps_data' not in st.session_state: st.session_state.gps_data = []
if 'last_action' not in st.session_state: st.session_state.last_action = ""

# Fonction de capture GPS avec Message
def enregistrer_etape(type_p, desc, col_num, color="green"):
    if not st.session_state.tid:
        st.error("❌ Erreur : Vous devez d'abord démarrer la tournée !")
        return

    loc = get_geolocation()
    if loc and 'coords' in loc:
        lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO points_arret (tournee_id, type_point, latitude, longitude, description, num_collecte)
                    VALUES (:tid, :tp, :lat, :lon, :desc, :nc)
                """), {"tid": st.session_state.tid, "tp": type_p, "lat": lat, "lon": lon, "desc": desc, "nc": col_num})
                conn.commit()
            
            # Mise à jour pour l'affichage
            st.session_state.gps_data.append({
                "Heure": datetime.now().strftime("%H:%M"),
                "Action": desc,
                "lat": lat,
                "lon": lon,
                "Couleur": color
            })
            st.session_state.last_action = f"✅ SUCCESS : '{desc}' enregistré à {datetime.now().strftime('%H:%M')}"
            st.toast(st.session_state.last_action) # Petit message éphémère en bas
        except Exception as e:
            st.error(f"Erreur technique : {e}")
    else:
        st.warning("⚠️ GPS non détecté. Vérifiez que la géolocalisation est activée sur votre téléphone.")

# --- INTERFACE ---
st.markdown('<div class="main-header"><h1>♻️ AGENT COLLECTE - MÉKHÉ</h1></div>', unsafe_allow_html=True)

# Zone de statut (Le message pour l'agent)
if st.session_state.last_action:
    st.markdown(f'<div class="success-msg">{st.session_state.last_action}</div>', unsafe_allow_html=True)

# 1. Configuration
with st.container():
    c1, c2 = st.columns(2)
    with c1:
        agent = st.text_input("👤 Nom de l'Agent", value="Awa")
        q_sel = st.selectbox("🏘️ Quartier", ["Ngaye Diagne", "Ngaye Djité", "HLM", "Mbambara", "Lebou Est", "Lebou Ouest", "Ndiob"])
    with c2:
        e_sel = st.selectbox("👥 Équipe", ["Équipe A", "Équipe B", "Équipe C"])
        dist_km = st.number_input("📏 KM Compteur Final", min_value=0.0)

if not st.session_state.tid:
    if st.button("🚀 DÉMARRER LA JOURNÉE"):
        with engine.connect() as conn:
            res = conn.execute(text("""
                INSERT INTO tournees (agent_nom, equipe_nom, quartier_nom, statut) 
                VALUES (:a, :e, :q, 'en_cours') RETURNING id
            """), {"a": agent, "e": e_sel, "q": q_sel})
            st.session_state.tid = res.fetchone()[0]
            conn.commit()
        st.success(f"Tournée n°{st.session_state.tid} ouverte. Bonne collecte !")

# 2. Bouton d'urgence (Dépôt Sauvage)
st.markdown("---")
if st.button("🚨 SIGNALER UN DÉPÔT SAUVAGE ICI", help="Cliquez si vous voyez un tas d'ordures non autorisé"):
    enregistrer_etape("signalement", "Dépôt Sauvage Signalé", 0, color="red")

# 3. Actions de Tournée
st.markdown('<div class="card">🚛 <b>TOURNÉE N°1 (C1)</b></div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🚩 Départ Dépôt"): enregistrer_etape("depart", "Départ Dépôt C1", 1)
with col2:
    if st.button("🗑️ Début Ramassage"): enregistrer_etape("collecte", "Début Ramassage C1", 1)
with col3:
    if st.button("🏭 Arrivée Décharge"): enregistrer_etape("decharge", "Arrivée Décharge C1", 1)

vol1 = st.number_input("📦 Volume C1 collecté (m³)", min_value=0.0)

# Option Tour 2
if st.checkbox("➕ Faire un deuxième tour (C2)"):
    st.markdown('<div class="card" style="border-left-color: orange;">🚛 <b>TOURNÉE N°2 (C2)</b></div>', unsafe_allow_html=True)
    col4, col5 = st.columns(2)
    with col4:
        if st.button("🗑️ Début C2"): enregistrer_etape("collecte", "Début C2", 2)
    with col5:
        if st.button("🏭 Décharge C2"): enregistrer_etape("decharge", "Arrivée Décharge C2", 2)
    vol2 = st.number_input("📦 Volume C2 collecté (m³)", min_value=0.0)
else:
    vol2 = 0

# 4. Finalisation
st.write("---")
if st.button("💾 ENREGISTRER TOUT ET FERMER", type="primary"):
    total = vol1 + vol2
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE tournees SET volume_c1=:v1, volume_c2=:v2, volume_total_m3=:vt, 
            distance_km=:km, statut='termine' WHERE id=:tid
        """), {"v1": vol1, "v2": vol2, "vt": total, "km": dist_km, "tid": st.session_state.tid})
        conn.commit()
    st.balloons()
    st.success(f"Bravo ! Travail terminé. Total : {total} m³.")

# 5. Carte Interactive
if st.session_state.gps_data:
    st.markdown("### 🗺️ VOTRE CARTE DE COLLECTE")
    df_map = pd.DataFrame(st.session_state.gps_data)
    fig = px.scatter_mapbox(df_map, lat="lat", lon="lon", color="Couleur",
                            color_discrete_map={"green": "#2e7d32", "red": "#f44336"},
                            hover_name="Action", zoom=14, height=500)
    fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)
if st.button("💾 ENREGISTRER TOUT ET GÉNÉRER RAPPORT", type="primary"):
    vol_total = vol1 + (vol2 if st.session_state.show_c2 else 0)
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE tournees SET volume_collecte1 = :v1, volume_collecte2 = :v2, 
            volume_m3 = :vt, distance_parcourue_km = :km, statut = 'termine' WHERE id = :tid
        """), {"v1": vol1, "v2": vol2 if st.session_state.show_c2 else 0, "vt": vol_total, "km": km_final, "tid": st.session_state.tournee_id})
        conn.commit()
    
    # Génération Excel
    df_export = pd.DataFrame([{
        "Date": date_j, "Agent": agent, "Equipe": equipe, "Quartier": q_sel,
        "Volume Total (m3)": vol_total, "KM Final": km_final, "Points GPS": len(st.session_state.points_gps)
    }])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Rapport_Collecte')
    st.download_button(label="📥 Télécharger le fichier Excel", data=output.getvalue(), file_name=f"collecte_{date_j}_{equipe}.xlsx", mime="application/vnd.ms-excel")
    st.balloons()

# ==================== CARTE INTERACTIVE ====================
if st.session_state.points_gps:
    st.markdown("### 🗺️ ITINÉRAIRE DE L'AGENT EN TEMPS RÉEL")
    df_map = pd.DataFrame(st.session_state.points_gps)
    fig = px.scatter_mapbox(df_map, lat="lat", lon="lon", hover_name="Type", hover_data=["Heure"],
                            color="Tour", zoom=14, height=600)
    
    # Ajouter les lignes pour voir le trajet
    if len(df_map) > 1:
        fig.add_trace(go.Scattermapbox(lat=df_map["lat"], lon=df_map["lon"], mode='lines', line=dict(width=3, color='green'), name="Trajet"))
        
    fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)
    
    # Tableau récapitulatif sous la carte
    st.write("📋 Historique des points capturés :")
    st.table(df_map[["Heure", "Type", "Tour"]])
