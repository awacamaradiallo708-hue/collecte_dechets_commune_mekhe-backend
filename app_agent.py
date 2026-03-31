import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from streamlit_js_eval import get_geolocation
import io

st.set_page_config(page_title="Suivi Collecte Mékhé", page_icon="🗑️", layout="wide")

# ==================== STYLE CSS ====================
st.markdown("""
    <style>
    .main-header { background: linear-gradient(135deg, #1e5128 0%, #4e944f 100%); padding: 2rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 2rem; }
    .stButton button { width: 100%; padding: 15px !important; font-size: 20px !important; font-weight: bold !important; border-radius: 12px !important; }
    .card { background: #f8f9fa; padding: 1.5rem; border-radius: 15px; border-left: 8px solid #1e5128; margin-bottom: 1rem; }
    label { font-size: 18px !important; font-weight: bold; color: #1e5128; }
    </style>
""", unsafe_allow_html=True)

# ==================== CONNEXION & CONFIG ====================
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

if 'points_gps' not in st.session_state: st.session_state.points_gps = []
if 'tournee_id' not in st.session_state: st.session_state.tournee_id = None
if 'show_c2' not in st.session_state: st.session_state.show_c2 = False

# ==================== FONCTIONS ====================
def enregistrer_gps_sql(tid, type_p, desc, col_num):
    loc = get_geolocation()
    if loc and 'coords' in loc:
        lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description, collecte_numero)
                    VALUES (:tid, :h, :t, :lat, :lon, :d, :c)
                """), {"tid": tid, "h": datetime.now(), "t": type_p, "lat": lat, "lon": lon, "d": desc, "c": col_num})
                conn.commit()
            st.session_state.points_gps.append({"Heure": datetime.now().strftime("%H:%M"), "Type": desc, "lat": lat, "lon": lon, "Tour": col_num})
            st.success(f"📍 Point enregistré : {desc}")
        except Exception as e: st.error(f"Erreur BDD : {e}")
    else:
        st.warning("Veuillez activer le GPS sur votre téléphone.")

# ==================== INTERFACE D'ACCUEIL ====================
st.markdown('<div class="main-header"><h1>♻️ SUIVI COLLECTE MÉKHÉ</h1><p>Interface de saisie et cartographie temps réel</p></div>', unsafe_allow_html=True)

with st.container():
    c1, c2, c3 = st.columns(3)
    with c1:
        agent = st.text_input("👤 Nom de l'Agent", value="Awa")
        equipe = st.selectbox("👥 Équipe de collecte", ["Équipe A", "Équipe B", "Équipe C", "Équipe D"])
    with c2:
        date_j = st.date_input("📅 Date", value=date.today())
        try:
            with engine.connect() as conn:
                q_list = conn.execute(text("SELECT nom FROM quartiers WHERE actif = true")).fetchall()
                quartiers = [r[0] for r in q_list]
            q_sel = st.selectbox("🏘️ Quartier de collecte", quartiers if quartiers else ["NDIOP"])
        except: q_sel = st.selectbox("🏘️ Quartier", ["NDIOP"])
    with c3:
        km_final = st.number_input("📏 KM Compteur Final", min_value=0.0)

if st.button("🚀 DÉMARRER LA COLLECTE DU JOUR") and not st.session_state.tournee_id:
    with engine.connect() as conn:
        res = conn.execute(text("""
            INSERT INTO tournees (date_tournee, agent_nom, equipe, statut) 
            VALUES (:d, :a, :e, 'en_cours') RETURNING id
        """), {"d": date_j, "a": agent, "e": equipe})
        st.session_state.tournee_id = res.fetchone()[0]
        conn.commit()
    st.success(f"✅ Tournée n°{st.session_state.tournee_id} ouverte pour l'{equipe}")

# ==================== TOURS DE COLLECTE ====================
# --- TOUR 1 ---
st.markdown('<div class="card">🚛 <b>PREMIÈRE TOURNÉE (C1)</b></div>', unsafe_allow_html=True)
t1_col1, t1_col2 = st.columns(2)
with t1_col1:
    if st.button("📍 DÉPART DÉPÔT"): enregistrer_gps_sql(st.session_state.tournee_id, "depart_depot", "Départ Dépôt C1", 1)
    if st.button("📍 DÉBUT RAMASSAGE"): enregistrer_gps_sql(st.session_state.tournee_id, "debut_collecte", "Début Ramassage C1", 1)
with t1_col2:
    if st.button("📍 FIN & DÉCHARGE"): enregistrer_gps_sql(st.session_state.tournee_id, "arrivee_decharge", "Fin & Décharge C1", 1)
    vol1 = st.number_input("📦 Volume C1 (m³)", min_value=0.0, value=10.0)

# --- TOUR 2 OPTIONNEL ---
if not st.session_state.show_c2:
    if st.button("➕ AJOUTER UNE DEUXIÈME TOURNÉE (C2)"):
        st.session_state.show_c2 = True
        st.rerun()
else:
    st.markdown('<div class="card" style="border-left-color: #FF9800;">🚛 <b>DEUXIÈME TOURNÉE (C2)</b></div>', unsafe_allow_html=True)
    t2_col1, t2_col2 = st.columns(2)
    with t2_col1:
        if st.button("📍 DÉBUT C2"): enregistrer_gps_sql(st.session_state.tournee_id, "debut_collecte", "Début C2", 2)
    with t2_col2:
        if st.button("📍 RETOUR FINAL"): enregistrer_gps_sql(st.session_state.tournee_id, "retour_depot", "Retour Final", 2)
        vol2 = st.number_input("📦 Volume C2 (m³)", min_value=0.0, value=5.0)

# ==================== SAUVEGARDE & EXCEL ====================
st.write("---")
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
