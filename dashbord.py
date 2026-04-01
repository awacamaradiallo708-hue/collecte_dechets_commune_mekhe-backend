import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
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

@st.cache_data(ttl=300)
def load_all_data():
    with engine.connect() as conn:
        # 1. On charge les tournées SANS les colonnes d'heures qui posent problème
        q_tournees = text("""
            SELECT id, date_tournee, agent_nom, quartier_nom, 
                   volume_total_m3, distance_km, statut
            FROM tournees 
            WHERE statut = 'termine' 
            ORDER BY date_tournee DESC
        """)
        df_t = pd.read_sql(q_tournees, conn)
        
        # 2. On charge les points GPS
        q_gps = text("""
            SELECT tournee_id, latitude, longitude, type_point, heure_capture 
            FROM points_arret
            ORDER BY heure_capture ASC
        """)
        df_gps = pd.read_sql(q_gps, conn)
        
        # 3. Calcul du temps basé sur les points GPS (Alternative robuste)
        if not df_t.empty and not df_gps.empty:
            df_t['date_tournee'] = pd.to_datetime(df_t['date_tournee'])
            df_t['mois'] = df_t['date_tournee'].dt.month
            
            # On calcule la durée pour chaque tournée en prenant le premier et le dernier point GPS
            durees = []
            for t_id in df_t['id']:
                points = df_gps[df_gps['tournee_id'] == t_id]
                if len(points) >= 2:
                    h_debut = pd.to_datetime(points['heure_capture'].iloc[0])
                    h_fin = pd.to_datetime(points['heure_capture'].iloc[-1])
                    duree_heures = (h_fin - h_debut).total_seconds() / 3600
                    durees.append({'id': t_id, 'duree_h': round(duree_heures, 2)})
                else:
                    durees.append({'id': t_id, 'duree_h': 0.0})
            
            df_durees = pd.DataFrame(durees)
            df_t = df_t.merge(df_durees, on='id', how='left')
        else:
            # Si pas de points GPS, on initialise la colonne à 0
            df_t['duree_h'] = 0.0
            
        return df_t, df_gps

# ==================== FONCTION PDF ====================
def generer_pdf(df_p, titre):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"MAIRIE DE MÉKHÉ - RAPPORT DE COLLECTE", styles['Title']))
    elements.append(Paragraph(f"Période : {titre}", styles['Heading2']))
    elements.append(Spacer(1, 15))
    
    data = [
        ["Indicateur", "Valeur"], 
        ["Volume Total", f"{df_p['volume_total_m3'].sum():.1f} m³"],
        ["Distance Totale", f"{df_p['distance_km'].sum():.1f} km"],
        ["Temps Total Estime", f"{df_p['duree_h'].sum():.1f} h"]
    ]
    t = Table(data, colWidths=[200, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.green), 
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), 
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

# ==================== INTERFACE ====================
st.title("📊 Dashboard Suivi Collecte - Mékhé")

try:
    df, df_gps = load_all_data()

    if df.empty:
        st.info("ℹ️ Aucune donnée de collecte validée pour le moment.")
    else:
        tabs = st.tabs(["📈 Statistiques & Temps", "🗺️ Cartographie GPS", "📄 Rapports PDF", "🔧 Administration"])

        # --- ONGLET 1 : STATS & TEMPS ---
        with tabs[0]:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Volume Global", f"{df['volume_total_m3'].sum():.1f} m³")
            c2.metric("Temps Total", f"{df['duree_h'].sum():.1f} h")
            c3.metric("Moyenne/Tournée", f"{df['duree_h'].mean():.1f} h")
            c4.metric("Distance Cumulée", f"{df['distance_km'].sum():.1f} km")
            
            # Graphique Temps par Jour
            df_jour = df.groupby('date_tournee')['duree_h'].sum().reset_index()
            fig_t = px.line(df_jour, x='date_tournee', y='duree_h', 
                            title="Évolution du temps de collecte journalier", markers=True,
                            labels={'date_tournee': 'Date', 'duree_h': 'Heures'})
            st.plotly_chart(fig_t, use_container_width=True)

        # --- ONGLET 2 : CARTE GPS ---
        with tabs[1]:
            st.subheader("📍 Localisation des points de collecte")
            if not df_gps.empty:
                t_filter = st.selectbox("Filtrer par Tournée (ID)", ["Tous"] + list(df['id'].unique()))
                plot_data = df_gps if t_filter == "Tous" else df_gps[df_gps['tournee_id'] == t_filter]
                
                fig_map = px.scatter_mapbox(plot_data, lat="latitude", lon="longitude", 
                                            color="type_point", hover_name="type_point",
                                            mapbox_style="carto-positron", zoom=13, height=600)
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.warning("⚠️ Aucun point GPS enregistré.")

        # --- ONGLET 3 : PDF ---
        with tabs[2]:
            st.subheader("Générer le rapport")
            m = st.selectbox("Mois", range(1, 13), format_func=lambda x: calendar.month_name[x])
            df_mois = df[df['mois'] == m]
            
            if not df_mois.empty:
                if st.button("🚀 Créer le PDF"):
                    pdf = generer_pdf(df_mois, calendar.month_name[m])
                    st.download_button(f"📥 Télécharger Rapport {calendar.month_name[m]}", pdf, f"Rapport_{m}.pdf", "application/pdf")
            else:
                st.warning("Aucune donnée pour ce mois.")

        # --- ONGLET 4 : ADMIN ---
        with tabs[3]:
            st.subheader("🔧 Correction manuelle")
            sel_id = st.selectbox("ID Tournée", df['id'].unique())
            current_row = df[df['id'] == sel_id].iloc[0]
            
            v_new = st.number_input("Volume (m³)", value=float(current_row['volume_total_m3']))
            d_new = st.number_input("Distance (km)", value=float(current_row['distance_km']))
            
            if st.button("Mettre à jour"):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE tournees SET volume_total_m3 = :v, distance_km = :d WHERE id = :id"), 
                                 {"v": v_new, "d": d_new, "id": int(sel_id)})
                st.success("Modifications enregistrées ! Actualisez la page.")
                st.cache_data.clear()

except Exception as e:
    st.error(f"Une erreur est survenue : {e}")
