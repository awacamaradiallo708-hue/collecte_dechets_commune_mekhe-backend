import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
from sqlalchemy import create_engine, text
import os
from streamlit_js_eval import get_geolocation
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Mékhé Propre - Système Agent", layout="wide")

# --- STYLE CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .main-header { background: #1b5e20; padding: 20px; color: white; text-align: center; border-radius: 10px; margin-bottom: 20px; }
    .stButton button { height: 70px; font-size: 20px !important; border-radius: 12px !important; font-weight: bold !important; margin-bottom: 10px; }
    .card { background: #f1f8e9; padding: 20px; border-radius: 15px; border-left: 10px solid #43a047; margin-bottom: 20px; }
    .success-msg { color: #2e7d32; font-weight: bold; font-size: 18px; padding: 15px; background: #e8f5e9; border-radius: 10px; border: 1px solid #2e7d32; margin-bottom: 20px; }
    label { font-size: 18px !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION BASE DE DONNÉES ---
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# --- INITIALISATION SÉCURISÉE DU SESSION STATE ---
# (C'est ici que nous corrigeons l'erreur AttributeError)
if 'tid' not in st.session_state: st.session_state.tid = None
if 'gps_data' not in st.session_state: st.session_state.gps_data = []
if 'last_action' not in st.session_state: st.session_state.last_action = ""
if 'show_c2' not in st.session_state: st.session_state.show_c2 = False

# --- FONCTION DE CAPTURE GPS ---
def enregistrer_etape(type_p, desc, col_num, color="green"):
    if not st.session_state.tid:
        st.error("❌ Vous devez d'abord cliquer sur 'DÉMARRER LA JOURNÉE'")
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
            
            # Enregistrement pour l'affichage local
            st.session_state.gps_data.append({
                "Heure": datetime.now().strftime("%H:%M"),
                "Action": desc,
                "lat": lat, "lon": lon,
                "Couleur": color,
                "Tour": f"Collecte {col_num}" if col_num > 0 else "Signalement"
            })
            st.session_state.last_action = f"✅ Enregistré avec succès : {desc} ({datetime.now().strftime('%H:%M')})"
            st.toast(st.session_state.last_action)
        except Exception as e:
            st.error(f"Erreur BDD : {e}")
    else:
        st.warning("⚠️ GPS introuvable. Activez la localisation sur votre téléphone.")

# --- INTERFACE UTILISATEUR ---
st.markdown('<div class="main-header"><h1>♻️ AGENT COLLECTE - MÉKHÉ</h1></div>', unsafe_allow_html=True)

# Affichage du message de confirmation pour l'agent
if st.session_state.last_action:
    st.markdown(f'<div class="success-msg">{st.session_state.last_action}</div>', unsafe_allow_html=True)

# 1. PARAMÈTRES DE DÉPART
with st.container():
    c1, c2 = st.columns(2)
    with c1:
        agent = st.text_input("👤 Nom de l'Agent", value="Awa")
        # Liste de vos quartiers exacts
        quartiers_mekhe = ["Ngaye Diagne", "Ngaye Djité", "HLM", "Mbambara", "Lebou Est", "Lebou Ouest", "Ndiob"]
        q_sel = st.selectbox("🏘️ Quartier de la tournée", quartiers_mekhe)
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
        st.success(f"Tournée n°{st.session_state.tid} initialisée !")

# 2. SIGNALEMENT D'URGENCE
st.markdown("---")
if st.button("🚨 SIGNALER UN DÉPÔT SAUVAGE ICI"):
    enregistrer_etape("signalement", "Dépôt Sauvage", 0, color="red")

# 3. COLLECTE N°1
st.markdown('<div class="card">🚛 <b>TOURNÉE N°1 (C1)</b></div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🚩 Départ Dépôt (C1)"): 
        enregistrer_etape("depart", "Départ Dépôt C1", 1)
with col2:
    if st.button("🗑️ Début Ramassage (C1)"): 
        enregistrer_etape("collecte", "Début Ramassage C1", 1)
with col3:
    if st.button("🏭 Arrivée Décharge (C1)"): 
        enregistrer_etape("decharge", "Arrivée Décharge C1", 1)

vol1 = st.number_input("📦 Volume C1 collecté (m³)", min_value=0.0, key="v1")

# 4. COLLECTE N°2 (OPTIONNELLE)
st.write("---")
# Utilisation de checkbox pour activer/désactiver le tour 2
st.session_state.show_c2 = st.checkbox("➕ Faire un deuxième tour (C2)", value=st.session_state.show_c2)

if st.session_state.show_c2:
    st.markdown('<div class="card" style="border-left-color: #FF9800;">🚛 <b>TOURNÉE N°2 (C2)</b></div>', unsafe_allow_html=True)
    col4, col5 = st.columns(2)
    with col4:
        if st.button("🗑️ Début Ramassage (C2)"): 
            enregistrer_etape("collecte", "Début Ramassage C2", 2)
    with col5:
        if st.button("🏭 Arrivée Décharge (C2)"): 
            enregistrer_etape("decharge", "Arrivée Décharge C2", 2)
    vol2 = st.number_input("📦 Volume C2 collecté (m³)", min_value=0.0, key="v2")
else:
    vol2 = 0.0

# 5. CLÔTURE ET EXPORT
st.write("---")
if st.button("💾 CLÔTURER LA JOURNÉE & ENREGISTRER", type="primary"):
    total_m3 = vol1 + vol2
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE tournees SET volume_c1=:v1, volume_c2=:v2, volume_total_m3=:vt, 
                distance_km=:km, statut='termine' WHERE id=:tid
            """), {"v1": vol1, "v2": vol2, "vt": total_m3, "km": dist_km, "tid": st.session_state.tid})
            conn.commit()
        
        # Génération du fichier Excel pour le téléphone
        df_recap = pd.DataFrame([{
            "Date": date.today(), "Agent": agent, "Equipe": e_sel, "Quartier": q_sel,
            "Volume Total": total_m3, "KM": dist_km
        }])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_recap.to_excel(writer, index=False)
        
        st.download_button(label="📥 Télécharger le Rapport Excel", 
                           data=output.getvalue(), 
                           file_name=f"Rapport_{agent}_{date.today()}.xlsx",
                           mime="application/vnd.ms-excel")
        
        st.balloons()
        st.success(f"Données sauvegardées ! Total collecté : {total_m3} m³")
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde finale : {e}")

# 6. CARTE INTERACTIVE
if st.session_state.gps_data:
    st.markdown("### 🗺️ VOTRE TRAJET EN TEMPS RÉEL")
    df_map = pd.DataFrame(st.session_state.gps_data)
    
    # Carte avec distinction de couleur (Vert=Normal, Rouge=Signalement)
    fig = px.scatter_mapbox(df_map, lat="lat", lon="lon", color="Couleur",
                            color_discrete_map={"green": "#2e7d32", "red": "#f44336"},
                            hover_name="Action", hover_data=["Heure", "Tour"],
                            zoom=14, height=500)
    
    fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)
    
    # Tableau récapitulatif
    st.write("📋 Historique des points :")
    st.dataframe(df_map[["Heure", "Action", "Tour"]], use_container_width=True)
