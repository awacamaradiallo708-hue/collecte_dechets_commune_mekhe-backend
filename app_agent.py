# ======================= APPLICATION AGENT + GPS FUSION =======================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from sqlalchemy import create_engine, text
from io import BytesIO
import os
from geopy.distance import geodesic

# === Vérifier GPS ===
try:
    from streamlit_js_eval import get_geolocation
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    st.warning("⚠️ streamlit-js-eval non installé. pip install streamlit-js-eval")

# === Configuration page ===
st.set_page_config(page_title="Agent Collecte - Mékhé", page_icon="🗑️", layout="wide")

# === CSS ===
st.markdown("""
<style>
.main-header { background: linear-gradient(135deg,#2E7D32 0%,#1B5E20 100%); padding:1rem; border-radius:10px; color:white; text-align:center; margin-bottom:1rem;}
.collecte-card { background:#e8f5e9; padding:1rem; border-radius:10px; margin-bottom:1rem; border-left:4px solid #4CAF50;}
.collecte2-optional { background:#fef7e0; padding:1rem; border-radius:10px; border-left:4px solid #FF9800; margin-bottom:1rem;}
.gps-active { background:#4CAF50; color:white; padding:0.5rem; border-radius:8px; text-align:center; font-weight:bold; animation:pulse 2s infinite;}
@keyframes pulse {0% {opacity:1;} 50% {opacity:0.7;} 100% {opacity:1;}}
.gps-inactive { background:#f44336; color:white; padding:0.5rem; border-radius:8px; text-align:center; font-weight:bold;}
.gps-precision-high { background:#4CAF50; color:white; padding:0.2rem 0.5rem; border-radius:15px; font-size:0.8rem; display:inline-block;}
.gps-precision-medium { background:#FF9800; color:white; padding:0.2rem 0.5rem; border-radius:15px; font-size:0.8rem; display:inline-block;}
.gps-precision-low { background:#f44336; color:white; padding:0.2rem 0.5rem; border-radius:15px; font-size:0.8rem; display:inline-block;}
.stButton button { width:100%; padding:12px; font-size:16px; font-weight:bold;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🗑️ Agent de Collecte - Suivi de Tournée</h1><p>Commune de Mékhé | GPS Haute Précision | Itinéraire en temps réel</p></div>', unsafe_allow_html=True)

# ==================== BASE DE DONNÉES ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ Configuration base de données manquante")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS ====================
def get_position_exacte():
    if not GPS_AVAILABLE:
        return {"lat": 15.115000, "lon": -16.635000, "accuracy": 100, "error": "Package non installé"}
    try:
        geolocation = get_geolocation()
        if geolocation and 'coords' in geolocation:
            coords = geolocation['coords']
            lat = coords.get('latitude')
            lon = coords.get('longitude')
            accuracy = coords.get('accuracy',100)
            if lat and lon:
                return {"lat":lat,"lon":lon,"accuracy":accuracy,"altitude":coords.get('altitude'),"speed":coords.get('speed'),"heading":coords.get('heading'),"timestamp":geolocation.get('timestamp'),"status":"success"}
            else:
                return {"lat": 15.115000,"lon":-16.635000,"accuracy":100,"status":"no_coords","error":"Coordonnées non disponibles"}
        else:
            return {"lat": 15.115000,"lon":-16.635000,"accuracy":100,"status":"no_data","error":"Aucune donnée GPS"}
    except Exception as e:
        return {"lat": 15.115000,"lon":-16.635000,"accuracy":100,"status":"error","error": str(e)}

def get_precision_label(accuracy):
    if accuracy < 10: return ("🟢 Excellente","gps-precision-high", "Moins de 10 mètres")
    elif accuracy <50: return ("🟡 Bonne","gps-precision-medium", f"{accuracy:.0f} mètres")
    else: return ("🔴 Faible","gps-precision-low", f"{accuracy:.0f} mètres")

def calculer_distance(p1,p2):
    if p1 and p2 and p1.get('lat') and p2.get('lat'):
        try: return geodesic((p1['lat'],p1['lon']),(p2['lat'],p2['lon'])).kilometers
        except: return 0
    return 0

def formater_duree(minutes):
    if minutes<=0: return "0 min"
    h=int(minutes//60); m=int(minutes%60)
    return f"{h}h {m}min" if h>0 else f"{m}min"

def get_quartiers():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id,nom FROM quartiers WHERE actif=true ORDER BY nom")).fetchall()
        return [(r[0],r[1]) for r in res]

def get_equipes():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id,nom FROM equipes WHERE actif=true ORDER BY nom")).fetchall()
        return [(r[0],r[1]) for r in res]

# ==================== SESSION STATE ====================
if 'agent_nom' not in st.session_state: st.session_state.agent_nom=""
if 'tournee_id' not in st.session_state: st.session_state.tournee_id=None
if 'date_tournee' not in st.session_state: st.session_state.date_tournee=date.today()
if 'quartier_nom' not in st.session_state: st.session_state.quartier_nom=""
if 'volume1' not in st.session_state: st.session_state.volume1=0.0
if 'volume2' not in st.session_state: st.session_state.volume2=0.0
if 'points_gps' not in st.session_state: st.session_state.points_gps=[]
if 'gps_actif' not in st.session_state: st.session_state.gps_actif=False
if 'collecte1_validee' not in st.session_state: st.session_state.collecte1_validee=False
if 'collecte2_validee' not in st.session_state: st.session_state.collecte2_validee=False
if 'distance_totale' not in st.session_state: st.session_state.distance_totale=0.0
if 'derniere_position' not in st.session_state: st.session_state.derniere_position=None
if 'temps_debut_tournee' not in st.session_state: st.session_state.temps_debut_tournee=None
if 'precision_moyenne' not in st.session_state: st.session_state.precision_moyenne=0.0

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("👤 Agent de collecte")
    nom_input = st.text_input("Votre nom complet", value=st.session_state.agent_nom, placeholder="Ex: Alioune Diop")
    if nom_input: st.session_state.agent_nom=nom_input; st.success(f"✅ Connecté: {nom_input}")
    
    st.markdown("---")
    st.markdown("### 📍 GPS Haute Précision")
    col1,col2 = st.columns(2)
    with col1:
        if st.button("🎯 ACTIVER GPS"): st.session_state.gps_actif=True; st.info("📱 Autorisez la géolocalisation dans votre navigateur"); st.rerun()
    with col2:
        if st.button("⏸️ DÉSACTIVER"): st.session_state.gps_actif=False
    
    if st.session_state.gps_actif:
        st.markdown('<div class="gps-active">📍 GPS ACTIF</div>', unsafe_allow_html=True)
        pos_actuelle = get_position_exacte()
        if pos_actuelle.get('status')=='success':
            st.metric("Latitude", f"{pos_actuelle['lat']:.6f}")
            st.metric("Longitude", f"{pos_actuelle['lon']:.6f}")
            label, cls, detail = get_precision_label(pos_actuelle['accuracy'])
            st.markdown(f'<span class="{cls}">🎯 Précision: {label} ({detail})</span>', unsafe_allow_html=True)
            if pos_actuelle.get('speed'): st.metric("Vitesse", f"{pos_actuelle['speed']:.1f} km/h")
            if pos_actuelle.get('altitude'): st.metric("Altitude", f"{pos_actuelle['altitude']:.0f} m")
        else:
            st.warning("⚠️ En attente de signal GPS...")
    else:
        st.markdown('<div class="gps-inactive">⚠️ GPS INACTIF</div>', unsafe_allow_html=True)

# ==================== COMMUNE + ÉQUIPE ====================
col1,col2 = st.columns(2)
with col1: st.session_state.date_tournee=st.date_input("📅 Date", value=st.session_state.date_tournee)
with col2:
    quartiers_list=get_quartiers()
    if quartiers_list: st.session_state.quartier_nom=st.selectbox("📍 Quartier",[q[1] for q in quartiers_list])
col1,col2=st.columns(2)
with col1:
    equipes_list=get_equipes()
    if equipes_list: equipe_nom=st.selectbox("👥 Équipe",[e[1] for e in equipes_list])
with col2:
    if st.button("🚀 DÉMARRER LA TOURNÉE"): st.session_state.temps_debut_tournee=datetime.now(); st.success("✅ Tournée démarrée !")

# ==================== COLLECTE 1 ====================
st.markdown('<div class="collecte-card"><h3>Collecte 1 - Obligatoire</h3></div>', unsafe_allow_html=True)
col1,col2=st.columns(2)
with col1: volume1_input = st.number_input("Volume Collecte 1 (m³)", value=st.session_state.volume1, step=0.1)
with col2: collecte1_valider = st.button("✅ Valider Collecte 1")
if collecte1_valider:
    st.session_state.volume1=volume1_input
    st.session_state.collecte1_validee=True
    st.success(f"Collecte 1 validée: {volume1_input} m³")
    # Ajouter point GPS
    if st.session_state.gps_actif:
        pos=get_position_exacte()
        st.session_state.points_gps.append({"type":"collecte1","lat":pos['lat'],"lon":pos['lon'],"timestamp":datetime.now()})
        # Calcul distance
        if st.session_state.derniere_position:
            st.session_state.distance_totale += calculer_distance(st.session_state.derniere_position,pos)
        st.session_state.derniere_position=pos

# ==================== COLLECTE 2 ====================
st.markdown('<div class="collecte2-optional"><h3>Collecte 2 - Optionnelle</h3></div>', unsafe_allow_html=True)
col1,col2=st.columns(2)
with col1: volume2_input = st.number_input("Volume Collecte 2 (m³)", value=st.session_state.volume2, step=0.1)
with col2: collecte2_valider = st.button("✅ Valider Collecte 2")
if collecte2_valider:
    st.session_state.volume2=volume2_input
    st.session_state.collecte2_validee=True
    st.success(f"Collecte 2 validée: {volume2_input} m³")
    # Ajouter point GPS
    if st.session_state.gps_actif:
        pos=get_position_exacte()
        st.session_state.points_gps.append({"type":"collecte2","lat":pos['lat'],"lon":pos['lon'],"timestamp":datetime.now()})
        # Calcul distance
        if st.session_state.derniere_position:
            st.session_state.distance_totale += calculer_distance(st.session_state.derniere_position,pos)
        st.session_state.derniere_position=pos

# ==================== EXPORT / RÉCAP ====================
st.markdown("---")
st.subheader("📊 Récapitulatif de la Tournée")
st.write(f"Agent: {st.session_state.agent_nom}")
st.write(f"Date: {st.session_state.date_tournee}")
st.write(f"Quartier: {st.session_state.quartier_nom}")
st.write(f"Distance parcourue: {st.session_state.distance_totale:.2f} km")
st.write(f"Volume Collecte 1: {st.session_state.volume1} m³ | Collecte 2: {st.session_state.volume2} m³")
st.write(f"Points GPS enregistrés: {len(st.session_state.points_gps)}")

# Carte interactive
if st.session_state.points_gps:
    df_gps=pd.DataFrame(st.session_state.points_gps)
    fig=px.scatter_mapbox(df_gps, lat="lat", lon="lon", color="type", hover_data=["timestamp"], zoom=14, height=400)
    fig.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(fig, use_container_width=True)

# Export Excel
def export_excel():
    df_points=pd.DataFrame(st.session_state.points_gps)
    with BytesIO() as b:
        with pd.ExcelWriter(b, engine='openpyxl') as writer:
            pd.DataFrame([{
                "Agent": st.session_state.agent_nom,
                "Date": st.session_state.date_tournee,
                "Quartier": st.session_state.quartier_nom,
                "Volume1": st.session_state.volume1,
                "Volume2": st.session_state.volume2,
                "Distance_km": st.session_state.distance_totale
            }]).to_excel(writer, index=False, sheet_name="Résumé")
            if not df_points.empty:
                df_points.to_excel(writer, index=False, sheet_name="Points_GPS")
        return b.getvalue()

if st.button("💾 Export Excel"):
    data_bytes=export_excel()
    st.download_button("Télécharger le fichier Excel", data=data_bytes, file_name=f"Tournée_{st.session_state.date_tournee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
