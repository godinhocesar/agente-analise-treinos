import streamlit as st
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import requests

from src.strava_api import get_strava_activities, get_activity_streams
from src.data_processing import (
    process_strava_streams, calcular_velocidade_e_pace, calcular_parciais_km,
    analisar_zonas_fc, gerar_analise_ia, formatar_tempo_hms, formatar_tempo_min_seg
)
from src.plotting import plotar_grafico
from src.firestore import save_analysis_to_firestore, get_analyses_from_firestore

def display_strava_authentication():
    """Handles Strava authentication."""
    try:
        STRAVA_CLIENT_ID = st.secrets["strava"]["client_id"]
        STRAVA_CLIENT_SECRET = st.secrets["strava"]["client_secret"]
    except (KeyError, FileNotFoundError):
        st.error("As chaves do Strava não foram encontradas nos segredos. Verifique o seu ficheiro .streamlit/secrets.toml.")
        st.stop()

    REDIRECT_URI = "http://localhost:8501"

    if 'strava_token' not in st.session_state:
        query_params = st.query_params
        auth_code = query_params.get("code")
        if auth_code:
            try:
                response = requests.post(
                    'https://www.strava.com/oauth/token',
                    data={
                        'client_id': STRAVA_CLIENT_ID,
                        'client_secret': STRAVA_CLIENT_SECRET,
                        'code': auth_code,
                        'grant_type': 'authorization_code'
                    }
                )
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
            auth_url = (
                f"https://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}"
                f"&redirect_uri={REDIRECT_URI}&response_type=code&scope=activity:read_all"
            )
            st.link_button("Conectar com o Strava", auth_url, use_container_width=True)
            return None
    return st.session_state['strava_token']

def display_workout_analysis_tab(db, token_info):
    """Displays the workout analysis tab."""
    access_token = token_info['access_token']
    athlete_name = token_info.get('athlete', {}).get('firstname', 'Atleta')
    user_id = token_info.get('athlete', {}).get('id')

    st.header(f"Bem-vindo, {athlete_name}!")
    st.write("Selecione um treino do Strava para uma análise detalhada.")

    try:
        activities = get_strava_activities(access_token)
        run_activities = [act for act in activities if act['type'] == 'Run']
        if not run_activities:
            st.warning("Nenhuma atividade de corrida encontrada nos seus treinos recentes do Strava.")
            return

        activity_options = {
            f"{datetime.fromisoformat(act['start_date_local'].replace('Z', '')).strftime('%d/%m/%Y')} - "
            f"{act['name']} ({act.get('distance', 0)/1000:.2f} km)": act
            for act in run_activities
        }
        selected_activity_name = st.selectbox(
            "Seus treinos de corrida recentes:",
            options=["Selecione um treino"] + list(activity_options.keys())
        )

        if selected_activity_name and selected_activity_name != "Selecione um treino":
            selected_activity = activity_options[selected_activity_name]
            activity_id = selected_activity['id']
            start_date = datetime.fromisoformat(selected_activity['start_date_local'].replace('Z', ''))
            st.header(f"Análise Detalhada: {selected_activity_name}")

            with st.spinner("A analisar o seu treino..."):
                display_detailed_analysis(db, user_id, activity_id, access_token, start_date, selected_activity_name)

    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code == 401:
            st.error("Sua conexão com o Strava expirou. Por favor, conecte-se novamente.")
            del st.session_state['strava_token']
            if st.button("Reconectar ao Strava"):
                st.rerun()
        else:
            st.error(f"Ocorreu um erro ao buscar suas atividades do Strava: {e}")

def display_detailed_analysis(db, user_id, activity_id, access_token, start_date, selected_activity_name):
    """Displays the detailed analysis of a selected workout."""
    streams = get_activity_streams(activity_id, access_token)
    df = process_strava_streams(streams, start_date)

    if df.empty or 'timestamp' not in df.columns:
        st.error("Não foi possível processar os dados desta atividade. Os fluxos de dados essenciais (como o tempo) podem estar em falta.")
        return

    df_com_pace = calcular_velocidade_e_pace(df)

    st.subheader("Painel de Métricas Gerais")
    display_general_metrics(df_com_pace)

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
    has_fc = 'fc_bpm' in df_com_pace.columns and df_com_pace['fc_bpm'].notna().any()
    if has_fc:
        fc_max_input = st.number_input("Informe sua Frequência Cardíaca Máxima (bpm):", min_value=100, max_value=250, value=192)
        tempo_por_zona = analisar_zonas_fc(df, fc_max_input)
        if not tempo_por_zona.empty:
            display_hr_zones(tempo_por_zona)
    else:
        tempo_por_zona = None
        st.info("Não há dados de Frequência Cardíaca para este treino.")

    st.subheader("🤖 Análise do Treinador de IA")
    analise_texto = gerar_analise_ia(tempo_por_zona, df_parciais)
    st.markdown(analise_texto)

    metrics_to_save = get_metrics_to_save(df_com_pace, selected_activity_name, start_date, has_fc, analise_texto)
    if st.button("Guardar Análise na Base de Dados"):
        with st.spinner("A guardar..."):
            save_analysis_to_firestore(db, user_id, activity_id, metrics_to_save)
            st.success("Análise guardada com sucesso!")

def display_general_metrics(df_com_pace):
    """Displays the general metrics panel."""
    has_dist = 'distancia_m' in df_com_pace.columns and not df_com_pace.empty
    has_fc = 'fc_bpm' in df_com_pace.columns and df_com_pace['fc_bpm'].notna().any()
    has_cadence = 'cadencia_spm' in df_com_pace.columns and df_com_pace['cadencia_spm'].notna().any()
    has_altitude = 'altitude_m' in df_com_pace.columns and df_com_pace['altitude_m'].notna().any()

    tempo_total = (df_com_pace['timestamp'].iloc[-1] - df_com_pace['timestamp'].iloc[0]).total_seconds()
    distancia_total_km = df_com_pace['distancia_m'].iloc[-1] / 1000.0 if has_dist else 0
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

def display_hr_zones(tempo_por_zona):
    """Displays the heart rate zones table."""
    st.subheader("Tempo em Cada Zona de Esforço")
    total_tempo = tempo_por_zona.sum()
    tabela_zonas = pd.DataFrame(tempo_por_zona).reset_index()
    tabela_zonas.columns = ['Zona', 'Tempo (s)']
    tabela_zonas['Tempo'] = tabela_zonas['Tempo (s)'].apply(formatar_tempo_min_seg)
    tabela_zonas['Percentual'] = (tabela_zonas['Tempo (s)'] / total_tempo * 100).map('{:.1f}%'.format)
    tabela_zonas.set_index('Zona', inplace=True)
    st.table(tabela_zonas[['Tempo', 'Percentual']])

def get_metrics_to_save(df_com_pace, selected_activity_name, start_date, has_fc, analise_texto):
    """Prepares a dictionary of metrics to be saved to Firestore."""
    tempo_total = (df_com_pace['timestamp'].iloc[-1] - df_com_pace['timestamp'].iloc[0]).total_seconds()
    distancia_total_km = df_com_pace['distancia_m'].iloc[-1] / 1000.0 if 'distancia_m' in df_com_pace.columns else 0
    pace_medio_decimal = tempo_total / 60 / distancia_total_km if distancia_total_km > 0 else 0
    fc_media = df_com_pace['fc_bpm'].mean() if has_fc else 0
    fc_max = df_com_pace['fc_bpm'].max() if has_fc else 0
    cad_media = df_com_pace['cadencia_spm'].mean() if 'cadencia_spm' in df_com_pace.columns and df_com_pace['cadencia_spm'].notna().any() else 0
    ascensao_total = df_com_pace['altitude_m'].diff().clip(lower=0).sum() if 'altitude_m' in df_com_pace.columns else 0

    return {
        "activity_name": selected_activity_name, "activity_date": start_date,
        "distancia_km": float(distancia_total_km), "tempo_total_s": float(tempo_total),
        "pace_medio_min_km": float(pace_medio_decimal) if pace_medio_decimal > 0 else 0.0,
        "fc_media": float(fc_media) if has_fc else 0.0,
        "fc_max": int(fc_max) if has_fc and pd.notna(fc_max) else 0,
        "cadencia_media": float(cad_media),
        "ascensao_total_m": float(ascensao_total),
        "analise_ia": analise_texto
    }

def display_progress_dashboard_tab(db, user_id):
    """Displays the progress dashboard tab."""
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