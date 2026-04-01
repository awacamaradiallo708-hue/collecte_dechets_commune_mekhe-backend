import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, text
import os
import io
import calendar

# Bibliothèques pour le PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==================== CONFIGURATION PAGE ====================
st.set_page_config(
    page_title="Dashboard Collecte - Mékhé",
    page_icon="📊",
    layout="wide"
)

# Style CSS personnalisé
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #1e5631 0%, #a4de02 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .admin-box {
        background: #fff3e0;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #ff9800;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== CONNEXION BDD ====================
DATABASE_URL = st.secrets["DATABASE_URL"] if "DATABASE_URL" in st.secrets else os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("❌ Erreur : DATABASE_URL non configurée.")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS UTILES ====================

@st.cache_data(ttl=600) # Cache de 10 minutes
def load_all_data():
    with engine.connect() as conn:
        query = text("""
            SELECT 
                t.id, t.date_tournee, t.agent_nom, q.nom as quartier, e.nom as equipe,
                t.volume_m3, t.distance_parcourue_km, t.heure_depot_depart, t.heure_retour_depot,
                (SELECT COUNT(*) FROM points_arret WHERE tournee_id = t.id) as nb_points
            FROM tournees t
            JOIN quartiers q ON t.quartier_id = q.id
            JOIN equipes e ON t.equipe_id = e.id
            WHERE t.statut = 'termine'
            ORDER BY t.date_tournee DESC
        """)
        df = pd.read_sql(query, conn)
        df['date_tournee'] = pd.to_datetime(df['date_tournee'])
        df['semaine'] = df['date_tournee'].dt.isocalendar().week
        df['mois'] = df['date_tournee'].dt.month
        df['annee'] = df['date_tournee'].dt.year
        return df

def generer_pdf(df_periode, titre_periode):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Entête
    elements.append(Paragraph(f"RAPPORT OFFICIEL DE COLLECTE - MÉKHÉ", styles['Title']))
    elements.append(Paragraph(f"Période : {titre_periode}", styles['Heading2']))
    elements.append(Paragraph(f"Généré le : {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Résumé
    stats = [
        ["Indicateur", "Valeur"],
        ["Nombre de tournées", str(len(df_periode))],
        ["Volume total collecté", f"{df_periode['volume_m3'].sum():.2f} m³"],
        ["Distance totale", f"{df_periode['distance_parcourue_km'].sum():.2f} km"],
        ["Nombre d'agents", str(df_periode['agent_nom'].nunique())]
    ]
    table_stats = Table(stats, colWidths=[200, 150])
    table_stats.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.green),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 8)
    ]))
    elements.append(table_stats)
    elements.append(Spacer(1, 25))

    # Tableau détaillé (colonnes simplifiées pour tenir sur A4)
    elements.append(Paragraph("Détail des opérations :", styles['Heading3']))
    data_detail = [["Date", "Quartier", "Agent", "Volume (m³)"]]
    for _, row in df_periode.iterrows():
        data_detail.append([row['date_tournee'].strftime('%d/%m/%Y'), row['quartier'], row['agent_nom'], f"{row['volume_m3']:.1f}"])
    
    table_detail = Table(data_detail, colWidths=[80, 150, 150, 80])
    table_detail.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (3,0), (3,-1), 'CENTER')
    ]))
    elements.append(table_detail)

    doc.build(elements)
    return buffer.getvalue()

# ==================== INTERFACE PRINCIPALE ====================

st.markdown('<div class="main-header"><h1>📊 Suivi des Déchets - Mékhé</h1><p>Outil de gestion pour les services techniques municipaux</p></div>', unsafe_allow_html=True)

df = load_all_data()

if df.empty:
    st.info("ℹ️ En attente de données. Les collectes apparaîtront ici après validation par les agents.")
    st.stop()

# Barre latérale (Filtres)
with st.sidebar:
    st.image("https://via.placeholder.com/150?text=MEKHE", width=100) # Remplacez par le logo de la ville
    st.header("🎛️ Filtres")
    selected_quartier = st.multiselect("Quartiers", df['quartier'].unique(), default=df['quartier'].unique())
    df_filtered = df[df['quartier'].isin(selected_quartier)]

# Onglets
tabs = st.tabs(["📈 Analyse", "🗺️ Carte", "📄 Rapports PDF", "🔧 Administration"])

# --- ONGLET 1 : ANALYSE ---
with tabs[0]:
    col1, col2, col3 = st.columns(3)
    col1.metric("Volume Total", f"{df_filtered['volume_m3'].sum():.1f} m³")
    col2.metric("Distance Cumulée", f"{df_filtered['distance_parcourue_km'].sum():.1f} km")
    col3.metric("Tournées Terminées", len(df_filtered))

    st.plotly_chart(px.bar(df_filtered.groupby('quartier')['volume_m3'].sum().reset_index(), 
                           x='quartier', y='volume_m3', title="Volume par Quartier", color='volume_m3'), use_container_width=True)

# --- ONGLET 2 : CARTE (VOTRE EXPERTISE) ---
with tabs[1]:
    st.subheader("📍 Géolocalisation des collectes")
    with engine.connect() as conn:
        df_geo = pd.read_sql("SELECT latitude, longitude, type_point FROM points_arret", conn)
    
    if not df_geo.empty:
        fig_map = px.scatter_mapbox(df_geo, lat="latitude", lon="longitude", color="type_point",
                                    mapbox_style="carto-positron", zoom=13)
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.warning("Aucune donnée GPS disponible.")

# --- ONGLET 3 : RAPPORTS PDF (DEMANDÉ) ---
with tabs[2]:
    st.subheader("📄 Génération de Rapports Officiels")
    type_r = st.radio("Type de rapport :", ["Hebdomadaire (Semaine)", "Mensuel (Mois)"], horizontal=True)
    
    if type_r == "Hebdomadaire (Semaine)":
        sem = st.selectbox("Choisir la semaine", sorted(df['semaine'].unique(), reverse=True))
        df_pdf = df[df['semaine'] == sem]
        titre = f"Semaine {sem} - Année {df_pdf['annee'].iloc[0]}"
    else:
        m = st.selectbox("Choisir le mois", range(1, 13), format_func=lambda x: calendar.month_name[x])
        df_pdf = df[df['mois'] == m]
        titre = f"Mois de {calendar.month_name[m]}"

    if st.button("🚀 Préparer le PDF"):
        pdf_bytes = generer_pdf(df_pdf, titre)
        st.download_button(label="📥 Télécharger le rapport PDF", data=pdf_bytes, 
                           file_name=f"Rapport_Mekhe_{titre}.pdf", mime="application/pdf")

# --- ONGLET 4 : ADMINISTRATION (DEMANDÉ) ---
with tabs[3]:
    st.markdown('<div class="admin-box">', unsafe_allow_html=True)
    st.subheader("✏️ Correction d'erreurs de saisie")
    st.write("Modifiez ici les volumes ou distances en cas d'erreur de l'agent.")
    
    # Liste des 20 dernières tournées pour modification
    tournee_to_edit = st.selectbox("Sélectionner la tournée à corriger (ID - Agent - Date)", 
                                   options=df.head(20).apply(lambda x: f"{x['id']} | {x['agent_nom']} | {x['date_tournee'].strftime('%d/%m')}", axis=1))
    
    id_to_edit = int(tournee_to_edit.split(" | ")[0])
    row_data = df[df['id'] == id_to_edit].iloc[0]

    c1, c2 = st.columns(2)
    new_vol = c1.number_input("Corriger Volume (m³)", value=float(row_data['volume_m3']))
    new_dist = c2.number_input("Corriger Distance (km)", value=float(row_data['distance_parcourue_km']))

    if st.button("✅ Enregistrer les corrections"):
        try:
            with engine.begin() as conn:
                conn.execute(text("UPDATE tournees SET volume_m3 = :v, distance_parcourue_km = :d WHERE id = :id"),
                             {"v": new_vol, "d": new_dist, "id": id_to_edit})
            st.success(f"Tournée {id_to_edit} mise à jour ! Veuillez rafraîchir la page.")
            st.cache_data.clear() # On vide le cache pour forcer la lecture de la correction
        except Exception as e:
            st.error(f"Erreur lors de la mise à jour : {e}")
    st.markdown('</div>', unsafe_allow_html=True)
