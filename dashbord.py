import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import io
import calendar

# Imports PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==================== CONFIGURATION ====================
st.set_page_config(page_title="Dashboard Mékhé", layout="wide")
DATABASE_URL = st.secrets["DATABASE_URL"] if "DATABASE_URL" in st.secrets else os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def calculer_duree(h_dep, h_arr):
    try:
        fmt = '%H:%M'
        d = datetime.strptime(str(h_arr)[:5], fmt) - datetime.strptime(str(h_dep)[:5], fmt)
        return round(d.total_seconds() / 3600, 2)
    except: return 0

# ==================== CHARGEMENT DES DONNÉES ====================
@st.cache_data(ttl=60)
def load_all_data():
    with engine.connect() as conn:
        df_t = pd.read_sql(text("""
            SELECT id, date_tournee, agent_nom, quartier_nom, volume_total_m3, 
                   distance_km, heure_depart_depot, heure_arrivee_depot 
            FROM tournees WHERE statut = 'termine'
        """), conn)
        
        df_gps = pd.read_sql(text("SELECT * FROM points_arret"), conn)
        
        if not df_t.empty:
            df_t['date_tournee'] = pd.to_datetime(df_t['date_tournee'])
            df_t['semaine'] = df_t['date_tournee'].dt.isocalendar().week
            df_t['mois'] = df_t['date_tournee'].dt.month
            df_t['duree_h'] = df_t.apply(lambda x: calculer_duree(x['heure_depart_depot'], x['heure_arrivee_depot']), axis=1)
        return df_t, df_gps

# ==================== FONCTION PDF ====================
def generer_pdf(df_p, titre):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"MAIRIE DE MÉKHÉ - RAPPORT DE COLLECTE", styles['Title']))
    elements.append(Paragraph(f"Période : {titre}", styles['Heading2']))
    
    data = [["Indicateur", "Valeur Totale"],
            ["Volume (m³)", f"{df_p['volume_total_m3'].sum():.1f}"],
            ["Temps (h)", f"{df_p['duree_h'].sum():.1f}"],
            ["Nombre de Tournées", str(len(df_p))]]
    
    t = Table(data, colWidths=[200, 150])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.darkgreen), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('GRID', (0,0), (-1,-1), 1, colors.black)]))
    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

# ==================== INTERFACE ====================
st.title("📊 Suivi de la Collecte - Mairie de Mékhé")

try:
    df, df_gps = load_all_data()
    tabs = st.tabs(["📈 Analyse & Temps", "📍 Carte GPS", "📄 Rapports PDF", "🔧 Admin"])

    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Volume Total", f"{df['volume_total_m3'].sum():.1f} m³")
        c2.metric("Temps Total", f"{df['duree_h'].sum():.1f} h")
        c3.metric("Distance", f"{df['distance_km'].sum():.1f} km")
        
        fig = px.bar(df.groupby('quartier_nom')['volume_total_m3'].sum().reset_index(), 
                     x='quartier_nom', y='volume_total_m3', title="Volume par Quartier", color_discrete_sequence=['#2E8B57'])
        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        st.subheader("📍 Points de passage des agents")
        if not df_gps.empty:
            fig_map = px.scatter_mapbox(df_gps, lat="latitude", lon="longitude", color="type_point", 
                                        hover_data=["heure_passage"], mapbox_style="carto-positron", zoom=13, height=500)
            st.plotly_chart(fig_map, use_container_width=True)

    with tabs[2]:
        st.subheader("Exporter en PDF")
        type_r = st.radio("Période", ["Hebdomadaire", "Mensuel"], horizontal=True)
        if type_r == "Hebdomadaire":
            val = st.selectbox("Semaine", sorted(df['semaine'].unique(), reverse=True))
            df_f = df[df['semaine'] == val]
        else:
            val = st.selectbox("Mois", range(1,13), format_func=lambda x: calendar.month_name[x])
            df_f = df[df['mois'] == val]
            
        if st.button("🚀 Créer le PDF"):
            pdf = generer_pdf(df_f, f"{type_r} {val}")
            st.download_button("📥 Télécharger", pdf, "Rapport.pdf")

    with tabs[3]:
        st.subheader("🔧 Correction")
        sel_id = st.selectbox("Tournée ID", df['id'].unique())
        new_v = st.number_input("Nouveau Volume", value=float(df[df['id']==sel_id]['volume_total_m3'].iloc[0]))
        if st.button("Mettre à jour"):
            with engine.begin() as conn:
                conn.execute(text("UPDATE tournees SET volume_total_m3 = :v WHERE id = :id"), {"v": new_v, "id": int(sel_id)})
            st.cache_data.clear()
            st.success("Donnée corrigée !")

except Exception as e:
    st.error(f"Erreur : {e}")
