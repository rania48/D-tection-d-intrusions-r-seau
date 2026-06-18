import streamlit as st
import pandas as pd
from pymongo import MongoClient
import plotly.express as px
import time
from datetime import datetime

# Setup page config
st.set_page_config(
    page_title="IDS Real-time Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a premium look
st.markdown("""
<style>
    /* Main container background */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* Header customizations */
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* KPI Card styling */
    .kpi-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        transition: transform 0.2s, border-color 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: #58a6ff;
    }
    .kpi-title {
        font-size: 0.85rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to render metric card
def render_metric_card(title, value, color, icon=""):
    return f"""
    <div class="kpi-card">
        <div class="kpi-title">{icon} {title}</div>
        <div class="kpi-value" style="color: {color};">{value}</div>
    </div>
    """

# Standard CIC-IDS2017 label mapping
ATTACK_LABELS_MAP = {
    "0": "Normal (Benign)",
    "1": "DDoS",
    "2": "PortScan",
    "3": "Botnet",
    "4": "Infiltration",
    "5": "Web Attack – Brute Force",
    "6": "Web Attack – XSS",
    "7": "Web Attack – Sql Injection",
    "8": "FTP-Patator",
    "9": "SSH-Patator",
    "10": "DoS GoldenEye",
    "11": "DoS Hulk",
    "12": "DoS Slowhttptest",
    "13": "DoS slowloris",
    "14": "Heartbleed",
    "None": "None",
    "unknown": "Inconnu"
}

# Sidebar configuration
st.sidebar.image("https://img.icons8.com/nolan/96/shield.png", width=70)
st.sidebar.title("Configuration")

mongo_uri = st.sidebar.text_input("URI MongoDB", "mongodb://localhost:27017/")
db_name = st.sidebar.text_input("Base de données", "ids_db")
collection_name = st.sidebar.text_input("Collection", "predictions")

# Auto refresh configuration
st.sidebar.markdown("---")
st.sidebar.subheader("Rafraîchissement")
auto_refresh = st.sidebar.checkbox("Rafraîchissement automatique", value=True)
refresh_interval = st.sidebar.slider("Intervalle (secondes)", min_value=1, max_value=30, value=3)

# Data Retrieval function
def load_data(uri, database, collection):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        client.server_info()  # Force connection verification
        db = client[database]
        col = db[collection]
        cursor = col.find()
        df = pd.DataFrame(list(cursor))
        return df, True, None
    except Exception as e:
        return pd.DataFrame(), False, str(e)

# Manual refresh button in sidebar
if st.sidebar.button("🔄 Actualiser maintenant", use_container_width=True):
    st.rerun()

# Database Purge Option (Helper tool)
if st.sidebar.checkbox("Options de nettoyage"):
    st.sidebar.warning("Purge de la base de données predictions.")
    if st.sidebar.button("⚠️ Vider la collectionpredictions", use_container_width=True):
        try:
            client = MongoClient(mongo_uri)
            client[db_name][collection_name].drop()
            st.sidebar.success("Collection predictions vidée avec succès !")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Erreur : {e}")

# Header
st.markdown("<h1 style='text-align: center; margin-bottom: 25px;'>🛡️ IDS Real-time Monitoring Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #8b949e; font-size: 1.1rem; margin-top:-20px; margin-bottom: 30px;'>Visualisation en temps réel du trafic réseau et détection d'intrusions (CIC-IDS2017)</p>", unsafe_allow_html=True)

# Fetch data
df, connected, error_msg = load_data(mongo_uri, db_name, collection_name)

if not connected:
    st.sidebar.error("🔴 MongoDB Déconnecté")
    st.error(f"### ❌ Impossible de se connecter à MongoDB\n**Détail de l'erreur :** `{error_msg}`")
    st.info("💡 Veuillez vérifier que votre serveur MongoDB est en cours d'exécution sur le port 27017.")
else:
    st.sidebar.success("🟢 MongoDB Connecté")

    # If the collection is empty
    if df.empty:
        # Display empty state KPI cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(render_metric_card("Total Flux", 0, "#58a6ff", "📊"), unsafe_allow_html=True)
        with col2:
            st.markdown(render_metric_card("Normal", 0, "#2ea043", "🟢"), unsafe_allow_html=True)
        with col3:
            st.markdown(render_metric_card("Attack", 0, "#f85149", "🔴"), unsafe_allow_html=True)
        with col4:
            st.markdown(render_metric_card("Types d'Attaque", 0, "#ab7df8", "🔥"), unsafe_allow_html=True)
            
        st.markdown("---")
        st.info("ℹ️ **Aucune donnée disponible pour le moment.** La collection MongoDB `predictions` est vide.\n\nVeuillez démarrer votre **Producer Kafka** et le **Spark Structured Streaming** pour alimenter la base de données.")
        st.markdown(
            """
            <div style="background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-top: 20px;">
                <h4 style="margin-top: 0; color: #ffffff;">⚙️ Instructions de démarrage rapide</h4>
                <ol>
                    <li>Démarrer Zookeeper et Kafka</li>
                    <li>Lancer le Producer : <code style="color: #ff7b72;">python producer/kafka_producer.py</code></li>
                    <li>Lancer Spark Streaming : <code style="color: #ff7b72;">spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.x.x spark/spark_streaming_prediction.py</code></li>
                </ol>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        # Preprocessing
        if '_id' in df.columns:
            df = df.drop(columns=['_id'])
            
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
        # Calculation of KPIs
        total_flows = len(df)
        normal_flows = len(df[df['status'] == 'NORMAL'])
        attack_flows = len(df[df['status'] == 'ATTACK'])
        
        # Unique attack types excluding None or NORMAL
        attack_types_df = df[(df['status'] == 'ATTACK') & (df['attack_type'] != 'None')]
        unique_attack_types = attack_types_df['attack_type'].nunique()
        
        # Render KPIs
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(render_metric_card("Total Flux", f"{total_flows:,}", "#58a6ff", "📊"), unsafe_allow_html=True)
        with col2:
            st.markdown(render_metric_card("Normal", f"{normal_flows:,}", "#2ea043", "🟢"), unsafe_allow_html=True)
        with col3:
            st.markdown(render_metric_card("Attack", f"{attack_flows:,}", "#f85149", "🔴"), unsafe_allow_html=True)
        with col4:
            st.markdown(render_metric_card("Types d'Attaque", unique_attack_types, "#ab7df8", "🔥"), unsafe_allow_html=True)
            
        st.markdown("---")
        
        # Charts section
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.subheader("📊 Répartition Globale (NORMAL vs ATTACK)")
            status_counts = df['status'].value_counts().reset_index()
            status_counts.columns = ['Statut', 'Nombre']
            
            fig_pie = px.pie(
                status_counts,
                names='Statut',
                values='Nombre',
                hole=0.4,
                color='Statut',
                color_discrete_map={'NORMAL': '#2ea043', 'ATTACK': '#f85149'},
                template="plotly_dark"
            )
            fig_pie.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=20, b=20, l=20, r=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with chart_col2:
            st.subheader("🔥 Répartition des Types d'Attaques (XGBoost)")
            if not attack_types_df.empty:
                # Map codes to human readable
                attack_types_mapped = attack_types_df.copy()
                attack_types_mapped['attack_name'] = attack_types_mapped['attack_type'].map(
                    lambda x: f"{ATTACK_LABELS_MAP.get(str(x), str(x))} (Code {x})" if str(x) != "None" else "None"
                )
                
                attack_counts = attack_types_mapped['attack_name'].value_counts().reset_index()
                attack_counts.columns = ["Type d'Attaque", 'Nombre']
                
                # Sort ascending for horizontal bar chart
                attack_counts = attack_counts.sort_values(by='Nombre', ascending=True)
                
                fig_bar = px.bar(
                    attack_counts,
                    y="Type d'Attaque",
                    x='Nombre',
                    orientation='h',
                    color='Nombre',
                    color_continuous_scale='Reds',
                    template="plotly_dark"
                )
                fig_bar.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=True, gridcolor='#30363d'),
                    yaxis=dict(showgrid=False),
                    margin=dict(t=20, b=20, l=20, r=20),
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Aucune attaque détectée pour le moment. En attente de trafic malveillant...")

        st.markdown("---")
        
        # Recent Alerts Section
        st.subheader("🚨 Dernières Alertes & Prédictions")
        
        # Filter table option
        view_filter = st.radio(
            "Filtrer le tableau",
            ["Toutes les prédictions", "Alertes d'attaques uniquement"],
            horizontal=True
        )
        
        # Sort by timestamp descending to show latest first
        table_df = df.sort_values(by='timestamp', ascending=False)
        
        if view_filter == "Alertes d'attaques uniquement":
            table_df = table_df[table_df['status'] == 'ATTACK']
            
        # Select latest 100 entries
        display_df = table_df.head(100).copy()
        
        if not display_df.empty:
            # Format datetime
            display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Map columns for better visibility
            display_df['true_label'] = display_df['true_label'].map(
                lambda x: f"{ATTACK_LABELS_MAP.get(str(x), str(x))} ({x})" if str(x) != "None" else "None"
            )
            display_df['rf_prediction'] = display_df['rf_prediction'].map(
                lambda x: f"{ATTACK_LABELS_MAP.get(str(x), str(x))} ({x})" if str(x) != "None" else "None"
            )
            display_df['attack_type'] = display_df['attack_type'].map(
                lambda x: f"{ATTACK_LABELS_MAP.get(str(x), str(x))} ({x})" if str(x) != "None" else "None"
            )
            
            # Style helper
            def highlight_status(row):
                styles = [''] * len(row)
                status_idx = row.index.get_loc('status')
                if row['status'] == 'ATTACK':
                    styles[status_idx] = 'background-color: rgba(248, 81, 73, 0.2); color: #ff7b72; font-weight: bold;'
                else:
                    styles[status_idx] = 'background-color: rgba(46, 160, 67, 0.2); color: #56d364;'
                return styles
            
            # Show dataframe with styled status column
            if hasattr(display_df.style, 'map'):
                styled_table = display_df.style.apply(highlight_status, axis=1)
            else:
                styled_table = display_df.style.apply(highlight_status, axis=1)
                
            st.dataframe(
                styled_table,
                column_config={
                    "timestamp": "Horodatage",
                    "flow_id": "ID Flux",
                    "true_label": "Vraie Classe",
                    "rf_prediction": "Préd. Random Forest",
                    "status": "Statut final",
                    "attack_type": "Classe d'Attaque (XGBoost)",
                    "model_used": "Modèle Utilisé"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aucun enregistrement ne correspond aux critères de filtrage.")

# Handle auto-refresh rerun loop
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
