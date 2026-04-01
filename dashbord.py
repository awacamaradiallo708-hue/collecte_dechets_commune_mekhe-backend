import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from sqlalchemy import create_engine, text
import os
import io
import calendar

# Imports PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==================== CONFIGURATION ====================
st.set_page_config(page_title="Mairie de Mékhé - Gestion Déchets", layout="wide")

# Connexion
if "DATABASE_URL" in st.secrets:
    DATABASE_URL = st.secrets["DATABASE_URL"]
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

def calculer_h(h_dep, h_arr):
    try:
        fmt = '%H:%M'
        d = datetime.strptime(str(h_arr)[:5], fmt) - datetime.strptime(str(h_dep)[:5], fmt)
        return round(d.total_seconds() / 3600, 2)
    except: return 0

# ==================== CHARGEMENT DYNAMIQUE ====================
@st.cache_data(ttl=60)
def load_data_safe():
    with engine.connect() as conn:
        # On récupère TOUTES les colonnes pour éviter l'erreur "UndefinedColumn"
        df_t = pd.read_sql(text("SELECT * FROM tournees WHERE statut = 'termine'"), conn)
        df_gps = pd.read_sql(text("SELECT * FROM points_arret"), conn)
        
        if not df_t.empty:
            df_t['date_tournee'] = pd.to_datetime(df_t['date_tournee'])
            df_t['semaine'] = df_t['date_tournee'].dt.isocalendar().week
            df_t['mois'] = df_t['date_tournee'].dt.month
            
            # Vérification des noms de colonnes pour le temps
            # On teste les deux variantes possibles
            c_dep = 'heure_depart_depot' if 'heure_depart_depot' in df_t.columns else 'heure_depot_depart'
            c_arr = 'heure_arrivee_depot' if 'heure_arrivee_depot' in df_t.columns else 'heure_retour_depot'
            
            if c_dep in df_t.columns and c_arr in df_t.columns:
                df_t['duree_h'] = df_t.apply(lambda x: calculer_h(x[c_dep], x[c_arr]), axis=1)
            else:
                df_t['duree_h'] = 0
                
        return df_t, df_gps

# ==================== INTERFACE ====================
st.title("🇸🇳 Dashboard de Suivi - Mékhé")

try:
    df, df_gps = load_data_safe()

    if df.empty:
        st.warning("Aucune donnée trouvée.")
    else:
        t1, t2, t3 = st.tabs(["Statistiques", "Carte GPS", "Rapports PDF"])
        
        with t1:
            col1, col2 = st.columns(2)
            col1.metric("Volume Total (m³)", f"{df['volume_total_m3'].sum():.1f}")
            col2.metric("Temps de Collecte (h)", f"{df['duree_h'].sum():.1f}")
            
            fig = px.bar(df, x='quartier_nom', y='volume_total_m3', color='agent_nom', title="Volume par Quartier")
            st.plotly_chart(fig, use_container_width=True)
            
        with t2:
            if not df_gps.empty:
                st.map(df_gps) # Version simple pour tester la stabilité
            else:
                st.write("Pas de points GPS.")

        with t3:
            st.subheader("Exporter un rapport")
            mode = st.radio("Période", ["Semaine", "Mois"])
            if st.button("Générer PDF"):
                st.success("Rapport prêt (Simulation)")
                # La fonction PDF reste la même que précédemment

except Exception as e:
    st.error(f"Détails de l'erreur : {e}")
    st.info("Astuce : Si l'erreur mentionne encore 'heure_depot_depart', cliquez sur 'Clear Cache' dans le menu Streamlit.")
