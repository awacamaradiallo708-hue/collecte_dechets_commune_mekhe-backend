import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import os
import io
import calendar

# Imports pour le PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==================== CONFIGURATION ====================
st.set_page_config(page_title="Dashboard Mékhé", page_icon="📊", layout="wide")

DATABASE_URL = st.secrets["DATABASE_URL"] if "DATABASE_URL" in st.secrets else os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# ==================== CHARGEMENT DES DONNÉES ====================

def calculer_duree(h_dep, h_ret):
    """Calcule la durée entre deux chaînes de caractères HH:MM"""
    try:
        fmt = '%H:%M'
        tdelta = datetime.strptime(h_ret, fmt) - datetime.strptime(h_dep, fmt)
        return round(tdelta.seconds / 3600, 2) # Retourne en heures (ex: 2.5h)
    except:
        return 0

@st.cache_data(ttl=300)
def load_all_data():
    with engine.connect() as conn:
        # 1. Données des tournées
        q_tournees = text("""
            SELECT id, date_tournee, agent_nom, quartier_nom, 
                   volume_total_m3, distance_km, statut,
                   heure_depot_depart, heure_retour_depot
            FROM tournees WHERE statut = 'termine' ORDER BY date_tournee DESC
        """)
        df_t = pd.read_sql(q_tournees, conn)
        
        # 2. Données GPS (Points d'arrêt)
        q_gps = text("SELECT tournee_id, latitude, longitude, type_point, heure_capture FROM points_arret")
        df_gps = pd.read_sql(q_gps, conn)
        
        if not df_t.empty:
            df_t['date_tournee'] = pd.to_datetime(df_t['date_tournee'])
            df_t['mois'] = df_t['date_tournee'].dt.month
            # Calcul du temps passé (en heures)
            df_t['duree_h'] = df_t.apply(lambda x: calculer_duree(x['heure_depot_depart'], x['heure_retour_depot']), axis=1)
            
        return df_t, df_gps

# ==================== FONCTION PDF ====================
def generer_pdf(df_p, titre):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"RAPPORT DE COLLECTE - MÉKHÉ", styles['Title']))
    elements.append(Paragraph(f"Période : {titre}", styles['Heading2']))
    
    data = [["Indicateur", "Valeur"], 
            ["Volume Total", f"{df_p['volume_total_m3'].sum():.1f} m³"],
            ["Temps Total", f"{df_p['duree_h'].sum():.1f} h"]]
    t = Table(data, colWidths=[200, 150])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.green), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('GRID', (0,0), (-1,-1), 1, colors.black)]))
    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

# ==================== INTERFACE ====================
st.title("📊 Dashboard Suivi Collecte - Mékhé")

try:
    df, df_gps = load_all_data()

    if df.empty:
        st.info("En attente de données...")
    else:
        tabs = st.tabs(["📈 Statistiques & Temps", "🗺️ Cartographie GPS", "📄 Rapports PDF", "🔧 Administration"])

        # --- ONGLET 1 : STATS & TEMPS ---
        with tabs[0]:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Volume Global", f"{df['volume_total_m3'].sum():.1f} m³")
            c2.metric("Temps Total", f"{df['duree_h'].sum():.1f} h")
            c3.metric("Moyenne/Tournée", f"{df['duree_h'].mean():.1f} h")
            c4.metric("Distance", f"{df['distance_km'].sum():.1f} km")
            
            # Graphique Temps par Jour
            df_jour = df.groupby('date_tournee')['duree_h'].sum().reset_index()
            fig_t = px.line(df_jour, x='date_tournee', y='duree_h', title="Temps de collecte cumulé par jour", markers=True)
            st.plotly_chart(fig_t, use_container_width=True)

        # --- ONGLET 2 : CARTE GPS (GÉOMATIQUE) ---
        with tabs[1]:
            st.subheader("📍 Localisation des points de collecte")
            if not df_gps.empty:
                # Filtrer par tournée si besoin
                t_filter = st.selectbox("Filtrer par Tournée (ID)", ["Tous"] + list(df['id'].unique()))
                
                plot_data = df_gps if t_filter == "Tous" else df_gps[df_gps['tournee_id'] == t_filter]
                
                fig_map = px.scatter_mapbox(plot_data, lat="latitude", lon="longitude", 
                                            color="type_point", hover_name="type_point",
                                            mapbox_style="carto-positron", zoom=13, height=600)
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.warning("Aucun point GPS enregistré.")

        # --- ONGLET 3 : PDF ---
        with tabs[2]:
            st.subheader("Générer le rapport")
            m = st.selectbox("Mois", range(1, 13), format_func=lambda x: calendar.month_name[x])
            if st.button("🚀 Créer PDF"):
                pdf = generer_pdf(df[df['mois'] == m], calendar.month_name[m])
                st.download_button("📥 Télécharger", pdf, f"Rapport_{m}.pdf")

        # --- ONGLET 4 : ADMIN ---
        with tabs[3]:
            st.subheader("Correction")
            sel_id = st.selectbox("ID Tournée", df['id'].unique())
            v_new = st.number_input("Volume (m³)", value=float(df[df['id']==sel_id]['volume_total_m3'].iloc[0]))
            if st.button("Mettre à jour"):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE tournees SET volume_total_m3 = :v WHERE id = :id"), {"v": v_new, "id": int(sel_id)})
                st.cache_data.clear()
                st.success("Corrigé !")

except Exception as e:
    st.error(f"Erreur : {e}")
