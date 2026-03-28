"""
DASHBOARD DE SUIVI DES COLLECTES - COMMUNE DE MÉKHÉ
Version complète avec page administration
- Suivi quotidien, hebdomadaire, mensuel
- Graphiques interactifs
- Export Excel et Word
- Panneau d'administration
- Unités : mètres cubes (m³)
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
    .admin-box {
        background: #fff3e0;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #FF9800;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📊 Dashboard de Suivi des Collectes</h1><p>Commune de Mékhé | Suivi temps réel | Unité : m³</p></div>', unsafe_allow_html=True)

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

def exporter_excel(df, periode_type, periode_nom):
    """Exporte les données en Excel"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=f"Données_{periode_type}", index=False)
        
        synth_quartier = df.groupby('quartier').agg({
            'volume_total': 'sum',
            'distance': 'sum',
            'nb_points': 'sum',
            'id': 'count'
        }).round(2)
        synth_quartier.columns = ['Volume total (m³)', 'Distance (km)', 'Points GPS', 'Nombre collectes']
        synth_quartier.to_excel(writer, sheet_name="Synthèse par quartier")
        
        synth_agent = df.groupby('agent').agg({
            'volume_total': 'sum',
            'nb_points': 'sum',
            'id': 'count'
        }).round(2)
        synth_agent.columns = ['Volume total (m³)', 'Points GPS', 'Nombre collectes']
        synth_agent.to_excel(writer, sheet_name="Synthèse par agent")
        
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
        </style>
    </head>
    <body>
        <h1>📊 Rapport de suivi des collectes</h1>
        <p><strong>Période:</strong> {periode_nom}</p>
        <p><strong>Date d'édition:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        
        <h2>📈 Résumé général</h2>
        <table>
            <tr><th>Indicateur</th><th>Valeur</th></tr>
            <tr><td>Nombre de tournées</td><td>{stats.get('nb_tournees', 0)}</td> </tr>
            <tr><td>Volume total collecté</td><td>{stats.get('volume_total', 0):.1f} m³</td> </tr>
            <tr><td>Distance totale parcourue</td><td>{stats.get('distance_total', 0):.1f} km</td> </tr>
            <tr><td>Nombre de quartiers visités</td><td>{stats.get('nb_quartiers', 0)}</td> </tr>
            <tr><td>Nombre d'agents actifs</td><td>{stats.get('nb_agents', 0)}</td> </tr>
            <tr><td>Quartier le plus productif</td><td>{stats.get('top_quartier', 'N/A')}</td> </tr>
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

# ==================== PAGE ADMINISTRATION ====================
def show_admin_panel():
    """Panneau d'administration pour l'équipe technique"""
    
    st.markdown('<div class="admin-box">🔧 <strong>Panneau d\'administration</strong> - Accès réservé à l\'équipe technique</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Statistiques globales", 
        "👥 Gestion des agents", 
        "🏘️ Gestion des quartiers",
        "📁 Exports et sauvegarde"
    ])
    
    # ==================== TAB 1 : STATISTIQUES GLOBALES ====================
    with tab1:
        st.subheader("📊 Statistiques globales")
        
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM tournees WHERE statut = 'termine'")).scalar()
            st.metric("📦 Total collectes", total)
            
            volume = conn.execute(text("SELECT SUM(volume_m3) FROM tournees WHERE statut = 'termine'")).scalar()
            st.metric("📊 Volume total", f"{volume:.1f} m³" if volume else "0")
            
            agents = conn.execute(text("SELECT COUNT(DISTINCT agent_nom) FROM tournees WHERE statut = 'termine'")).scalar()
            st.metric("👥 Agents actifs", agents)
            
            derniere = conn.execute(text("SELECT MAX(date_tournee) FROM tournees WHERE statut = 'termine'")).scalar()
            st.metric("📅 Dernière collecte", derniere or "Aucune")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with engine.connect() as conn:
                df_activite = pd.read_sql("""
                    SELECT 
                        date_tournee,
                        COUNT(*) as nb_collectes,
                        SUM(volume_m3) as volume
                    FROM tournees 
                    WHERE statut = 'termine'
                    GROUP BY date_tournee
                    ORDER BY date_tournee DESC
                    LIMIT 30
                """, conn)
                
                if not df_activite.empty:
                    fig = px.bar(df_activite, x='date_tournee', y='nb_collectes', 
                                 title="Activité des 30 derniers jours",
                                 labels={'date_tournee': 'Date', 'nb_collectes': 'Nombre de collectes'})
                    st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            with engine.connect() as conn:
                df_volume = pd.read_sql("""
                    SELECT 
                        date_tournee,
                        SUM(volume_m3) as volume_total
                    FROM tournees 
                    WHERE statut = 'termine'
                    GROUP BY date_tournee
                    ORDER BY date_tournee DESC
                    LIMIT 30
                """, conn)
                
                if not df_volume.empty:
                    fig2 = px.line(df_volume, x='date_tournee', y='volume_total',
                                   title="Volume collecté des 30 derniers jours (m³)",
                                   markers=True)
                    st.plotly_chart(fig2, use_container_width=True)
        
        with engine.connect() as conn:
            df_mois = pd.read_sql("""
                SELECT 
                    EXTRACT(YEAR FROM date_tournee) as annee,
                    EXTRACT(MONTH FROM date_tournee) as mois,
                    COUNT(*) as nb_collectes,
                    SUM(volume_m3) as volume_total
                FROM tournees 
                WHERE statut = 'termine'
                GROUP BY annee, mois
                ORDER BY annee DESC, mois DESC
                LIMIT 12
            """, conn)
            
            if not df_mois.empty:
                df_mois['periode'] = df_mois['annee'].astype(int).astype(str) + '-' + df_mois['mois'].astype(int).astype(str).str.zfill(2)
                fig3 = px.bar(df_mois, x='periode', y='volume_total',
                              title="Volume collecté par mois (m³)",
                              labels={'periode': 'Mois', 'volume_total': 'Volume (m³)'})
                st.plotly_chart(fig3, use_container_width=True)
    
    # ==================== TAB 2 : GESTION DES AGENTS ====================
    with tab2:
        st.subheader("👥 Liste des agents")
        
        with engine.connect() as conn:
            agents_df = pd.read_sql("""
                SELECT 
                    agent_nom,
                    COUNT(*) as nb_collectes,
                    SUM(volume_m3) as volume_total_m3,
                    AVG(volume_m3) as volume_moyen_m3,
                    SUM(distance_parcourue_km) as distance_totale_km,
                    MAX(date_tournee) as derniere_activite
                FROM tournees 
                WHERE statut = 'termine'
                GROUP BY agent_nom
                ORDER BY volume_total_m3 DESC
            """, conn)
            
            if not agents_df.empty:
                agents_df.columns = ['Agent', 'Nb collectes', 'Volume total (m³)', 'Volume moyen (m³)', 'Distance totale (km)', 'Dernière activité']
                st.dataframe(agents_df, use_container_width=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    top_agents = agents_df.head(10)
                    fig_agents = px.bar(top_agents, x='Agent', y='Volume total (m³)',
                                        title="Top 10 agents (volume collecté)",
                                        labels={'Agent': 'Agent', 'Volume total (m³)': 'Volume (m³)'},
                                        color='Volume total (m³)',
                                        color_continuous_scale='Viridis')
                    st.plotly_chart(fig_agents, use_container_width=True)
                
                with col2:
                    csv = agents_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Exporter la liste des agents (CSV)",
                        data=csv,
                        file_name=f"agents_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("Aucun agent enregistré")
    
    # ==================== TAB 3 : GESTION DES QUARTIERS (CORRIGÉ EN m³) ====================
    with tab3:
        st.subheader("🏘️ Performance par quartier")
        
        with engine.connect() as conn:
            quartiers_df = pd.read_sql("""
                SELECT 
                    q.nom as quartier,
                    q.population,
                    COUNT(t.id) as nb_collectes,
                    SUM(t.volume_m3) as volume_total_m3,
                    AVG(t.volume_m3) as volume_moyen_m3,
                    SUM(t.distance_parcourue_km) as distance_totale_km,
                    SUM(CASE WHEN t.volume_m3 > 0 THEN t.distance_parcourue_km / t.volume_m3 ELSE 0 END) / NULLIF(COUNT(t.id), 0) as efficacite_moyenne
                FROM quartiers q
                LEFT JOIN tournees t ON q.id = t.quartier_id AND t.statut = 'termine'
                GROUP BY q.nom, q.population
                ORDER BY volume_total_m3 DESC
            """, conn)
            
            if not quartiers_df.empty:
                # Calcul m³ par habitant (volume par personne)
                quartiers_df['m3_par_habitant'] = (quartiers_df['volume_total_m3'] / quartiers_df['population']).fillna(0)
                
                # Renommer les colonnes pour l'affichage
                quartiers_df_display = quartiers_df.copy()
                quartiers_df_display.columns = [
                    'Quartier', 'Population', 'Nb collectes', 
                    'Volume total (m³)', 'Volume moyen (m³)', 
                    'Distance totale (km)', 'Efficacité (km/m³)', 
                    'm³ par habitant'
                ]
                
                st.dataframe(quartiers_df_display, use_container_width=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig_volume = px.bar(
                        quartiers_df.head(10), 
                        x='quartier', 
                        y='volume_total_m3',
                        title="Top quartiers - Volume total collecté (m³)",
                        labels={'quartier': 'Quartier', 'volume_total_m3': 'Volume (m³)'},
                        color='volume_total_m3',
                        color_continuous_scale='Viridis',
                        text='volume_total_m3'
                    )
                    fig_volume.update_traces(texttemplate='%{text:.1f} m³', textposition='outside')
                    st.plotly_chart(fig_volume, use_container_width=True)
                
                with col2:
                    fig_habitant = px.bar(
                        quartiers_df.head(10), 
                        x='quartier', 
                        y='m3_par_habitant',
                        title="Volume collecté par habitant (m³/hab)",
                        labels={'quartier': 'Quartier', 'm3_par_habitant': 'm³ par habitant'},
                        color='m3_par_habitant',
                        color_continuous_scale='Viridis',
                        text='m3_par_habitant'
                    )
                    fig_habitant.update_traces(texttemplate='%{text:.3f} m³', textposition='outside')
                    st.plotly_chart(fig_habitant, use_container_width=True)
                
                st.subheader("📊 Relation Volume collecté vs Population")
                fig_scatter = px.scatter(
                    quartiers_df,
                    x='population',
                    y='volume_total_m3',
                    size='volume_total_m3',
                    text='quartier',
                    title="Corrélation entre population et volume collecté",
                    labels={'population': 'Population', 'volume_total_m3': 'Volume collecté (m³)'},
                    color='volume_total_m3',
                    color_continuous_scale='Viridis'
                )
                fig_scatter.update_traces(textposition='top center')
                st.plotly_chart(fig_scatter, use_container_width=True)
                
                csv = quartiers_df_display.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exporter les données des quartiers (CSV)",
                    data=csv,
                    file_name=f"quartiers_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Aucune donnée disponible")
    
    # ==================== TAB 4 : EXPORTS ET SAUVEGARDE ====================
    with tab4:
        st.subheader("📁 Exports et sauvegarde")
        
        st.markdown("""
        <div class="info-box">
        <strong>📋 Instructions :</strong><br>
        - Export complet : Toutes les données de la base<br>
        - Export période : Données selon la période sélectionnée<br>
        - Sauvegarde : Export hebdomadaire recommandé
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Export complet")
            if st.button("📥 Exporter TOUTES les données", use_container_width=True):
                with engine.connect() as conn:
                    df_all = pd.read_sql("""
                        SELECT 
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
                    """, conn)
                    
                    if not df_all.empty:
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_all.to_excel(writer, sheet_name="Toutes les collectes", index=False)
                            
                            synth = df_all.groupby('quartier').agg({
                                'volume_m3': 'sum',
                                'distance_parcourue_km': 'sum'
                            }).round(2)
                            synth.columns = ['Volume total (m³)', 'Distance totale (km)']
                            synth.to_excel(writer, sheet_name="Synthèse par quartier")
                            
                            df_all['mois'] = df_all['date_tournee'].dt.strftime('%Y-%m')
                            evol = df_all.groupby('mois').agg({'volume_m3': 'sum'}).round(2)
                            evol.columns = ['Volume total (m³)']
                            evol.to_excel(writer, sheet_name="Évolution mensuelle")
                        
                        st.download_button(
                            label="📥 Télécharger l'export complet (Excel)",
                            data=output.getvalue(),
                            file_name=f"export_complet_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("Aucune donnée à exporter")
        
        with col2:
            st.markdown("#### 🗄️ Sauvegarde de la base")
            st.info("""
            **🔧 Commandes utiles pour la sauvegarde :**
            
            Via Neon.tech :
            1. Aller sur https://neon.tech
            2. Ouvrir le projet
            3. Aller dans "Backups"
            4. Créer une sauvegarde manuelle
            """)
        
        st.markdown("---")
        st.markdown("#### 📈 Rapport de synthèse")
        
        date_debut = st.date_input("Date début", value=date.today() - timedelta(days=30))
        date_fin = st.date_input("Date fin", value=date.today())
        
        if st.button("📊 Générer rapport de synthèse", use_container_width=True):
            with engine.connect() as conn:
                df_periode = pd.read_sql(f"""
                    SELECT 
                        t.date_tournee,
                        t.agent_nom,
                        q.nom as quartier,
                        t.volume_m3,
                        t.distance_parcourue_km
                    FROM tournees t
                    JOIN quartiers q ON t.quartier_id = q.id
                    WHERE t.statut = 'termine'
                    AND t.date_tournee BETWEEN '{date_debut}' AND '{date_fin}'
                    ORDER BY t.date_tournee
                """, conn)
                
                if not df_periode.empty:
                    stats = {
                        "nb_tournees": len(df_periode),
                        "volume_total": df_periode['volume_m3'].sum(),
                        "distance_total": df_periode['distance_parcourue_km'].sum(),
                        "nb_quartiers": df_periode['quartier'].nunique(),
                        "nb_agents": df_periode['agent_nom'].nunique(),
                        "top_quartier": df_periode.groupby('quartier')['volume_m3'].sum().idxmax()
                    }
                    
                    html_content = exporter_word(df_periode, "période", f"{date_debut} au {date_fin}", stats)
                    st.download_button(
                        label="📥 Télécharger le rapport Word",
                        data=html_content,
                        file_name=f"rapport_synthese_{date_debut}_{date_fin}.html",
                        mime="text/html"
                    )
                else:
                    st.warning("Aucune donnée pour cette période")

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
    
    st.markdown("---")
    quartiers = st.multiselect("Quartiers", df_filtered['quartier'].unique(), default=df_filtered['quartier'].unique())
    agents = st.multiselect("Agents", df_filtered['agent'].unique(), default=df_filtered['agent'].unique())
    
    df_filtered = df_filtered[df_filtered['quartier'].isin(quartiers)]
    df_filtered = df_filtered[df_filtered['agent'].isin(agents)]

# ==================== ONGLETS PRINCIPAUX ====================
tabs = st.tabs([
    "📈 Tableau de bord",
    "🥇 Classements",
    "🗺️ Carte",
    "📋 Détails",
    "🔧 Administration"
])

# ==================== TAB 1 : TABLEAU DE BORD ====================
with tabs[0]:
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
        
        if total_volume > 0:
            efficacite = total_distance / total_volume
            st.info(f"📊 **Efficacité globale :** {efficacite:.2f} km par m³ collecté")
        
        st.markdown("---")
        
        evol_journaliere = df_filtered.groupby('date')['volume_total'].sum().reset_index()
        fig_evol = px.line(
            evol_journaliere, x='date', y='volume_total',
            title="Volume collecté par jour (m³)",
            markers=True,
            labels={'date': 'Date', 'volume_total': 'Volume (m³)'}
        )
        fig_evol.update_layout(height=400)
        st.plotly_chart(fig_evol, use_container_width=True)
        
        evol_quartier = df_filtered.groupby(['date', 'quartier'])['volume_total'].sum().reset_index()
        fig_quartier = px.line(
            evol_quartier, x='date', y='volume_total', color='quartier',
            title="Évolution par quartier (m³)",
            markers=True
        )
        fig_quartier.update_layout(height=500)
        st.plotly_chart(fig_quartier, use_container_width=True)
        
    else:
        st.warning("⚠️ Aucune donnée pour la période sélectionnée")

# ==================== TAB 2 : CLASSEMENTS ====================
with tabs[1]:
    st.subheader("🥇 Classements et performances")
    
    if not df_filtered.empty:
        col1, col2 = st.columns(2)
        
        with col1:
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
            perf_df = df_filtered.groupby('quartier').agg({
                'volume_total': 'sum',
                'distance': 'sum',
                'id': 'count',
                'nb_points': 'sum'
            }).round(2)
            perf_df.columns = ['Volume (m³)', 'Distance (km)', 'Collectes', 'Points GPS']
            perf_df = perf_df.sort_values('Volume (m³)', ascending=False)
            st.dataframe(perf_df, use_container_width=True)
    else:
        st.info("Aucune donnée disponible")

# ==================== TAB 3 : CARTE ====================
with tabs[2]:
    st.subheader("🗺️ Carte des points de collecte")
    
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
with tabs[3]:
    st.subheader("📋 Détail des collectes")
    
    if not df_filtered.empty:
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
        st.info("Aucune donnée pour la période sélectionnée")

# ==================== TAB 5 : ADMINISTRATION ====================
with tabs[4]:
    show_admin_panel()

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📊 Dernière mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Données en temps réel | Unité : m³ | Commune de Mékhé")
