import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="Agent Collecte - Mékhé", page_icon="🗑️", layout="wide")

# ==================== STYLE CSS GÉANT ====================
st.markdown("""
    <style>
    .main-header { background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%); padding: 1.5rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 1.5rem; }
    .stButton button { width: 100%; padding: 20px !important; font-size: 22px !important; font-weight: bold !important; border-radius: 15px !important; }
    .collecte-card { background: #e8f5e9; padding: 1.5rem; border-radius: 15px; border-left: 10px solid #4CAF50; margin-bottom: 1.5rem; }
    .collecte2-card { background: #fff8e7; padding: 1.5rem; border-radius: 15px; border-left: 10px solid #FF9800; margin-bottom: 1.5rem; }
    .option-card { background: #f0f2f6; padding: 1rem; border-radius: 15px; text-align: center; margin: 1rem 0; border: 2px dashed #999; }
    label { font-size: 20px !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ AGENT DE COLLECTE - MÉKHÉ</h1><p>Gestion flexible des tours de collecte</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BDD ====================
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS GPS & SQL ====================
def capturer_gps():
    loc = get_geolocation()
    if loc and 'coords' in loc:
        return loc['coords']['latitude'], loc['coords']['longitude']
    return None, None

def enregistrer_point_sql(tournee_id, type_p, desc, col_num):
    if not tournee_id:
        st.error("❌ Cliquez d'abord sur 'DÉMARRER LA JOURNÉE'")
        return
    lat, lon = capturer_gps()
    if lat and lon:
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO points_arret (tournee_id, heure, type_point, latitude, longitude, description, collecte_numero)
                    VALUES (:tid, :heure, :type, :lat, :lon, :desc, :col)
                """), {"tid": tournee_id, "heure": datetime.now(), "type": type_p, "lat": lat, "lon": lon, "desc": desc, "col": col_num})
                conn.commit()
            st.session_state.points_gps.append({"lat": lat, "lon": lon, "type": type_p, "col": col_num})
            st.success(f"📍 Position GPS enregistrée pour le tour {col_num} !")
        except Exception as e:
            st.error(f"Erreur SQL : {e}")

# ==================== INITIALISATION ====================
if 'points_gps' not in st.session_state: st.session_state.points_gps = []
if 'tournee_id' not in st.session_state: st.session_state.tournee_id = None
if 'show_c2' not in st.session_state: st.session_state.show_c2 = False

# ==================== EN-TÊTE TOURNÉE ====================
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        agent = st.text_input("👤 NOM DE L'AGENT", key="agent_nom")
        date_j = st.date_input("📅 DATE", value=date.today())
    with col2:
        try:
            with engine.connect() as conn:
                q_list = conn.execute(text("SELECT id, nom FROM quartiers WHERE actif = true")).fetchall()
                quartiers = {r[1]: r[0] for r in q_list}
            quartier_sel = st.selectbox("🏘️ QUARTIER", list(quartiers.keys()) if quartiers else ["Centre"])
        except:
            quartier_sel = st.selectbox("🏘️ QUARTIER", ["Mékhé Centre"])
        dist_km = st.number_input("📏 KM COMPTEUR FINAL", min_value=0.0)

if st.button("🚀 DÉMARRER LA JOURNÉE / CRÉER TOURNÉE") and not st.session_state.tournee_id:
    with engine.connect() as conn:
        res = conn.execute(text("""
            INSERT INTO tournees (date_tournee, quartier_id, agent_nom, statut) 
            VALUES (:d, :q, :a, 'en_cours') RETURNING id
        """), {"d": date_j, "q": quartiers.get(quartier_sel, 1), "a": agent})
        st.session_state.tournee_id = res.fetchone()[0]
        conn.commit()
    st.success(f"✅ Tournée n°{st.session_state.tournee_id} ouverte !")

# ==================== COLLECTE 1 (OBLIGATOIRE) ====================
st.markdown('<div class="collecte-card">🚛 <b>PREMIER TOUR (C1)</b></div>', unsafe_allow_html=True)
c1a, c1b = st.columns(2)
with c1a:
    h_dep1 = st.text_input("⏰ Heure Départ Dépôt", value="07:00", key="h_dep1")
    if st.button("📍 ENR. DÉPART DÉPÔT (C1)"): 
        enregistrer_point_sql(st.session_state.tournee_id, "depart_depot", "Départ C1", 1)
    
    h_deb1 = st.text_input("⏰ Heure Début Collecte", value="07:30", key="h_deb1")
    if st.button("📍 ENR. DÉBUT RAMASSAGE (C1)"): 
        enregistrer_point_sql(st.session_state.tournee_id, "debut_collecte", "Début C1", 1)

with c1b:
    h_fin1 = st.text_input("⏰ Heure Fin Collecte", value="09:30", key="h_fin1")
    if st.button("📍 ENR. FIN RAMASSAGE (C1)"): 
        enregistrer_point_sql(st.session_state.tournee_id, "fin_collecte", "Fin C1", 1)
    
    vol1 = st.number_input("📦 Volume Collecté C1 (m³)", min_value=0.0, key="vol1")

st.markdown("<b>🏭 DÉCHARGE C1</b>", unsafe_allow_html=True)
d1a, d1b = st.columns(2)
with d1a:
    h_ent1 = st.text_input("⏰ Entrée Décharge 1", value="10:00")
    if st.button("📍 ENR. ENTRÉE DÉCHARGE (C1)"): 
        enregistrer_point_sql(st.session_state.tournee_id, "arrivee_decharge", "Entrée Déch 1", 1)
with d1b:
    h_sor1 = st.text_input("⏰ Sortie Décharge 1", value="10:30")
    if st.button("📍 ENR. SORTIE DÉCHARGE (C1)"): 
        enregistrer_point_sql(st.session_state.tournee_id, "sortie_decharge", "Sortie Déch 1", 1)

# ==================== CHOIX DEUXIÈME TOUR ====================
if not st.session_state.show_c2:
    st.markdown('<div class="option-card">', unsafe_allow_html=True)
    if st.button("➕ AJOUTER UN DEUXIÈME TOUR (C2)"):
        st.session_state.show_c2 = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="collecte2-card">🚛 <b>DEUXIÈME TOUR (C2)</b></div>', unsafe_allow_html=True)
    if st.button("❌ ANNULER LE DEUXIÈME TOUR"):
        st.session_state.show_c2 = False
        st.rerun()
        
    c2a, c2b = st.columns(2)
    with c2a:
        h_dep2 = st.text_input("⏰ Heure Départ vers C2", value="11:00")
        if st.button("📍 ENR. DÉPART (C2)"): 
            enregistrer_point_sql(st.session_state.tournee_id, "depart_depot", "Départ C2", 2)
        h_deb2 = st.text_input("⏰ Heure Début Collecte C2", value="11:15")
        if st.button("📍 ENR. DÉBUT RAMASSAGE (C2)"): 
            enregistrer_point_sql(st.session_state.tournee_id, "debut_collecte", "Début C2", 2)
    with c2b:
        h_fin2 = st.text_input("⏰ Heure Fin Collecte C2", value="13:00")
        if st.button("📍 ENR. FIN RAMASSAGE (C2)"): 
            enregistrer_point_sql(st.session_state.tournee_id, "fin_collecte", "Fin C2", 2)
        vol2 = st.number_input("📦 Volume Collecté C2 (m³)", min_value=0.0, key="vol2")

    st.markdown("<b>🏭 DÉCHARGE C2</b>", unsafe_allow_html=True)
    d2a, d2b = st.columns(2)
    with d2a:
        h_ent2 = st.text_input("⏰ Entrée Décharge 2", value="13:30")
        if st.button("📍 ENR. ENTRÉE DÉCHARGE (C2)"): 
            enregistrer_point_sql(st.session_state.tournee_id, "arrivee_decharge", "Entrée Déch 2", 2)
    with d2b:
        h_sor2 = st.text_input("⏰ Sortie Décharge 2", value="14:00")
        if st.button("📍 ENR. SORTIE DÉCHARGE (C2)"): 
            enregistrer_point_sql(st.session_state.tournee_id, "sortie_decharge", "Sortie Déch 2", 2)

# ==================== RETOUR FINAL ====================
st.markdown("---")
h_ret_final = st.text_input("🏁 Heure de Retour Final au Dépôt", value="14:45")
if st.button("📍 ENREGISTRER POSITION RETOUR FINAL"): 
    enregistrer_point_sql(st.session_state.tournee_id, "retour_depot", "Fin de journée", 2 if st.session_state.show_c2 else 1)

if st.button("💾 SAUVEGARDER ET FERMER LA TOURNÉE", type="primary"):
    v2_final = vol2 if st.session_state.show_c2 else 0
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE tournees SET 
            volume_collecte1 = :v1, volume_collecte2 = :v2, 
            volume_m3 = :vt, distance_parcourue_km = :d,
            heure_depot_depart = :h1, heure_retour_depot = :h2,
            statut = 'termine'
            WHERE id = :tid
        """), {
            "v1": vol1, "v2": v2_final, "vt": vol1 + v2_final, "d": dist_km,
            "h1": h_dep1, "h2": h_ret_final, "tid": st.session_state.tournee_id
        })
        conn.commit()
    st.balloons()
    st.success(f"✅ Tournée terminée ! Volume total : {vol1 + v2_final} m³")

# ==================== CARTE ====================
if st.session_state.points_gps:
    st.markdown("### 🗺️ ITINÉRAIRE RÉEL")
    df = pd.DataFrame(st.session_state.points_gps)
    fig = px.scatter_mapbox(df, lat="lat", lon="lon", color="col", zoom=13, height=500,
                            color_continuous_scale=["green", "orange"])
    if len(df) > 1:
        fig.add_trace(go.Scattermapbox(lat=df["lat"], lon=df["lon"], mode='lines+markers', line=dict(width=4, color='blue')))
    fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)
