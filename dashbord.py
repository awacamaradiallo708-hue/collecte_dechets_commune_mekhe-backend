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
st.set_page_config(page_title="Dashboard Collecte Mékhé", page_icon="📊", layout="wide")

# Connexion Base de Données (Secrets Streamlit)
DATABASE_URL = st.secrets["DATABASE_URL"] if "DATABASE_URL" in st.secrets else os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# --- Fonction de calcul de durée (Heures) ---
def calculer_duree_h(h_dep, h_arr):
    try:
        if not h_dep or not h_arr: return 0
        fmt = '%H:%M'
        t_dep = datetime.strptime(str(h_dep)[:5], fmt)
        t_arr = datetime.strptime(str(h_arr)[:5], fmt)
        diff = t_arr - t_dep
        return round(diff.total_seconds() / 3600, 2)
    except:
        return 0

# ==================== CHARGEMENT DES DONNÉES ====================
@st.cache_data(ttl=60)
def load_all_data():
    with engine.connect() as conn:
        # 1. Tournées (Colonnes synchronisées avec votre base)
        query_t = text("""
            SELECT id, date_tournee, agent_nom, quartier_nom, equipe_nom,
                   volume_total_m3, distance_km, statut,
                   heure_depart_depot, heure_arrivee_depot
            FROM tournees 
            WHERE statut = 'termine' 
            ORDER BY date_tournee DESC
        """)
        df_t = pd.read_sql(query_t, conn)
        
        # 2. Points GPS
        query_gps = text("SELECT tournee_id, latitude, longitude, type_point FROM points_arret")
        df_gps = pd.read_sql(query_gps, conn)
        
        if not df_t.empty:
            df_t['date_tournee'] = pd.to_datetime(df_t['date_tournee'])
            df_t['semaine'] = df_t['date_tournee'].dt.isocalendar().week
            df_t['mois'] = df_t['date_tournee'].dt.month
            df_t['annee'] = df_t['date_tournee'].dt.year
            df_t['duree_h'] = df_t.apply(lambda x: calculer_duree_h(x['heure_depart_depot'], x['heure_arrivee_depot']), axis=1)
            
        return df_t, df_gps

# ==================== GÉNÉRATION DU RAPPORT PDF ====================
def generer_pdf_officiel(df_periode, titre_periode):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Entête
    elements.append(Paragraph("REPUBLIQUE DU SENEGAL", styles['Normal']))
    elements.append(Paragraph("COMMUNE DE MÉKHÉ", styles['Heading2']))
    elements.append(Paragraph("SERVICE DE GESTION DES DÉCHETS", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"RAPPORT SYNTHETIQUE DE COLLECTE", styles['Title']))
    elements.append(Paragraph(f"Période : {titre_periode}", styles['Heading2']))
    elements.append(Spacer(1, 20))

    # Tableau 1 : Indicateurs Clés
    elements.append(Paragraph("1. Indicateurs de performance", styles['Heading3']))
    stats_data = [
        ["Indicateur", "Valeur Totale"],
        ["Volume Collecté (m³)", f"{df_periode['volume_total_m3'].sum():.2f}"],
        ["Distance Parcourue (km)", f"{df_periode['distance_km'].sum():.2f}"],
        ["Temps de Service (h)", f"{df_periode['duree_h'].sum():.2f}"],
        ["Nombre de Tournées", str(len(df_periode))]
    ]
    t1 = Table(stats_data, colWidths=[200, 150])
    t1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.darkgreen), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('GRID', (0,0), (-1,-1), 1, colors.black)]))
    elements.append(t1)
    elements.append(Spacer(1, 20))

    # Tableau 2 : Répartition par Quartier (Statistiques spatiales)
    elements.append(Paragraph("2. Répartition par quartier", styles['Heading3']))
    df_q = df_periode.groupby('quartier_nom')['volume_total_m3'].sum().reset_index()
    q_data = [["Quartier", "Volume (m³)"]]
    for _, row in df_q.iterrows():
        q_data.append([row['quartier_nom'], f"{row['volume_total_m3']:.2f}"])
    
    t2 = Table(q_data, colWidths=[200, 150])
    t2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(t2)

    doc.build(elements)
    return buffer.getvalue()

# ==================== INTERFACE STREAMLIT ====================
st.markdown("<h1 style='text-align: center; color: #1e5631;'>📊 Système de Suivi des Déchets - Mékhé</h1>", unsafe_allow_html=True)

try:
    df, df_gps = load_all_data()

    if df.empty:
        st.info("ℹ️ Aucune donnée de collecte disponible.")
    else:
        tabs = st.tabs(["📈 Statistiques & Temps", "📍 Cartographie GPS", "📄 Rapports PDF", "🔧 Administration"])

        # --- ONGLET 1 : STATS ---
        with tabs[0]:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Volume Total", f"{df['volume_total_m3'].sum():.1f} m³")
            c2.metric("Temps Collecte", f"{df['duree_h'].sum():.1f} h")
            c3.metric("Distance", f"{df['distance_km'].sum():.1f} km")
            c4.metric("Tournées", len(df))

            st.subheader("⏱️ Analyse du temps de collecte par jour")
            fig_time = px.line(df.groupby('date_tournee')['duree_h'].sum().reset_index(), 
                              x='date_tournee', y='duree_h', markers=True, title="Heures de travail cumulées")
            st.plotly_chart(fig_time, use_container_width=True)

        # --- ONGLET 2 : GPS ---
        with tabs[1]:
            st.subheader("🗺️ Localisation des points (GPS)")
            if not df_gps.empty:
                fig_map = px.scatter_mapbox(df_gps, lat="latitude", lon="longitude", 
                                            color="type_point", hover_name="type_point",
                                            mapbox_style="carto-positron", zoom=13, height=600)
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.warning("Aucun point GPS enregistré.")

        # --- ONGLET 3 : RAPPORTS (Hebdo & Mensuel) ---
        with tabs[2]:
            st.subheader("📄 Génération de rapports officiels")
            type_r = st.radio("Type de rapport", ["Hebdomadaire", "Mensuel"], horizontal=True)
            
            if type_r == "Hebdomadaire":
                sem = st.selectbox("Semaine n°", sorted(df['semaine'].unique(), reverse=True))
                df_f = df[df['semaine'] == sem]
                titre = f"Semaine {sem} - {datetime.now().year}"
            else:
                m = st.selectbox("Mois", range(1, 13), format_func=lambda x: calendar.month_name[x])
                df_f = df[df['mois'] == m]
                titre = f"Mois de {calendar.month_name[m]}"

            if st.button("🚀 Générer le PDF"):
                if not df_f.empty:
                    pdf = generer_pdf_officiel(df_f, titre)
                    st.download_button(f"📥 Télécharger Rapport {titre}", pdf, f"Rapport_{titre}.pdf", "application/pdf")
                else:
                    st.error("Aucune donnée pour cette période.")

        # --- ONGLET 4 : ADMIN ---
        with tabs[3]:
            st.subheader("🔧 Correction")
            sel_id = st.selectbox("ID Tournée", df['id'].unique())
            v_val = st.number_input("Volume (m³)", value=float(df[df['id']==sel_id]['volume_total_m3'].iloc[0]))
            if st.button("Mettre à jour"):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE tournees SET volume_total_m3 = :v WHERE id = :id"), {"v": v_val, "id": int(sel_id)})
                st.success("Modifié !")
                st.cache_data.clear()

except Exception as e:
    st.error(f"❌ Erreur : {e}")
