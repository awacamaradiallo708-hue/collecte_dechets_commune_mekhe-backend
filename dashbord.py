"""
DASHBOARD DE SUIVI DES COLLECTES - COMMUNE DE MÉKHÉ
Version stable synchronisée avec l'application agent
- Suivi quotidien, hebdomadaire, mensuel, annuel
- Graphiques interactifs
- Export Excel et Word
- Panneau d'administration
- Rapports imprimables en PDF (HTML)
- Unités : m³
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
from math import radians, sin, cos, sqrt, atan2

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

# ==================== FONCTIONS UTILITAIRES ====================
def haversine(lat1, lon1, lat2, lon2):
    """Distance en km entre deux points GPS"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def load_all_data():
    """Charge les données depuis la base avec les noms de colonnes originaux"""
    with engine.connect() as conn:
        # Tournées
        query_tournees = text("""
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
        df = pd.read_sql(query_tournees, conn)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date_tournee'])
            df['semaine'] = df['date'].dt.isocalendar().week
            df['annee'] = df['date'].dt.year
            df['mois'] = df['date'].dt.month
            # Alias pour faciliter l'affichage
            df.rename(columns={'agent_nom': 'agent', 'distance_parcourue_km': 'distance'}, inplace=True)
        
        # Points GPS
        query_points = text("""
            SELECT 
                pa.tournee_id,
                pa.heure,
                pa.type_point,
                pa.latitude,
                pa.longitude,
                pa.collecte_numero,
                pa.description,
                q.nom as quartier,
                t.date_tournee
            FROM points_arret pa
            JOIN tournees t ON pa.tournee_id = t.id
            JOIN quartiers q ON t.quartier_id = q.id
            WHERE pa.latitude IS NOT NULL
            ORDER BY t.date_tournee DESC, pa.heure
        """)
        df_points = pd.read_sql(query_points, conn)
        return df, df_points

def formater_duree(minutes):
    if minutes <= 0:
        return "0 min"
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m}min" if h > 0 else f"{m}min"

def generer_rapport_html(df, periode_nom):
    """Génère un rapport HTML complet pour la période sélectionnée"""
    if df.empty:
        return "<p>Aucune donnée pour cette période.</p>"
    
    # Indicateurs
    total_volume = df['volume_m3'].sum()
    total_tonnes = total_volume * 0.8
    total_distance = df['distance'].sum()
    nb_tournees = len(df)
    nb_quartiers = df['quartier'].nunique()
    nb_agents = df['agent'].nunique()
    top_quartier = df.groupby('quartier')['volume_m3'].sum().idxmax() if not df.empty else "N/A"
    top_agent = df.groupby('agent')['volume_m3'].sum().idxmax() if not df.empty else "N/A"
    
    # Évolution quotidienne
    evol_jour = df.groupby('date')['volume_m3'].sum().reset_index()
    fig1 = px.line(evol_jour, x='date', y='volume_m3', title="Volume collecté par jour (m³)", markers=True)
    fig1.update_layout(height=400)
    graph1_html = fig1.to_html(include_plotlyjs='cdn', div_id="graph1")
    
    # Volume par quartier (barres horizontales)
    top_quartiers = df.groupby('quartier')['volume_m3'].sum().sort_values(ascending=False)
    fig2 = px.bar(x=top_quartiers.values, y=top_quartiers.index, orientation='h',
                  title="Volume total par quartier (m³)", text=top_quartiers.values)
    fig2.update_traces(texttemplate='%{text:.1f} m³', textposition='outside')
    fig2.update_layout(height=400)
    graph2_html = fig2.to_html(include_plotlyjs='cdn', div_id="graph2")
    
    # Camembert
    fig3 = px.pie(values=top_quartiers.values, names=top_quartiers.index, title="Répartition des volumes")
    fig3.update_traces(textinfo='percent+label')
    graph3_html = fig3.to_html(include_plotlyjs='cdn', div_id="graph3")
    
    # Tableaux
    tableau_quartiers = df.groupby('quartier').agg({
        'volume_m3': 'sum',
        'distance': 'sum',
        'id': 'count'
    }).round(2)
    tableau_quartiers.columns = ['Volume (m³)', 'Distance (km)', 'Collectes']
    tableau_quartiers['Tonnes'] = (tableau_quartiers['Volume (m³)'] * 0.8).round(1)
    tableau_quartiers = tableau_quartiers.sort_values('Volume (m³)', ascending=False)
    
    tableau_agents = df.groupby('agent').agg({
        'volume_m3': 'sum',
        'id': 'count'
    }).round(2)
    tableau_agents.columns = ['Volume (m³)', 'Collectes']
    tableau_agents['Tonnes'] = (tableau_agents['Volume (m³)'] * 0.8).round(1)
    tableau_agents = tableau_agents.sort_values('Volume (m³)', ascending=False)
    
    # Construction du HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Rapport collectes - {periode_nom}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            h1 {{ color: #2E7D32; border-bottom: 2px solid #2E7D32; padding-bottom: 10px; }}
            h2 {{ color: #1B5E20; margin-top: 30px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .summary {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
            }}
            .metric {{
                flex: 1;
                text-align: center;
                padding: 10px;
                border-right: 1px solid #ddd;
            }}
            .metric:last-child {{ border-right: none; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #2E7D32; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{ background-color: #2E7D32; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .footer {{
                margin-top: 40px;
                text-align: center;
                font-size: 12px;
                color: #666;
                border-top: 1px solid #ddd;
                padding-top: 20px;
            }}
            @media print {{
                body {{ margin: 0; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Rapport de collecte des déchets</h1>
            <p>Commune de Mékhé – Période : {periode_nom}</p>
            <p>Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
        </div>
        
        <div class="summary">
            <div class="metric">
                <div class="metric-value">{total_volume:.1f} m³</div>
                <div>Volume total collecté</div>
                <small>({total_tonnes:.1f} tonnes)</small>
            </div>
            <div class="metric">
                <div class="metric-value">{total_distance:.1f} km</div>
                <div>Distance parcourue</div>
            </div>
            <div class="metric">
                <div class="metric-value">{nb_tournees}</div>
                <div>Tournées effectuées</div>
            </div>
            <div class="metric">
                <div class="metric-value">{nb_quartiers}</div>
                <div>Quartiers visités</div>
            </div>
            <div class="metric">
                <div class="metric-value">{nb_agents}</div>
                <div>Agents actifs</div>
            </div>
        </div>
        
        <div class="info">
            <p><strong>🏆 Quartier le plus productif :</strong> {top_quartier}</p>
            <p><strong>👤 Agent le plus performant :</strong> {top_agent}</p>
            <p><strong>⚡ Efficacité globale :</strong> {(total_distance / total_volume) if total_volume>0 else 0:.2f} km/m³</p>
        </div>
        
        <h2>📈 Évolution quotidienne</h2>
        {graph1_html}
        
        <h2>🏘️ Répartition par quartier</h2>
        {graph2_html}
        {graph3_html}
        
        <h2>📊 Tableau des quartiers</h2>
        {tableau_quartiers.to_html()}
        
        <h2>👥 Performance des agents</h2>
        {tableau_agents.to_html()}
        
        <div class="footer">
            <p>Rapport généré automatiquement par le système de suivi des collectes – Commune de Mékhé</p>
            <p>Les volumes sont exprimés en m³ (1 m³ ≈ 0,8 tonne).</p>
        </div>
    </body>
    </html>
    """
    return html

# ==================== CHARGEMENT DES DONNÉES ====================
with st.spinner("Chargement des données..."):
    df_tournees, df_points = load_all_data()

if df_tournees.empty:
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
    periode = st.selectbox("Période d'analyse", ["Aujourd'hui", "Cette semaine", "Ce mois", "Personnalisé"])
    
    if periode == "Aujourd'hui":
        date_filter = st.date_input("Date", value=date.today())
        df_filtered = df_tournees[df_tournees['date'].dt.date == date_filter]
        periode_nom = date_filter.strftime("%d/%m/%Y")
    elif periode == "Cette semaine":
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        df_filtered = df_tournees[(df_tournees['date'].dt.date >= start_of_week) & (df_tournees['date'].dt.date <= end_of_week)]
        periode_nom = f"Semaine du {start_of_week.strftime('%d/%m')} au {end_of_week.strftime('%d/%m/%Y')}"
    elif periode == "Ce mois":
        today = date.today()
        start_of_month = today.replace(day=1)
        df_filtered = df_tournees[df_tournees['date'].dt.date >= start_of_month]
        periode_nom = f"Mois de {calendar.month_name[today.month]} {today.year}"
    else:
        col1, col2 = st.columns(2)
        with col1:
            date_debut = st.date_input("Date début", value=date.today() - timedelta(days=30))
        with col2:
            date_fin = st.date_input("Date fin", value=date.today())
        df_filtered = df_tournees[(df_tournees['date'].dt.date >= date_debut) & (df_tournees['date'].dt.date <= date_fin)]
        periode_nom = f"Du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
    
    st.markdown("---")
    quartiers = st.multiselect("Quartiers", df_filtered['quartier'].unique(), default=df_filtered['quartier'].unique())
    agents = st.multiselect("Agents", df_filtered['agent'].unique(), default=df_filtered['agent'].unique())
    df_filtered = df_filtered[df_filtered['quartier'].isin(quartiers)]
    df_filtered = df_filtered[df_filtered['agent'].isin(agents)]

# Filtrer les points GPS
ids_tournees = df_filtered['id'].tolist()
df_points_filtre = df_points[df_points['tournee_id'].isin(ids_tournees)]

# ==================== ONGLETS ====================
tabs = st.tabs(["📈 Tableau de bord", "🥇 Classements", "🗺️ Carte", "📋 Détails", "📊 Rapports"])

# ==================== TAB 1 : TABLEAU DE BORD ====================
with tabs[0]:
    st.subheader(f"📅 Période : {periode_nom}")
    if not df_filtered.empty:
        total_volume = df_filtered['volume_m3'].sum()
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
            st.info(f"📊 **Efficacité globale :** {total_distance/total_volume:.2f} km/m³")
        
        st.markdown("---")
        evol_journaliere = df_filtered.groupby('date')['volume_m3'].sum().reset_index()
        fig_evol = px.line(evol_journaliere, x='date', y='volume_m3', title="Volume collecté par jour (m³)", markers=True)
        st.plotly_chart(fig_evol, use_container_width=True)
        
        evol_quartier = df_filtered.groupby(['date', 'quartier'])['volume_m3'].sum().reset_index()
        fig_quartier = px.line(evol_quartier, x='date', y='volume_m3', color='quartier', title="Évolution par quartier (m³)", markers=True)
        fig_quartier.update_layout(height=500)
        st.plotly_chart(fig_quartier, use_container_width=True)
    else:
        st.warning("⚠️ Aucune donnée pour la période sélectionnée")

# ==================== TAB 2 : CLASSEMENTS ====================
with tabs[1]:
    st.subheader("🥇 Classements")
    if not df_filtered.empty:
        col1, col2 = st.columns(2)
        with col1:
            top_quartiers = df_filtered.groupby('quartier')['volume_m3'].sum().sort_values(ascending=True)
            fig_quartiers = px.bar(x=top_quartiers.values, y=top_quartiers.index, orientation='h',
                                   title="Volume total par quartier (m³)", text=top_quartiers.values)
            fig_quartiers.update_traces(texttemplate='%{text:.1f} m³', textposition='outside')
            st.plotly_chart(fig_quartiers, use_container_width=True)
        with col2:
            top_agents = df_filtered.groupby('agent')['volume_m3'].sum().sort_values(ascending=True)
            fig_agents = px.bar(x=top_agents.values, y=top_agents.index, orientation='h',
                                title="Volume total par agent (m³)", text=top_agents.values)
            fig_agents.update_traces(texttemplate='%{text:.1f} m³', textposition='outside')
            st.plotly_chart(fig_agents, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            fig_pie = px.pie(df_filtered, values='volume_m3', names='quartier', title="Répartition des volumes", hole=0.3)
            st.plotly_chart(fig_pie, use_container_width=True)
        with col2:
            perf_df = df_filtered.groupby('quartier').agg({
                'volume_m3': 'sum', 'distance': 'sum', 'id': 'count', 'nb_points': 'sum'
            }).round(2)
            perf_df.columns = ['Volume (m³)', 'Distance (km)', 'Collectes', 'Points GPS']
            perf_df = perf_df.sort_values('Volume (m³)', ascending=False)
            st.dataframe(perf_df, use_container_width=True)
    else:
        st.info("Aucune donnée")

# ==================== TAB 3 : CARTE ====================
with tabs[2]:
    st.subheader("🗺️ Carte des points de collecte")
    if not df_points_filtre.empty:
        collecte_filtre = st.radio("Afficher les points de :", ["Toutes", "Collecte 1", "Collecte 2"], horizontal=True)
        if collecte_filtre == "Collecte 1":
            df_carte = df_points_filtre[df_points_filtre['collecte_numero'] == 1]
        elif collecte_filtre == "Collecte 2":
            df_carte = df_points_filtre[df_points_filtre['collecte_numero'] == 2]
        else:
            df_carte = df_points_filtre
        
        if not df_carte.empty:
            couleurs = {
                "depart_depot": "green", "debut_collecte": "blue", "fin_collecte": "blue",
                "depart_decharge": "orange", "arrivee_decharge": "red", "sortie_decharge": "purple",
                "retour_depot": "brown", "point_libre": "gray"
            }
            noms_points = {
                "depart_depot": "🏭 Départ dépôt", "debut_collecte": "🗑️ Début collecte",
                "fin_collecte": "🗑️ Fin collecte", "depart_decharge": "🚛 Départ décharge",
                "arrivee_decharge": "🏭 Arrivée décharge", "sortie_decharge": "🏭 Sortie décharge",
                "retour_depot": "🏁 Retour dépôt", "point_libre": "📍 Point libre"
            }
            df_carte["nom_affichage"] = df_carte["type_point"].map(noms_points)
            
            fig = px.scatter_mapbox(
                df_carte, lat="latitude", lon="longitude",
                color="type_point", hover_name="nom_affichage",
                hover_data={"quartier": True, "collecte_numero": True, "heure": True},
                color_discrete_map=couleurs,
                zoom=12, center={"lat": 15.11, "lon": -16.65},
                title=f"Itinéraire - {collecte_filtre}",
                height=550
            )
            # Tracer les lignes entre points consécutifs par tournée
            for tid in df_carte['tournee_id'].unique():
                df_tour = df_carte[df_carte['tournee_id'] == tid].sort_values('heure')
                if len(df_tour) > 1:
                    fig.add_trace(go.Scattermapbox(
                        lat=df_tour['latitude'].tolist(),
                        lon=df_tour['longitude'].tolist(),
                        mode='lines+markers',
                        line=dict(width=2, color='blue'),
                        marker=dict(size=6, color='blue'),
                        name=f'Trajet {tid}',
                        showlegend=False
                    ))
            fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":40,"l":0,"b":0})
            st.plotly_chart(fig, use_container_width=True)
            
            # Distances
            st.subheader("📏 Distances entre points consécutifs")
            distances = []
            for tid in df_carte['tournee_id'].unique():
                df_tour = df_carte[df_carte['tournee_id'] == tid].sort_values('heure')
                if len(df_tour) > 1:
                    for i in range(1, len(df_tour)):
                        p1 = df_tour.iloc[i-1]
                        p2 = df_tour.iloc[i]
                        d = haversine(p1['latitude'], p1['longitude'], p2['latitude'], p2['longitude'])
                        distances.append({
                            "Tournée": tid,
                            "De": p1['nom_affichage'],
                            "À": p2['nom_affichage'],
                            "Distance (km)": round(d, 2)
                        })
            if distances:
                st.dataframe(pd.DataFrame(distances), use_container_width=True)
                st.info(f"**Distance totale calculée :** {sum(d['Distance (km)'] for d in distances):.2f} km")
        else:
            st.info("Aucun point GPS pour la collecte sélectionnée")
    else:
        st.info("Aucun point GPS enregistré pour la période")

# ==================== TAB 4 : DÉTAILS ====================
with tabs[3]:
    st.subheader("📋 Détail des collectes")
    if not df_filtered.empty:
        display_df = df_filtered.copy()
        display_df['date'] = display_df['date'].dt.strftime('%d/%m/%Y')
        display_df['volume_m3'] = display_df['volume_m3'].apply(lambda x: f"{x:.1f} m³")
        display_df['distance'] = display_df['distance'].apply(lambda x: f"{x:.1f} km")
        display_df['volume_collecte1'] = display_df['volume_collecte1'].apply(lambda x: f"{x:.1f} m³")
        display_df['volume_collecte2'] = display_df['volume_collecte2'].apply(lambda x: f"{x:.1f} m³")
        
        st.dataframe(
            display_df[['date', 'quartier', 'agent', 'equipe', 'volume_collecte1', 'volume_collecte2', 'volume_m3', 'distance', 'nb_points']],
            use_container_width=True,
            column_config={
                "date": "Date", "quartier": "Quartier", "agent": "Agent", "equipe": "Équipe",
                "volume_collecte1": "Volume 1", "volume_collecte2": "Volume 2",
                "volume_m3": "Volume total", "distance": "Distance", "nb_points": "Points GPS"
            }
        )
        
        # Export Excel (simple)
        st.markdown("---")
        st.subheader("📥 Export des données")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 EXPORTER EN EXCEL", use_container_width=True):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    display_df.to_excel(writer, sheet_name="Collectes", index=False)
                st.download_button("📥 Télécharger Excel", data=output.getvalue(),
                                   file_name=f"collectes_{datetime.now().strftime('%Y%m%d')}.xlsx")
    else:
        st.info("Aucune donnée pour cette période")

# ==================== TAB 5 : RAPPORTS (HEBDOMADAIRES / MENSUELS / ANNUELS) ====================
with tabs[4]:
    st.subheader("📊 Génération de rapports (PDF imprimable)")
    col1, col2 = st.columns(2)
    with col1:
        type_rapport = st.selectbox("Type de rapport", ["Hebdomadaire", "Mensuel", "Annuel"])
    with col2:
        if type_rapport == "Hebdomadaire":
            annee = st.selectbox("Année", sorted(df_tournees['annee'].unique(), reverse=True))
            semaine = st.selectbox("Semaine", sorted(df_tournees[df_tournees['annee']==annee]['semaine'].unique()))
            df_rapport = df_tournees[(df_tournees['annee'] == annee) & (df_tournees['semaine'] == semaine)]
            periode_nom_rapport = f"Semaine {semaine} - {annee}"
        elif type_rapport == "Mensuel":
            annee = st.selectbox("Année", sorted(df_tournees['annee'].unique(), reverse=True))
            mois = st.selectbox("Mois", sorted(df_tournees[df_tournees['annee']==annee]['mois'].unique()))
            nom_mois = calendar.month_name[mois]
            df_rapport = df_tournees[(df_tournees['annee'] == annee) & (df_tournees['mois'] == mois)]
            periode_nom_rapport = f"{nom_mois} {annee}"
        else:  # Annuel
            annee = st.selectbox("Année", sorted(df_tournees['annee'].unique(), reverse=True))
            df_rapport = df_tournees[df_tournees['annee'] == annee]
            periode_nom_rapport = f"Année {annee}"
    
    if not df_rapport.empty:
        st.info(f"**{len(df_rapport)} tournée(s)** trouvée(s) pour la période")
        if st.button("📥 Générer le rapport HTML", use_container_width=True):
            html_content = generer_rapport_html(df_rapport, periode_nom_rapport)
            st.download_button(
                label="📄 Télécharger le rapport (HTML)",
                data=html_content,
                file_name=f"rapport_collectes_{periode_nom_rapport.replace(' ', '_')}.html",
                mime="text/html"
            )
            st.success("Rapport généré ! Ouvrez-le dans votre navigateur, puis utilisez Ctrl+P pour l'enregistrer en PDF.")
    else:
        st.warning("Aucune donnée pour la période sélectionnée")

# ==================== FOOTER ====================
st.markdown("---")
st.caption(f"📊 Dernière mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Données en temps réel | Unité : m³ | Commune de Mékhé")
