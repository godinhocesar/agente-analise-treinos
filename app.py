import streamlit as st
import fitparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta

# --- Funções de Análise ---
def calcular_velocidade_e_pace(df):
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
    df_fc = df.dropna(subset=['timestamp', 'fc_bpm']).copy()
    if df_fc.empty:
        return pd.Series(dtype='float64')
    df_fc['delta_tempo_s'] = df_fc['timestamp'].diff().dt.total_seconds()
    df_fc['delta_tempo_s'].fillna(1, inplace=True)
    zonas_limites = [0, fc_maxima * 0.6, fc_maxima * 0.7, fc_maxima * 0.8, fc_maxima * 0.9, fc_maxima * 2]
    zonas_labels = ["Z1 - Muito Leve", "Z2 - Leve", "Z3 - Moderado", "Z4 - Difícil", "Z5 - Máximo"]
    df_fc['zona_fc'] = pd.cut(df_fc['fc_bpm'], bins=zonas_limites, labels=zonas_labels, right=False, include_lowest=True)
    tempo_por_zona = df_fc.groupby('zona_fc', observed=False)['delta_tempo_s'].sum()
    return tempo_por_zona

def plotar_grafico(df):
    df_plot = df.dropna(subset=['distancia_m', 'velocidade_ms', 'fc_bpm']).copy()
    df_plot['distancia_km'] = df_plot['distancia_m'] / 1000.0
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

    ax2 = ax1.twinx()
    color_fc = 'tab:red'
    ax2.set_ylabel('FC (bpm)', color=color_fc, fontsize=12)
    ax2.plot(df_plot['distancia_km'], df_plot['fc_bpm'], color=color_fc, alpha=0.9, label='Frequência Cardíaca')
    ax2.tick_params(axis='y', labelcolor=color_fc)

    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    
    if df_plot['cadencia_spm'].notna().sum() > 50:
        line_cad = ax2.plot(df_plot['distancia_km'], df_plot['cadencia_spm'], color='tab:green', linestyle='--', label='Cadência')
        lines2.append(line_cad[0])
        labels2.append('Cadência')

    fig.tight_layout()
    ax1.legend(lines + lines2, labels + labels2, loc='best')
    return fig

# --- NOVA FUNCIONALIDADE ---
def calcular_parciais_km(df):
    df_parciais = df.dropna(subset=['delta_tempo_s', 'distancia_m']).copy()
    df_parciais['km_atual'] = (df_parciais['distancia_m'] // 1000).astype(int)
    
    parciais = []
    tempo_acumulado = 0
    for km in range(df_parciais['km_atual'].max() + 1):
        dados_km = df_parciais[df_parciais['km_atual'] == km]
        if not dados_km.empty:
            tempo_parcial = dados_km['delta_tempo_s'].sum()
            tempo_acumulado += tempo_parcial
            fc_media_parcial = dados_km['fc_bpm'].mean()
            
            pace_min = int(tempo_parcial // 60)
            pace_seg = int(tempo_parcial % 60)
            
            parciais.append({
                "Km": f"{km + 1}",
                "Ritmo": f"{pace_min:02d}'{pace_seg:02d}\"",
                "FC Média": f"{fc_media_parcial:.0f}" if pd.notna(fc_media_parcial) else "N/A",
                "Tempo Acumulado": formatar_tempo_hms(tempo_acumulado)
            })
    return pd.DataFrame(parciais)

def formatar_tempo_min_seg(segundos):
    minutos = int(segundos // 60)
    segundos = int(segundos % 60)
    return f"{minutos:02d}:{segundos:02d}"

def formatar_tempo_hms(segundos):
    return str(timedelta(seconds=int(segundos)))


# --- Interface do Aplicativo Streamlit ---
st.set_page_config(page_title="Agente de Análise de Treinos", layout="wide")
st.title("🏃‍♂️ Agente de Análise de Treinos")
st.write("Faça o upload do seu arquivo de treino no formato `.fit` para uma análise detalhada e completa.")

uploaded_file = st.file_uploader("Escolha seu arquivo .fit", type="fit")

if uploaded_file is not None:
    try:
        fitfile = fitparse.FitFile(uploaded_file)
        
        timestamps, distancias, heart_rates, cadences, altitudes = [], [], [], [], []
        for record in fitfile.get_messages('record'):
            timestamps.append(record.get_value('timestamp'))
            distancias.append(record.get_value('distance'))
            heart_rates.append(record.get_value('heart_rate'))
            cadences.append(record.get_value('cadence'))
            altitudes.append(record.get_value('altitude'))

        df = pd.DataFrame({
            'timestamp': timestamps, 'distancia_m': distancias,
            'fc_bpm': heart_rates, 'cadencia_spm': cadences,
            'altitude_m': altitudes
        })

        st.header("Análise Detalhada do Treino")
        
        with st.spinner('Analisando dados... Isso pode levar um momento.'):
            df_com_pace = calcular_velocidade_e_pace(df)

            st.subheader("Painel de Métricas Gerais")
            # ... (código do painel de métricas permanece o mesmo)
            tempo_total = (df_com_pace['timestamp'].iloc[-1] - df_com_pace['timestamp'].iloc[0]).total_seconds()
            distancia_total_km = df_com_pace['distancia_m'].iloc[-1] / 1000.0 if not df_com_pace.empty else 0
            pace_medio_decimal = tempo_total / 60 / distancia_total_km if distancia_total_km > 0 else 0
            fc_media = df_com_pace['fc_bpm'].mean()
            fc_max = df_com_pace['fc_bpm'].max()
            cad_media = df_com_pace['cadencia_spm'].mean()
            cad_max = df_com_pace['cadencia_spm'].max()
            velocidade_media_ms = df_com_pace['velocidade_ms'].mean()
            pernada_media_cm = (velocidade_media_ms / (cad_media / 120)) * 100 if cad_media > 0 else 0
            df_com_pace['altitude_diff'] = df_com_pace['altitude_m'].diff()
            ascensao_total = df_com_pace[df_com_pace['altitude_diff'] > 0]['altitude_diff'].sum()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Tempo Total", formatar_tempo_hms(tempo_total))
            col2.metric("Distância", f"{distancia_total_km:.2f} km")
            col3.metric("Pace Médio", f"{int(pace_medio_decimal)}:{int((pace_medio_decimal*60)%60):02d} /km")
            col4.metric("Ascensão Total", f"{ascensao_total:.0f} m")
            col1_fc, col2_fc, col3_cad, col4_cad = st.columns(4)
            col1_fc.metric("FC Média", f"{fc_media:.0f} bpm")
            col2_fc.metric("FC Máxima", f"{fc_max:.0f} bpm")
            col3_cad.metric("Cadência Média", f"{cad_media:.0f} spm")
            col4_cad.metric("Pernada Média", f"{pernada_media_cm:.0f} cm")

            # --- NOVIDADE: Tabela de Parciais ---
            st.subheader("Análise de Ritmo por Quilómetro (Parciais)")
            df_parciais = calcular_parciais_km(df_com_pace)
            st.dataframe(df_parciais.set_index('Km'), use_container_width=True)

            st.subheader("Gráfico de Desempenho por Distância")
            st.pyplot(plotar_grafico(df_com_pace))

            st.subheader("Análise de Esforço: Zonas de Frequência Cardíaca")
            fc_max_input = st.number_input("Informe sua Frequência Cardíaca Máxima (bpm):", min_value=100, max_value=250, value=183)
            
            if fc_max_input:
                tempo_por_zona = analisar_zonas_fc(df, fc_max_input)
                if not tempo_por_zona.empty:
                    total_tempo = tempo_por_zona.sum()
                    tabela_zonas = pd.DataFrame(tempo_por_zona).reset_index()
                    tabela_zonas.columns = ['Zona', 'Tempo (s)']
                    tabela_zonas['Tempo'] = tabelas_zonas['Tempo (s)'].apply(formatar_tempo_min_seg)
                    tabela_zonas['Percentual'] = (tabela_zonas['Tempo (s)'] / total_tempo * 100).map('{:.1f}%'.format)
                    tabela_zonas.set_index('Zona', inplace=True)
                    st.table(tabela_zonas[['Tempo', 'Percentual']])
                else:
                    st.warning("Não foram encontrados dados de Frequência Cardíaca suficientes para a análise de zonas.")
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo.")
        st.exception(e)

