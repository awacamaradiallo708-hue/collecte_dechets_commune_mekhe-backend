import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from sqlalchemy import create_engine, text
import os
import io
import calendar

# Imports pour la génération PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==================== CONFIGURATION ====================
st.set_page_config(page_title="Dashboard Collecte Mékhé", page_icon="📊", layout="wide")

# Connexion Base de Données
DATABASE_URL = st.secrets["DATABASE_URL"] if "DATABASE_URL" in st.secrets else os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# ==================== CHARGEMENT DES DONNÉES ====================
@st.cache_data(ttl=300)
def load_all_data():
    with engine.connect() as conn:
        # Requête directe sur la table tournees
        query = text("""
            SELECT 
                id, date_tournee, agent_nom, quartier_nom, equipe_nom,
                volume_total_m3, distance_km, statut
            FROM tournees 
            WHERE statut = 'termine'
            ORDER BY date_tournee DESC
        """)
        df = pd.read_sql(query, conn)
        
        if not df.empty:
            df['date_tournee'] = pd.to_datetime(df['date_tournee'])
            df['semaine'] = df['date_tournee'].dt.isocalendar().week
            df['mois'] = df['date_tournee'].dt.month
            df['annee'] = df['date_tournee'].dt.year
        return df

# ==================== FONCTION GÉNÉRATION PDF ====================
def generer_pdf(df_periode, titre_periode):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Titre du document
    elements.append(Paragraph(f"MAIRIE DE MÉKHÉ - RAPPORT DE COLLECTE", styles['Title']))
    elements.append(Paragraph(f"Période : {titre_periode}", styles['Heading2']))
    elements.append(Spacer(1, 20))

    # Tableau de synthèse (Metrics)
    stats = [
        ["Indicateur", "Valeur"],
        ["Volume Total Collecté", f"{df_periode['volume_total_m3'].sum():.2f} m³"],
        ["Distance Totale Parcourue", f"{df_periode['distance_km'].sum():.2f} km"],
        ["Nombre de Tournées", str(len(df_periode))]
    ]
    t_stats = Table(stats, colWidths=[200, 150])
    t_stats.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 11)
    ]))
    elements.append(t_stats)
    elements.append(Spacer(1, 30))

    # Tableau détaillé
    elements.append(Paragraph("Détails des collectes :", styles['Heading3']))
    data_detail = [["Date", "Quartier", "Agent", "Volume (m³)"]]
    for _, row in df_periode.iterrows():
        data_detail.append([
            row['date_tournee'].strftime('%d/%m/%Y'), 
            row['quartier_nom'], 
            row['agent_nom'], 
            str(row['volume_total_m3'])
        ])
    
    t_detail = Table(data_detail, colWidths=[80, 140, 140, 80])
    t_detail.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (3,0), (3,-1), 'CENTER'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)
    ]))
    elements.append(t_detail)

    doc.build(elements)
    return buffer.getvalue()

# ==================== INTERFACE STREAMLIT ====================
st.title("📊 Dashboard de Gestion des Déchets - Mékhé")

try:
    df = load_all_data()

    if df.empty:
        st.info("ℹ️ Aucune donnée de collecte validée pour le moment.")
    else:
        tab_stats, tab_pdf, tab_admin = st.tabs(["📈 Statistiques", "📄 Rapports PDF", "🔧 Administration"])

        # --- ONGLET 1 : STATISTIQUES ---
        with tab_stats:
            c1, c2, c3 = st.columns(3)
            c1.metric("Volume Global", f"{df['volume_total_m3'].sum():.1f} m³")
            c2.metric("Distance Cumulée", f"{df['distance_km'].sum():.1f} km")
            c3.metric("Tournées Effectuées", len(df))
            
            # Graphique par Quartier
            fig = px.bar(df.groupby('quartier_nom')['volume_total_m3'].sum().reset_index(), 
                         x='quartier_nom', y='volume_total_m3', 
                         title="Volume de déchets par Quartier",
                         labels={'quartier_nom': 'Quartier', 'volume_total_m3': 'Volume (m³)'},
                         color='volume_total_m3', color_continuous_scale='Greens')
            st.plotly_chart(fig, use_container_width=True)

        # --- ONGLET 2 : RAPPORTS PDF ---
        with tab_pdf:
            st.subheader("Générer un rapport officiel")
            mode = st.radio("Périodicité :", ["Mensuel", "Hebdomadaire"], horizontal=True)
            
            if mode == "Mensuel":
                m = st.selectbox("Mois", range(1, 13), index=datetime.now().month-1, format_func=lambda x: calendar.month_name[x])
                df_filtre = df[df['mois'] == m]
                titre_rep = f"Mois de {calendar.month_name[m]}"
            else:
                s = st.selectbox("Semaine", sorted(df['semaine'].unique(), reverse=True))
                df_filtre = df[df['semaine'] == s]
                titre_rep = f"Semaine {s}"

            if not df_filtre.empty:
                if st.button("🚀 Générer le PDF"):
                    pdf_bytes = generer_pdf(df_filtre, titre_rep)
                    st.download_button(f"📥 Télécharger Rapport ({titre_rep})", pdf_bytes, f"Rapport_Mekhe_{titre_rep}.pdf", "application/pdf")
            else:
                st.warning("Aucune donnée pour cette période.")

        # --- ONGLET 3 : ADMINISTRATION (CORRECTIONS) ---
        with tab_admin:
            st.subheader("🔧 Correction d'erreurs de saisie")
            st.info("Utilisez cet outil pour corriger un volume ou une distance saisi par erreur par un agent.")
            
            # Sélection de la tournée
            tournee_options = df.apply(lambda x: f"ID: {x['id']} | {x['date_tournee'].strftime('%d/%m')} | {x['quartier_nom']}", axis=1)
            selected_label = st.selectbox("Sélectionner la tournée à corriger", tournee_options)
            
            # Récupération de l'ID
            sel_id = int(selected_label.split("ID: ")[1].split(" |")[0])
            current_data = df[df['id'] == sel_id].iloc[0]

            col_a, col_b = st.columns(2)
            v_val = col_a.number_input("Corriger Volume (m³)", value=float(current_data['volume_total_m3']), step=0.1)
            d_val = col_b.number_input("Corriger Distance (km)", value=float(current_data['distance_km']), step=0.1)
            
            if st.button("✅ Valider les modifications"):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE tournees SET volume_total_m3 = :v, distance_km = :d WHERE id = :id"),
                                 {"v": v_val, "d": d_val, "id": sel_id})
                st.success("Données mises à jour avec succès dans la base !")
                st.cache_data.clear() # Force le rechargement des graphiques

except Exception as e:
    st.error(f"Une erreur est survenue : {e}")
