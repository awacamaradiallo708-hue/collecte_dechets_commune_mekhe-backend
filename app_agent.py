import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_js_eval import get_geolocation
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from math import radians, cos, sin, sqrt, atan2

# ========================
# CONFIG
# ========================
API_URL = "https://neo.tech/api"  # à adapter

st.set_page_config(layout="wide")
st.title("🚛 Suivi de collecte des déchets")

# ========================
# SESSION STATE
# ========================
if "gps_actif" not in st.session_state:
    st.session_state.gps_actif = False

if "points_tracking" not in st.session_state:
    st.session_state.points_tracking = []

if "points_gps" not in st.session_state:
    st.session_state.points_gps = []

if "derniere_position" not in st.session_state:
    st.session_state.derniere_position = None

if "distance_totale" not in st.session_state:
    st.session_state.distance_totale = 0

# ========================
# AUTO REFRESH
# ========================
st_autorefresh(interval=5000, key="live")

# ========================
# GPS
# ========================
def get_position():
    geo = get_geolocation()
    if geo:
        return {
            "status": "success",
            "lat": geo['coords']['latitude'],
            "lon": geo['coords']['longitude'],
            "accuracy": geo['coords']['accuracy'],
            "speed": geo['coords'].get('speed', 0)
        }
    return {"status": "error"}

# ========================
# DISTANCE (Haversine)
# ========================
def calculer_distance(p1, p2):
    R = 6371000
    lat1, lon1 = radians(p1["lat"]), radians(p1["lon"])
    lat2, lon2 = radians(p2["lat"]), radians(p2["lon"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

# ========================
# STATUT
# ========================
def detecter_statut(vitesse):
    if vitesse is None:
        return "inconnu"
    elif vitesse < 2:
        return "collecte"
    elif vitesse > 15:
        return "transport"
    else:
        return "pause"

# ========================
# TRACKING AUTOMATIQUE
# ========================
def tracking_automatique():
    if not st.session_state.gps_actif:
        return

    pos = get_position()

    if pos["status"] != "success":
        return

    distance = 0

    if st.session_state.derniere_position:
        distance = calculer_distance(st.session_state.derniere_position, pos)
        st.session_state.distance_totale += distance

    statut = detecter_statut(pos.get("speed", 0))

    point = {
        "latitude": pos["lat"],
        "longitude": pos["lon"],
        "heure": datetime.now().strftime("%H:%M:%S"),
        "distance": distance,
        "statut": statut
    }

    st.session_state.points_tracking.append(point)
    st.session_state.derniere_position = pos

    # Envoi base
    try:
        requests.post(API_URL, json=point)
    except:
        pass

# ========================
# BOUTONS
# ========================
col1, col2 = st.columns(2)

with col1:
    if st.button("▶️ Démarrer tournée"):
        st.session_state.gps_actif = True

with col2:
    if st.button("⏹️ Arrêter tournée"):
        st.session_state.gps_actif = False

# ========================
# TRACKING
# ========================
if st.session_state.gps_actif:
    tracking_automatique()

# ========================
# FUSION DES POINTS
# ========================
all_points = st.session_state.points_gps + st.session_state.points_tracking

# ========================
# CARTE
# ========================
if len(all_points) > 1:
    lats = [p["latitude"] for p in all_points]
    lons = [p["longitude"] for p in all_points]

    fig = go.Figure()

    fig.add_trace(go.Scattermapbox(
        lat=lats,
        lon=lons,
        mode='lines+markers',
        marker=dict(size=6),
        line=dict(width=4),
        name="Trajet"
    ))

    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=13,
        mapbox_center={"lat": lats[0], "lon": lons[0]},
        height=600
    )

    st.plotly_chart(fig)

# ========================
# STATS
# ========================
st.subheader("📊 Statistiques")

st.metric("Distance totale (m)", round(st.session_state.distance_totale, 2))
st.metric("Points enregistrés", len(all_points))

# ========================
# PDF
# ========================
def generer_pdf():
    doc = SimpleDocTemplate("rapport.pdf")
    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("Rapport de collecte", styles['Title']))
    elements.append(Paragraph(f"Distance : {round(st.session_state.distance_totale,2)} m", styles['Normal']))
    elements.append(Paragraph(f"Points : {len(all_points)}", styles['Normal']))

    doc.build(elements)

# ========================
# EXPORT
# ========================
if st.button("📄 Générer rapport PDF"):
    generer_pdf()
    st.success("Rapport généré !")
