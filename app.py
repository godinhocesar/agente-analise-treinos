import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta, datetime
import requests
# Bibliotecas do Firebase
import google.cloud.firestore
from google.oauth2 import service_account

# --- Configurações Iniciais ---
try:
    STRAVA_CLIENT_ID = st.secrets["strava"]["client_id"]
    STRAVA_CLIENT_SECRET = st.secrets["strava"]["client_secret"]
except (KeyError, FileNotFoundError):
    st.error("As chaves do Strava não foram encontradas nos segredos. Verifique o seu ficheiro .streamlit/secrets.toml.")
    st.stop()

REDIRECT_URI = "http://localhost:8501"

# --- Funções de Análise e API ---
def calcular_velocidade_e_pace(df):
    if 'timestamp' not in df.columns or 'distancia_m' not in df.columns:
        return df
    df_calc = df.copy()
    df_calc.dropna(subset=['timestamp', 'distancia_m'], inplace=True)
    df_calc['delta_distancia_m'] = df_calc['distancia_m'].diff()
    df_calc['delta_tempo_s'] = df_calc['timestamp'].diff().dt.total_seconds()
    df_calc['velocidade_ms'] = df_calc['delta_distancia_m'] / df_calc['delta_tempo_s']
    df_calc.replace([np.inf, -np.inf], np.nan, inplace=True)
    df_calc['velocidade_ms'] = df_calc['velocidade_ms'].ffill()
    df_calc.dropna(subset=['velocidade_ms'], inplace=True)
    df_calc['pace_min_km'] = 16.667 / df_calc['velocidade_ms']
    return df_calc

def analisar_zonas_fc(df, fc_maxima):
    if 'fc_bpm' not in df.columns or 'timestamp' not in df.columns:
        return pd.Series(dtype='float64')
    df_fc = df.dropna(subset=['timestamp', 'fc_bpm']).copy()
    if df_fc.empty: return pd.Series(dtype='float64')
    df_fc['delta_tempo_s'] = df_fc['timestamp'].diff().dt.total_seconds()
    df_fc['delta_tempo_s'].fillna(1, inplace=True)
    zonas_limites = [0, fc_maxima * 0.6, fc_maxima * 0.7, fc_maxima * 0.8, fc_maxima * 0.9, fc_maxima * 2]
    zonas_labels = ["Z1 - Muito Leve", "Z2 - Leve", "Z3 - Moderado", "Z4 - Difícil", "Z5 - Máximo"]
    df_fc['zona_fc'] = pd.cut(df_fc['fc_bpm'], bins=zonas_limites, labels=zonas_labels, right=False, include_lowest=True)
    tempo_por_zona = df_fc.groupby('zona_fc', observed=False)['delta_tempo_s'].sum()
    return tempo_por_zona

def plotar_grafico(df):
    if 'distancia_m' not in df.columns or 'velocidade_ms' not in df.columns:
        return None
    df_plot = df.dropna(subset=['distancia_m', 'velocidade_ms']).copy()
    df_plot['distancia_km'] = df_plot['distancia_m'] / 1000.0
    if 'pace_min_km' not in df_plot.columns: return None
    df_plot['pace_suavizado'] = df_plot['pace_min_km'].rolling(window=30, min_periods=1).mean()
    df_plot = df_plot[(df_plot['pace_suavizado'] < 15) & (df_plot['pace_suavizado'] > 2)]
    
    fig, ax1 = plt.subplots(figsize=(15, 7))
    plt.title('Análise do Treino por Distância', fontsize=16)
    
    color = 'tab:blue'
    ax1.set_xlabel('Distância (km)')
    ax1.set_ylabel('Pace (min/km)', color=color, fontsize=12)
    ax1.fill_between(df_plot['distancia_km'], df_plot['pace_suavizado'], 8.0, color=color, alpha=0.8, label='Pace (Suavizado)')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.invert_yaxis()
    ax1.set_ylim(8.0, 3.0)

    lines, labels = ax1.get_legend_handles_labels()
    
    has_fc_plot = 'fc_bpm' in df_plot.columns and df_plot['fc_bpm'].notna().sum() > 1
    has_cadence_plot = 'cadencia_spm' in df_plot.columns and df_plot['cadencia_spm'].notna().sum() > 50

    if has_fc_plot or has_cadence_plot:
        ax2 = ax1.twinx()
        if has_fc_plot:
            color_fc = 'tab:red'
            ax2.set_ylabel('FC (bpm)', color=color_fc, fontsize=12)
            ax2.plot(df_plot['distancia_km'], df_plot['fc_bpm'], color=color_fc, alpha=0.9, label='Frequência Cardíaca')
            ax2.tick_params(axis='y', labelcolor=color_fc)
            lines2, labels2 = ax2.get_legend_handles_labels()
            lines.extend(lines2)
            labels.extend(labels2)

        if has_cadence_plot:
            if 'ax2' not in locals():
                ax2 = ax1.twinx()
            
            line_cad = ax2.plot(df_plot['distancia_km'], df_plot['cadencia_spm'], color='tab:green', linestyle='--', label='Cadência')
            lines.append(line_cad[0])
            labels.append('Cadência')

    fig.tight_layout()
    ax1.legend(lines, labels, loc='best')
    return fig

def calcular_parciais_km(df):
    if 'delta_tempo_s' not in df.columns or 'distancia_m' not in df.columns:
        return pd.DataFrame()
    df_parciais = df.dropna(subset=['delta_tempo_s', 'distancia_m']).copy()
    if df_parciais.empty: return pd.DataFrame()
    df_parciais['km_atual'] = (df_parciais['distancia_m'] // 1000).astype(int)
    parciais = []
    tempo_acumulado = 0
    km_max = int(df_parciais['distancia_m'].max() // 1000)
    for km in range(km_max + 1):
        dados_km = df_parciais[df_parciais['km_atual'] == km]
        if not dados_km.empty:
            tempo_parcial = dados_km['delta_tempo_s'].sum()
            tempo_acumulado += tempo_parcial
            fc_media_parcial = dados_km['fc_bpm'].mean() if 'fc_bpm' in dados_km.columns and dados_km['fc_bpm'].notna().any() else 'N/A'
            pace_min = int(tempo_parcial // 60)
            pace_seg = int(tempo_parcial % 60)
            parciais.append({
                "Km": f"{km + 1}", "Ritmo": f"{pace_min:02d}'{pace_seg:02d}\"",
                "FC Média": f"{fc_media_parcial:.0f}" if isinstance(fc_media_parcial, (int, float)) else "N/A",
                "Tempo Acumulado": formatar_tempo_hms(tempo_acumulado)
            })
    return pd.DataFrame(parciais)

def formatar_tempo_min_seg(segundos):
    minutos = int(segundos // 60)
    segundos = int(segundos % 60)
    return f"{minutos:02d}:{segundos:02d}"

def formatar_tempo_hms(segundos):
    return str(timedelta(seconds=int(segundos)))

@st.cache_data(ttl=600)
def get_strava_activities(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://www.strava.com/api/v3/athlete/activities', headers=headers)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=3600)
def get_activity_streams(activity_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    keys = 'time,distance,heartrate,cadence,altitude'
    response = requests.get(f'https://www.strava.com/api/v3/activities/{activity_id}/streams?keys={keys}&key_by_type=true', headers=headers)
    response.raise_for_status()
    return response.json()

def process_strava_streams(streams, start_date):
    data_dict = {}
    time_data = streams.get('time', {}).get('data', [])
    if not time_data:
        return pd.DataFrame()
    start_timestamp = int(start_date.timestamp())
    data_dict['timestamp'] = [datetime.fromtimestamp(start_timestamp + t) for t in time_data]
    base_len = len(data_dict['timestamp'])

    for key, stream_name in [('distancia_m', 'distance'), ('fc_bpm', 'heartrate'), ('cadencia_spm', 'cadence'), ('altitude_m', 'altitude')]:
        stream_data = streams.get(stream_name, {}).get('data', [])
        if len(stream_data) == base_len:
            data_dict[key] = stream_data
    
    df = pd.DataFrame(data_dict)
    
    if 'cadencia_spm' in df.columns and df['cadencia_spm'].notna().any():
        df['cadencia_spm'] = df['cadencia_spm'] * 2
    return df

def gerar_analise_ia(tempo_por_zona, df_parciais):
    if tempo_por_zona is None or tempo_por_zona.empty:
        return "- Não foi possível gerar a análise do treinador pois não há dados de Frequência Cardíaca para este treino."
    
    analise = []
    total_tempo = tempo_por_zona.sum()
    
    tempo_z4_z5 = tempo_por_zona.get("Z4 - Difícil", 0) + tempo_por_zona.get("Z5 - Máximo", 0)
    percentual_alta_intensidade = (tempo_z4_z5 / total_tempo) * 100 if total_tempo > 0 else 0
    
    tipo_treino = "de intensidade moderada"
    if percentual_alta_intensidade > 40:
        tipo_treino = "de alta intensidade (Tiros/Variação)"
    elif percentual_alta_intensidade < 20:
        tipo_treino = "de baixa intensidade (Leve/Regenerativo)"

    analise.append(f"**Diagnóstico do Treino:** Este foi um treino {tipo_treino}, com **{percentual_alta_intensidade:.0f}%** do tempo gasto em zonas de esforço elevadas.")

    if not df_parciais.empty and len(df_parciais) > 2:
        parciais_seg = df_parciais['Ritmo'].str.extract(r"(\d+)'(\d+)\"").astype(int)
        parciais_seg['total_s'] = parciais_seg[0] * 60 + parciais_seg[1]
        desvio_padrao = parciais_seg['total_s'].std()
        
        if desvio_padrao < 15:
             analise.append("**Análise de Ritmo:** O seu ritmo foi **extremamente consistente** ao longo do treino. Excelente controlo de esforço!")
        elif desvio_padrao < 30:
             analise.append("**Análise de Ritmo:** O seu ritmo foi **consistente**, com pequenas variações. Bom trabalho na gestão de energia.")
        else:
             analise.append("**Análise de Ritmo:** O seu ritmo apresentou **variações significativas**, o que pode indicar um treino intervalado ou um percurso com muitas subidas.")

    if tipo_treino.startswith("de alta intensidade"):
        analise.append("**Recomendação do Treinador:** Excelente trabalho! Após um estímulo tão forte, a prioridade máxima para o seu próximo treino é a **recuperação**. Foque num treino de rodagem muito leve, mantendo a sua FC na Zona 2.")
    elif tipo_treino.startswith("de baixa intensidade"):
         analise.append("**Recomendação do Treinador:** Missão cumprida! Este treino de baixa intensidade é fundamental para construir a sua base aeróbica e permitir que o corpo se recupere. É este tipo de treino que o prepara para os dias de maior esforço.")

    return "\n\n".join(f"- {item}" for item in analise)

@st.cache_resource
def init_firestore_connection():
    creds_dict = st.secrets["firebase_credentials"]
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    db = google.cloud.firestore.Client(credentials=creds)
    return db

def save_analysis_to_firestore(db, user_id, activity_id, metrics):
    doc_ref = db.collection("users").document(str(user_id)).collection("activities").document(str(activity_id))
    doc_ref.set(metrics)

@st.cache_data(ttl=300)
def get_analyses_from_firestore(_db, user_id):
    activities_ref = _db.collection("users").document(str(user_id)).collection("activities")
    all_activities = [doc.to_dict() for doc in activities_ref.stream()]
    
    if not all_activities: return pd.DataFrame()
        
    df = pd.DataFrame(all_activities)
    df['activity_date'] = pd.to_datetime(df['activity_date'])
    df.sort_values(by='activity_date', ascending=False, inplace=True)
    return df

st.set_page_config(page_title="Plataforma de Treino Inteligente", layout="wide")
db = init_firestore_connection()

st.title("🏃‍♂️ Plataforma de Treino Inteligente")

if 'strava_token' not in st.session_state:
    query_params = st.query_params
    auth_code = query_params.get("code")
    if auth_code:
        try:
            response = requests.post('https://www.strava.com/oauth/token', data={'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 'code': auth_code, 'grant_type': 'authorization_code'})
            response.raise_for_status()
            token_data = response.json()
            st.session_state['strava_token'] = token_data
            st.success("Conexão com o Strava bem-sucedida! A página será recarregada.")
            st.query_params.clear()
            st.rerun()
        except requests.exceptions.RequestException as e:
            st.error(f"Ocorreu um erro ao conectar com o Strava: {e}")
    else:
        st.info("Para começar, conecte a sua conta do Strava para importar os seus treinos automaticamente.")
        auth_url = (f"https://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=activity:read_all")
        st.link_button("Conectar com o Strava", auth_url, use_container_width=True)
else:
    token_info = st.session_state['strava_token']
    access_token = token_info['access_token']
    athlete_name = token_info.get('athlete', {}).get('firstname', 'Atleta')
    user_id = token_info.get('athlete', {}).get('id')
    
    st.header(f"Bem-vindo, {athlete_name}!")

    tab1, tab2 = st.tabs(["📊 Análise de Treino", "📈 Dashboard de Progresso"])

    with tab1:
        st.write("Selecione um treino do Strava para uma análise detalhada.")
        try:
            activities = get_strava_activities(access_token)
            run_activities = [act for act in activities if act['type'] == 'Run']
            if not run_activities:
                st.warning("Nenhuma atividade de corrida encontrada nos seus treinos recentes do Strava.")
            else:
                activity_options = {f"{datetime.fromisoformat(act['start_date_local'].replace('Z', '')).strftime('%d/%m/%Y')} - {act['name']} ({act.get('distance', 0)/1000:.2f} km)": act for act in run_activities}
                selected_activity_name = st.selectbox("Seus treinos de corrida recentes:", options=["Selecione um treino"] + list(activity_options.keys()))
                if selected_activity_name and selected_activity_name != "Selecione um treino":
                    selected_activity = activity_options[selected_activity_name]
                    activity_id = selected_activity['id']
                    start_date = datetime.fromisoformat(selected_activity['start_date_local'].replace('Z', ''))
                    st.header(f"Análise Detalhada: {selected_activity_name}")
                    
                    with st.spinner(f"A analisar o seu treino..."):
                        streams = get_activity_streams(activity_id, access_token)
                        df = process_strava_streams(streams, start_date)
                        
                        if df.empty or 'timestamp' not in df.columns:
                             st.error("Não foi possível processar os dados desta atividade. Os fluxos de dados essenciais (como o tempo) podem estar em falta.")
                        else:
                            df_com_pace = calcular_velocidade_e_pace(df)
                            
                            st.subheader("Painel de Métricas Gerais")
                            has_dist = 'distancia_m' in df_com_pace.columns and not df_com_pace.empty
                            has_fc = 'fc_bpm' in df_com_pace.columns and df_com_pace['fc_bpm'].notna().any()
                            has_cadence = 'cadencia_spm' in df_com_pace.columns and df_com_pace['cadencia_spm'].notna().any()
                            has_altitude = 'altitude_m' in df_com_pace.columns and df_com_pace['altitude_m'].notna().any()
                            
                            tempo_total = (df_com_pace['timestamp'].iloc[-1] - df_com_pace['timestamp'].iloc[0]).total_seconds()
                            distancia_total_km = df_com_pace['distancia_m'].iloc[-1] / 1000.0 if has_dist else selected_activity.get('distance', 0) / 1000.0
                            pace_medio_decimal = tempo_total / 60 / distancia_total_km if distancia_total_km > 0 else 0
                            
                            fc_media = df_com_pace['fc_bpm'].mean() if has_fc else 0
                            fc_max = df_com_pace['fc_bpm'].max() if has_fc else 0
                            cad_media = df_com_pace['cadencia_spm'].mean() if has_cadence else 0
                            cad_max = df_com_pace['cadencia_spm'].max() if has_cadence else 0
                            velocidade_media_ms = df_com_pace['velocidade_ms'].mean() if 'velocidade_ms' in df_com_pace.columns else 0
                            pernada_media_cm = (velocidade_media_ms / (cad_media / 120)) * 100 if cad_media > 0 and velocidade_media_ms > 0 else 0
                            ascensao_total = df_com_pace['altitude_m'].diff().clip(lower=0).sum() if has_altitude else 0
                            
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Tempo Total", formatar_tempo_hms(tempo_total))
                            col2.metric("Distância", f"{distancia_total_km:.2f} km")
                            col3.metric("Pace Médio", f"{int(pace_medio_decimal)}:{int((pace_medio_decimal*60)%60):02d} /km" if pace_medio_decimal > 0 else "N/A")
                            col4.metric("Ascensão Total", f"{ascensao_total:.0f} m" if has_altitude else "N/A")
                            col1_fc, col2_fc, col3_cad, col4_cad = st.columns(4)
                            col1_fc.metric("FC Média", f"{fc_media:.0f} bpm" if has_fc else "N/A")
                            col2_fc.metric("FC Máxima", f"{fc_max:.0f} bpm" if has_fc else "N/A")
                            col3_cad.metric("Cadência Média", f"{cad_media:.0f} spm" if has_cadence else "N/A")
                            col4_cad.metric("Pernada Média", f"{pernada_media_cm:.0f} cm" if pernada_media_cm > 0 else "N/A")

                            st.subheader("Análise de Ritmo por Quilómetro (Parciais)")
                            df_parciais = calcular_parciais_km(df_com_pace)
                            if not df_parciais.empty:
                                st.dataframe(df_parciais.set_index('Km'), use_container_width=True)
                            else:
                                st.info("Não há dados de distância suficientes para calcular as parciais por quilómetro.")

                            st.subheader("Gráfico de Desempenho por Distância")
                            figura = plotar_grafico(df_com_pace)
                            if figura:
                                st.pyplot(figura)
                            else:
                                st.info("Não há dados de distância e ritmo suficientes para gerar o gráfico de desempenho.")

                            st.subheader("Análise de Esforço: Zonas de Frequência Cardíaca")
                            if has_fc:
                                fc_max_input = st.number_input("Informe sua Frequência Cardíaca Máxima (bpm):", min_value=100, max_value=250, value=192)
                                tempo_por_zona = analisar_zonas_fc(df, fc_max_input)
                                if not tempo_por_zona.empty:
                                    st.subheader("Tempo em Cada Zona de Esforço")
                                    total_tempo = tempo_por_zona.sum()
                                    tabela_zonas = pd.DataFrame(tempo_por_zona).reset_index()
                                    tabela_zonas.columns = ['Zona', 'Tempo (s)']
                                    tabela_zonas['Tempo'] = tabela_zonas['Tempo (s)'].apply(formatar_tempo_min_seg)
                                    tabela_zonas['Percentual'] = (tabela_zonas['Tempo (s)'] / total_tempo * 100).map('{:.1f}%'.format)
                                    tabela_zonas.set_index('Zona', inplace=True)
                                    st.table(tabela_zonas[['Tempo', 'Percentual']])
                            else:
                                tempo_por_zona = None
                                st.info("Não há dados de Frequência Cardíaca para este treino.")
                            
                            st.subheader("🤖 Análise do Treinador de IA")
                            analise_texto = gerar_analise_ia(tempo_por_zona, df_parciais)
                            st.markdown(analise_texto)

                            metrics_to_save = {
                                "activity_name": selected_activity_name, "activity_date": start_date,
                                "distancia_km": float(distancia_total_km), "tempo_total_s": float(tempo_total),
                                "pace_medio_min_km": float(pace_medio_decimal) if pace_medio_decimal > 0 else 0.0, 
                                "fc_media": float(fc_media) if has_fc else 0.0,
                                "fc_max": int(fc_max) if has_fc and pd.notna(fc_max) else 0, 
                                "cadencia_media": float(cad_media) if has_cadence else 0.0,
                                "ascensao_total_m": float(ascensao_total) if has_altitude else 0.0,
                                "analise_ia": analise_texto
                            }
                            if st.button("Guardar Análise na Base de Dados"):
                                with st.spinner("A guardar..."):
                                    save_analysis_to_firestore(db, user_id, activity_id, metrics_to_save)
                                    st.success("Análise guardada com sucesso!")

        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code == 401:
                st.error("Sua conexão com o Strava expirou. Por favor, conecte-se novamente.")
                del st.session_state['strava_token']
                if st.button("Reconectar ao Strava"):
                    st.rerun()
            else:
                st.error(f"Ocorreu um erro ao buscar suas atividades do Strava: {e}")

    with tab2:
        st.subheader("Seu Histórico de Treinos Analisados")
        with st.spinner("A carregar o seu histórico da base de dados..."):
            history_df = get_analyses_from_firestore(db, user_id)

        if history_df.empty:
            st.info("Ainda não há treinos guardados na sua base de dados. Analise um treino e clique em 'Guardar' para começar a construir o seu histórico.")
        else:
            st.write("Aqui está um resumo de todos os treinos que você guardou:")
            
            display_df = history_df.copy()
            display_df['Data'] = display_df['activity_date'].dt.strftime('%d/%m/%Y')
            display_df['Distância (km)'] = display_df['distancia_km'].map('{:.2f}'.format)
            display_df['Pace Médio'] = display_df['pace_medio_min_km'].apply(lambda x: f"{int(x)}:{int((x*60)%60):02d}" if x > 0 else "N/A")
            display_df['FC Média'] = display_df['fc_media'].apply(lambda x: f"{x:.0f}" if x > 0 else "N/A")
            
            st.dataframe(display_df[['Data', 'Distância (km)', 'Pace Médio', 'FC Média']], use_container_width=True)

            st.subheader("Evolução da Distância dos Treinos")
            evolution_df = history_df.set_index('activity_date').sort_index()
            st.line_chart(evolution_df['distancia_km'])

            st.subheader("Evolução do Pace Médio nos Treinos Longos (>= 7km)")
            
            long_runs_df = history_df[history_df['distancia_km'] >= 7.0].copy()
            
            if long_runs_df.empty or len(long_runs_df) < 2:
                st.info("Ainda não há treinos longos suficientes (pelo menos 2 treinos com >= 7km) para gerar um gráfico de evolução de pace.")
            else:
                long_runs_df.sort_values(by='activity_date', inplace=True)
                
                fig_pace, ax_pace = plt.subplots()
                ax_pace.plot(long_runs_df['activity_date'], long_runs_df['pace_medio_min_km'], marker='o', linestyle='-')
                ax_pace.set_title("Pace Médio em Treinos Longos")
                ax_pace.set_ylabel("Pace Médio (min/km)")
                ax_pace.set_xlabel("Data do Treino")
                ax_pace.invert_yaxis()
                fig_pace.autofmt_xdate()
                
                st.pyplot(fig_pace)

