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

# ==================== CHARGEMENT DES DONNÉES (CORRIGÉ) ====================
@st.cache_data(ttl=300)
def load_all_data():
    with engine.connect() as conn:
        # On lie la table tournées avec les noms des quartiers et équipes
        query = text("""
            SELECT 
                t.id, 
                t.date_tournee, 
                t.agent_nom, 
                q.nom as quartier_nom, 
                e.nom as equipe_nom,
                t.volume_total_m3, 
                t.distance_km, 
                t.statut
            FROM tournees t
            LEFT JOIN quartiers q ON t.quartier_id = q.id
            LEFT JOIN equipes e ON t.equipe_id = e.id
            WHERE t.statut = 'termine'
            ORDER BY t.date_tournee DESC
        """)
        df = pd.read_sql(query, conn)
        
        if not df.empty:
            df['date_tournee'] = pd.to_datetime(df['date_tournee'])
            df['semaine'] = df['date_tournee'].dt.isocalendar().week
            df['mois'] = df['date_tournee'].dt.month
            df['annee'] = df['date_tournee'].dt.year
        return df

# ==================== FONCTION PDF ====================
def generer_pdf(df_periode, titre_periode):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"COMMUNE DE MÉKHÉ - RAPPORT DE COLLECTE", styles['Title']))
    elements.append(Paragraph(f"Période : {titre_periode}", styles['Heading2']))
    elements.append(Spacer(1, 20))

    # Tableau de synthèse
    stats = [
        ["Indicateur", "Valeur"],
        ["Volume Total Collecté", f"{df_periode['volume_total_m3'].sum():.2f} m³"],
        ["Distance Totale", f"{df_periode['distance_km'].sum():.2f} km"],
        ["Nombre de Tournées", str(len(df_periode))]
    ]
    t = Table(stats, colWidths=[200, 150])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.green), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('GRID', (0,0), (-1,-1), 1, colors.black)]))
    elements.append(t)
    elements.append(Spacer(1, 25))

    # Tableau détaillé
    data_detail = [["Date", "Quartier", "Agent", "m³"]]
    for _, row in df_periode.iterrows():
        data_detail.append([row['date_tournee'].strftime('%d/%m'), row['quartier_nom'], row['agent_nom'], row['volume_total_m3']])
    
    table_d = Table(data_detail, colWidths=[70, 130, 130, 70])
    table_d.setStyle(TableStyle([('FONTSIZE', (0,0), (-1,-1), 9), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
    elements.append(table_d)

    doc.build(elements)
    return buffer.getvalue()

# ==================== INTERFACE ====================
st.title("📊 Suivi de la Collecte - Mairie de Mékhé")

try:
    df = load_all_data()

    if df.empty:
        st.info("ℹ️ Aucune donnée de collecte terminée pour le moment.")
    else:
        tabs = st.tabs(["📈 Analyse", "📄 Export PDF", "🔧 Administration"])

        # --- ONGLET ANALYSE ---
        with tabs[0]:
            c1, c2, c3 = st.columns(3)
            c1.metric("Volume Global", f"{df['volume_total_m3'].sum():.1f} m³")
            c2.metric("Distance Cumulée", f"{df['distance_km'].sum():.1f} km")
            c3.metric("Tournées", len(df))
            
            fig = px.bar(df.groupby('quartier_nom')['volume_total_m3'].sum().reset_index(), 
                         x='quartier_nom', y='volume_total_m3', title="Performance par Quartier", 
                         labels={'quartier_nom': 'Quartier', 'volume_total_m3': 'Volume (m³)'},
                         color_discrete_sequence=['#2E8B57'])
            st.plotly_chart(fig, use_container_width=True)

        # --- ONGLET PDF ---
        with tabs[1]:
            st.subheader("Générer un rapport officiel")
            choix = st.selectbox("Choisir le mois", range(1, 13), format_func=lambda x: calendar.month_name[x])
            df_mois = df[df['mois'] == choix]
            
            if not df_mois.empty:
                if st.button("Préparer le rapport PDF"):
                    pdf = generer_pdf(df_mois, calendar.month_name[choix])
                    st.download_button(f"📥 Télécharger Rapport {calendar.month_name[choix]}", pdf, f"Rapport_Mekhe_{choix}.pdf", "application/pdf")
            else:
                st.write("Aucune donnée pour ce mois.")

        # --- ONGLET ADMIN ---
        with tabs[2]:
            st.subheader("🔧 Correction d'une erreur de saisie")
            selected_id = st.selectbox("Sélectionner la tournée (ID)", df['id'].unique())
            
            col_v, col_d = st.columns(2)
            v_val = col_v.number_input("Volume correct (m³)", step=0.1)
            d_val = col_d.number_input("Distance correcte (km)", step=0.1)
            
            if st.button("Mettre à jour la base de données"):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE tournees SET volume_total_m3 = :v, distance_km = :d WHERE id = :id"),
                                 {"v": v_val, "d": d_val, "id": int(selected_id)})
                st.success("Données corrigées avec succès !")
                st.cache_data.clear()

except Exception as e:
    st.error("❌ Erreur technique lors de la lecture des données.")
    st.info("Vérifiez que la table 'tournees' contient bien les colonnes 'quartier_id' et 'equipe_id' pour faire la liaison avec vos nouvelles tables.")
