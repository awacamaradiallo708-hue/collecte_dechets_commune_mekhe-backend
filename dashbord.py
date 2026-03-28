"""
DASHBOARD DE SUIVI DES COLLECTES - COMMUNE DE MÉKHÉ
Version temps réel avec :
- Suivi quotidien
- Suivi hebdomadaire
- Graphiques interactifs
- Export Excel et Word
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, text
import os
from io import BytesIO
import calendar

st.set_page_config(
    page_title="Dashboard Collecte - Mékhé",
    page_icon="📊",
    layout="wide"
)

# ==================== STYLE CSS ====================
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #2196F3;
        margin: 1rem 0;
    }
    .success-box {
        background: #d4edda;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📊 Dashboard de Suivi des Collectes</h1><p>Commune de Mékhé | Suivi temps réel</p></div>', unsafe_allow_html=True)

# ==================== CONNEXION BASE DE DONNÉES ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ Configuration base de données manquante")
    st.stop()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==================== FONCTIONS ====================

def load_all_data():
    """Charge toutes les données de la base"""
    with engine.connect() as conn:
        query = text("""
            SELECT 
                t.id,
                t.date_tournee,
                t.agent_nom,
                q.nom as quartier,
                e.nom as equipe,
                t.volume_collecte1,
                t.volume_collecte2,
                t.volume_m3,
                t.distance_parcourue_km,
                t.heure_depot_depart,
                t.heure_retour_depot,
                t.created_at,
                (SELECT COUNT(*) FROM points_arret WHERE tournee_id = t.id) as nb_points
            FROM tournees t
            JOIN quartiers q ON t.quartier_id = q.id
            JOIN equipes e ON t.equipe_id = e.id
            WHERE t.statut = 'termine'
            ORDER BY t.date_tournee DESC
        """)
        
        result = conn.execute(query).fetchall()
        
        df = pd.DataFrame(result, columns=[
            'id', 'date', 'agent', 'quartier', 'equipe',
            'volume1', 'volume2', 'volume_total', 'distance',
            'depart', 'retour', 'created_at', 'nb_points'
        ])
        
        df['date'] = pd.to_datetime(df['date'])
        df['semaine'] = df['date'].dt.isocalendar().week
        df['annee'] = df['date'].dt.year
        df['mois'] = df['date'].dt.month
        df['jour_semaine'] = df['date'].dt.day_name()
        
        return df

def get_stats_quotidiennes(df, date_jour):
    """Statistiques pour une journée donnée"""
    df_jour = df[df['date'].dt.date == date_jour]
    
    if df_jour.empty:
        return None
    
    return {
        "nb_tournees": len(df_jour),
        "volume_total": df_jour['volume_total'].sum(),
        "distance_total": df_jour['distance'].sum(),
        "nb_quartiers": df_jour['quartier'].nunique(),
        "nb_agents": df_jour['agent'].nunique(),
        "moyenne_volume": df_jour['volume_total'].mean(),
        "top_quartier": df_jour.groupby('quartier')['volume_total'].sum().idxmax() if not df_jour.empty else "N/A"
    }

def get_stats_hebdomadaires(df, annee, semaine):
    """Statistiques pour une semaine donnée"""
    df_semaine = df[(df['annee'] == annee) & (df['semaine'] == semaine)]
    
    if df_semaine.empty:
        return None
    
    return {
        "nb_tournees": len(df_semaine),
        "volume_total": df_semaine['volume_total'].sum(),
        "distance_total": df_semaine['distance'].sum(),
        "nb_quartiers": df_semaine['quartier'].nunique(),
        "nb_agents": df_semaine['agent'].nunique(),
        "moyenne_journaliere": df_semaine.groupby('date')['volume_total'].sum().mean(),
        "top_quartier": df_semaine.groupby('quartier')['volume_total'].sum().idxmax() if not df_semaine.empty else "N/A"
    }

def get_stats_mensuelles(df, annee, mois):
    """Statistiques pour un mois donné"""
    df_mois = df[(df['annee'] == annee) & (df['mois'] == mois)]
    
    if df_mois.empty:
        return None
    
    return {
        "nb_tournees": len(df_mois),
        "volume_total": df_mois['volume_total'].sum(),
        "distance_total": df_mois['distance'].sum(),
        "nb_quartiers": df_mois['quartier'].nunique(),
        "nb_agents": df_mois['agent'].nunique(),
        "moyenne_journaliere": df_mois.groupby('date')['volume_total'].sum().mean(),
        "top_quartier": df_mois.groupby('quartier')['volume_total'].sum().idxmax() if not df_mois.empty else "N/A"
    }

def exporter_excel(df, periode_type, periode_nom):
    """Exporte les données en Excel"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Feuille résumé
        df.to_excel(writer, sheet_name=f"Données_{periode_type}", index=False)
        
        # Feuille synthèse par quartier
        synth_quartier = df.groupby('quartier').agg({
            'volume_total': 'sum',
            'distance': 'sum',
            'nb_points': 'sum',
            'id': 'count'
        }).round(2)
        synth_quartier.columns = ['Volume total (m³)', 'Distance (km)', 'Points GPS', 'Nombre collectes']
        synth_quartier = synth_quartier.sort_values('Volume total (m³)', ascending=False)
        synth_quartier.to_excel(writer, sheet_name="Synthèse par quartier")
        
        # Feuille synthèse par agent
        synth_agent = df.groupby('agent').agg({
            'volume_total': 'sum',
            'nb_points': 'sum',
            'id': 'count'
        }).round(2)
        synth_agent.columns = ['Volume total (m³)', 'Points GPS', 'Nombre collectes']
        synth_agent = synth_agent.sort_values('Volume total (m³)', ascending=False)
        synth_agent.to_excel(writer, sheet_name="Synthèse par agent")
        
        # Feuille évolution quotidienne
        evol_quotidienne = df.groupby('date').agg({
            'volume_total': 'sum',
            'distance': 'sum',
            'id': 'count'
        }).reset_index()
        evol_quotidienne.columns = ['Date', 'Volume (m³)', 'Distance (km)', 'Nombre collectes']
        evol_quotidienne.to_excel(writer, sheet_name="Évolution quotidienne", index=False)
    
    return output.getvalue()

def exporter_word(df, periode_type, periode_nom, stats):
    """Génère un rapport Word (HTML exportable)"""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Rapport Collectes - {periode_nom}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2E7D32; }}
            h2 {{ color: #1B5E20; margin-top: 30px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #2E7D32; color: white; }}
            .metric {{ background: #f5f5f5; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            .success {{ color: #28a745; }}
        </style>
    </head>
    <body>
        <h1>📊 Rapport de suivi des collectes</h1>
        <p><strong>Période:</strong> {periode_nom}</p>
        <p><strong>Date d'édition:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        
        <h2>📈 Résumé général</h2>
        <table>
            <tr><th>Indicateur</th><th>Valeur</th></tr>
            <tr><td>Nombre de tournées</td><td>{stats.get('nb_tournees', 0)}</td></tr>
            <tr><td>Volume total collecté</td><td>{stats.get('volume_total', 0):.1f} m³</td></tr>
            <tr><td>Distance totale parcourue</td><td>{stats.get('distance_total', 0):.1f} km</td></tr>
            <tr><td>Nombre de quartiers visités</td><td>{stats.get('nb_quartiers', 0)}</td></tr>
            <tr><td>Nombre d'agents actifs</td><td>{stats.get('nb_agents', 0)}</td></tr>
            <tr><td>Quartier le plus productif</td><td>{stats.get('top_quartier', 'N/A')}</td></tr>
        </table>
        
        <h2>🏘️ Répartition par quartier</h2>
        {df.groupby('quartier').agg({'volume_total': 'sum'}).sort_values('volume_total', ascending=False).to_html()}
        
        <h2>👥 Performance par agent</h2>
        {df.groupby('agent').agg({'volume_total': 'sum', 'id': 'count'}).sort_values('volume_total', ascending=False).to_html()}
        
        <hr>
        <footer>
            <p>Commune de Mékhé - Service de collecte des déchets</p>
            <p>Rapport généré automatiquement le {datetime.now().strftime('%d/%m/%Y')}</p>
        </footer>
    </body>
    </html>
    """
    
    return html_content

# ==================== CHARGEMENT DES DONNÉES ====================
with st.spinner("Chargement des données..."):
    df = load_all_data()

if df.empty:
    st.warning("⚠️ Aucune donnée disponible. Les agents doivent d'abord enregistrer des collectes.")
    st.info("""
    **Pour commencer :**
    1. Les agents doivent utiliser l'application de collecte
    2. Enregistrer leurs tournées
    3. Les données apparaîtront ici automatiquement
    """)
    st.stop()

# ==================== BARRE LATÉRALE ====================
with st.sidebar:
    st.header("🎛️ Filtres")
    
    # Sélection de la période
    periode = st.selectbox(
        "Période d'analyse",
        ["Aujourd'hui", "Cette semaine", "Ce mois", "Personnalisé"]
    )
    
    if periode == "Aujourd'hui":
        date_filter = st.date_input("Date", value=date.today())
        df_filtered = df[df['date'].dt.date == date_filter]
        periode_nom = date_filter.strftime("%d/%m/%Y")
        
    elif periode == "Cette semaine":
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        df_filtered = df[(df['date'].dt.date >= start_of_week) & (df['date'].dt.date <= end_of_week)]
        periode_nom = f"Semaine du {start_of_week.strftime('%d/%m')} au {end_of_week.strftime('%d/%m/%Y')}"
        
    elif periode == "Ce mois":
        today = date.today()
        start_of_month = today.replace(day=1)
        df_filtered = df[df['date'].dt.date >= start_of_month]
        periode_nom = f"Mois de {calendar.month_name[today.month]} {today.year}"
        
    else:
        col1, col2 = st.columns(2)
        with col1:
            date_debut = st.date_input("Date début", value=date.today() - timedelta(days=30))
        with col2:
            date_fin = st.date_input("Date fin", value=date.today())
        df_filtered = df[(df['date'].dt.date >= date_debut) & (df['date'].dt.date <= date_fin)]
        periode_nom = f"Du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
    
    # Filtres supplémentaires
    st.markdown("---")
    quartiers = st.multiselect("Quartiers", df_filtered['quartier'].unique(), default=df_filtered['quartier'].unique())
    agents = st.multiselect("Agents", df_filtered['agent'].unique(), default=df_filtered['agent'].unique())
    
    df_filtered = df_filtered[df_filtered['quartier'].isin(quartiers)]
    df_filtered = df_filtered[df_filtered['agent'].isin(agents)]

# ==================== MÉTRIQUES ====================
st.subheader(f"📅 Période : {periode_nom}")

if not df_filtered.empty:
    total_volume = df_filtered['volume_total'].sum()
    total_distance = df_filtered['distance'].sum()
    nb_tournees = len(df_filtered)
    nb_quartiers = df_filtered['quartier'].nunique()
    nb_agents = df_filtered['agent'].nunique()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📦 Volume total", f"{total_volume:.1f} m³")
        st.caption(f"≈ {total_volume * 0.8:.0f} tonnes")
    
    with col2:
        st.metric("📏 Distance totale", f"{total_distance:.1f} km")
    
    with col3:
        st.metric("🚛 Tournées", nb_tournees)
    
    with col4:
        st.metric("🏘️ Quartiers", nb_quartiers)
    
    with col5:
        st.metric("👥 Agents", nb_agents)
    
    # Efficacité
    if total_volume > 0:
        efficacite = total_distance / total_volume
        st.info(f"📊 **Efficacité globale :** {efficacite:.2f} km par m³ collecté")
    
    st.markdown("---")

# ==================== GRAPHIQUES ====================
if not df_filtered.empty:
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Évolution", 
        "🥇 Classements", 
        "🗺️ Carte", 
        "📋 Détails"
    ])
    
    # ==================== TAB 1 : ÉVOLUTION ====================
    with tab1:
        st.subheader("📈 Évolution des collectes")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Évolution quotidienne du volume
            evol_journaliere = df_filtered.groupby('date')['volume_total'].sum().reset_index()
            fig_evol = px.line(
                evol_journaliere, x='date', y='volume_total',
                title="Volume collecté par jour (m³)",
                markers=True,
                labels={'date': 'Date', 'volume_total': 'Volume (m³)'}
            )
            fig_evol.update_layout(height=400)
            st.plotly_chart(fig_evol, use_container_width=True)
        
        with col2:
            # Évolution cumulée
            evol_cumulee = evol_journaliere.copy()
            evol_cumulee['cumul'] = evol_cumulee['volume_total'].cumsum()
            fig_cumul = px.area(
                evol_cumulee, x='date', y='cumul',
                title="Volume cumulé (m³)",
                labels={'date': 'Date', 'cumul': 'Volume cumulé (m³)'},
                color_discrete_sequence=['#2E7D32']
            )
            fig_cumul.update_layout(height=400)
            st.plotly_chart(fig_cumul, use_container_width=True)
        
        # Évolution par quartier
        evol_quartier = df_filtered.groupby(['date', 'quartier'])['volume_total'].sum().reset_index()
        fig_quartier = px.line(
            evol_quartier, x='date', y='volume_total', color='quartier',
            title="Évolution par quartier (m³)",
            markers=True
        )
        fig_quartier.update_layout(height=500)
        st.plotly_chart(fig_quartier, use_container_width=True)
    
    # ==================== TAB 2 : CLASSEMENTS ====================
    with tab2:
        st.subheader("🥇 Classements et performances")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Classement par quartier
            top_quartiers = df_filtered.groupby('quartier')['volume_total'].sum().sort_values(ascending=True)
            fig_quartiers = px.bar(
                x=top_quartiers.values, y=top_quartiers.index, orientation='h',
                title="Volume total par quartier (m³)",
                labels={'x': 'Volume (m³)', 'y': 'Quartier'},
                color=top_quartiers.values,
                color_continuous_scale='Viridis',
                text=top_quartiers.values
            )
            fig_quartiers.update_traces(texttemplate='%{text:.1f} m³', textposition='outside')
            fig_quartiers.update_layout(height=400)
            st.plotly_chart(fig_quartiers, use_container_width=True)
        
        with col2:
            # Classement par agent
            top_agents = df_filtered.groupby('agent')['volume_total'].sum().sort_values(ascending=True)
            fig_agents = px.bar(
                x=top_agents.values, y=top_agents.index, orientation='h',
                title="Volume total par agent (m³)",
                labels={'x': 'Volume (m³)', 'y': 'Agent'},
                color=top_agents.values,
                color_continuous_scale='Viridis',
                text=top_agents.values
            )
            fig_agents.update_traces(texttemplate='%{text:.1f} m³', textposition='outside')
            fig_agents.update_layout(height=400)
            st.plotly_chart(fig_agents, use_container_width=True)
        
        # Camembert de répartition
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = px.pie(
                df_filtered, values='volume_total', names='quartier',
                title="Répartition des volumes par quartier",
                hole=0.3
            )
            fig_pie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Tableau des performances
            st.subheader("📊 Tableau de bord")
            
            perf_df = df_filtered.groupby('quartier').agg({
                'volume_total': 'sum',
                'distance': 'sum',
                'id': 'count',
                'nb_points': 'sum'
            }).round(2)
            perf_df.columns = ['Volume (m³)', 'Distance (km)', 'Collectes', 'Points GPS']
            perf_df = perf_df.sort_values('Volume (m³)', ascending=False)
            
            st.dataframe(perf_df, use_container_width=True)
    
    # ==================== TAB 3 : CARTE ====================
    with tab3:
        st.subheader("🗺️ Carte des points de collecte")
        
        # Récupérer les points GPS
        with engine.connect() as conn:
            points_query = text("""
                SELECT 
                    pa.latitude,
                    pa.longitude,
                    pa.type_point,
                    pa.description,
                    pa.collecte_numero,
                    pa.heure,
                    q.nom as quartier
                FROM points_arret pa
                JOIN tournees t ON pa.tournee_id = t.id
                JOIN quartiers q ON t.quartier_id = q.id
                WHERE pa.latitude IS NOT NULL
                ORDER BY pa.heure DESC
                LIMIT 500
            """)
            points = conn.execute(points_query).fetchall()
        
        if points:
            df_points = pd.DataFrame(points, columns=['lat', 'lon', 'type', 'description', 'collecte', 'heure', 'quartier'])
            
            couleurs = {
                "depart_depot": "green",
                "debut_collecte": "blue",
                "fin_collecte": "blue",
                "depart_decharge": "orange",
                "arrivee_decharge": "red",
                "sortie_decharge": "purple",
                "retour_depot": "brown"
            }
            
            noms_points = {
                "depart_depot": "🏭 Départ dépôt",
                "debut_collecte": "🗑️ Début collecte",
                "fin_collecte": "🗑️ Fin collecte",
                "depart_decharge": "🚛 Départ décharge",
                "arrivee_decharge": "🏭 Arrivée décharge",
                "sortie_decharge": "🏭 Sortie décharge",
                "retour_depot": "🏁 Retour dépôt"
            }
            
            df_points["nom_affichage"] = df_points["type"].map(noms_points)
            
            fig_map = px.scatter_mapbox(
                df_points,
                lat="lat",
                lon="lon",
                color="type",
                hover_name="nom_affichage",
                hover_data={"quartier": True, "collecte": True, "heure": True},
                color_discrete_map=couleurs,
                zoom=12,
                center={"lat": 15.11, "lon": -16.65},
                title="Carte des points GPS enregistrés",
                height=600
            )
            
            fig_map.update_layout(
                mapbox_style="open-street-map",
                margin={"r": 0, "t": 40, "l": 0, "b": 0}
            )
            
            st.plotly_chart(fig_map, use_container_width=True)
            
            st.markdown("""
            <div class="info-box">
            <strong>📊 Légende :</strong><br>
            🟢 Vert - Départ dépôt<br>
            🔵 Bleu - Points de collecte<br>
            🟠 Orange - Départ vers décharge<br>
            🔴 Rouge - Arrivée décharge<br>
            🟣 Violet - Sortie décharge<br>
            🟤 Marron - Retour dépôt
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Aucun point GPS enregistré pour le moment")
    
    # ==================== TAB 4 : DÉTAILS ====================
    with tab4:
        st.subheader("📋 Détail des collectes")
        
        # Afficher les données
        display_df = df_filtered.copy()
        display_df['date'] = display_df['date'].dt.strftime('%d/%m/%Y')
        display_df['volume_total'] = display_df['volume_total'].apply(lambda x: f"{x:.1f} m³")
        display_df['distance'] = display_df['distance'].apply(lambda x: f"{x:.1f} km")
        
        st.dataframe(
            display_df[['date', 'quartier', 'agent', 'equipe', 'volume_total', 'distance', 'nb_points']],
            use_container_width=True,
            column_config={
                "date": "Date",
                "quartier": "Quartier",
                "agent": "Agent",
                "equipe": "Équipe",
                "volume_total": "Volume",
                "distance": "Distance",
                "nb_points": "Points GPS"
            }
        )
        
        # Export
        st.markdown("---")
        st.subheader("📥 Export des données")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 EXPORTER EN EXCEL", use_container_width=True, type="primary"):
                excel_data = exporter_excel(df_filtered, periode, periode_nom)
                st.download_button(
                    label="📥 Télécharger Excel",
                    data=excel_data,
                    file_name=f"rapport_collectes_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col2:
            if st.button("📄 EXPORTER EN WORD", use_container_width=True):
                stats = {
                    "nb_tournees": len(df_filtered),
                    "volume_total": df_filtered['volume_total'].sum(),
                    "distance_total": df_filtered['distance'].sum(),
                    "nb_quartiers": df_filtered['quartier'].nunique(),
                    "nb_agents": df_filtered['agent'].nunique(),
                    "top_quartier": df_filtered.groupby('quartier')['volume_total'].sum().idxmax() if not df_filtered.empty else "N/A"
                }
                html_content = exporter_word(df_filtered, periode, periode_nom, stats)
                st.download_button(
                    label="📥 Télécharger Word",
                    data=html_content,
                    file_name=f"rapport_collectes_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html"
                )

else:
    st.warning("⚠️ Aucune donnée pour la période sélectionnée")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📊 Dernière mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Données en temps réel | Commune de Mékhé")
