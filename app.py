import streamlit as st
import fitparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta

# --- Funções de Análise (nossa lógica principal) ---
def calcular_velocidade_e_pace(df):
    df.dropna(subset=['timestamp', 'distancia_m'], inplace=True)
    df['delta_distancia_m'] = df['distancia_m'].diff()
    df['delta_tempo_s'] = df['timestamp'].diff().dt.total_seconds()
    df['velocidade_ms'] = df['delta_distancia_m'] / df['delta_tempo_s']
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df['velocidade_ms'] = df['velocidade_ms'].ffill()
    df.dropna(subset=['velocidade_ms'], inplace=True)
    df['pace_min_km'] = 16.667 / df['velocidade_ms']
    return df

def analisar_zonas_fc(df, fc_maxima):
    zonas_limites = [0, fc_maxima * 0.6, fc_maxima * 0.7, fc_maxima * 0.8, fc_maxima * 0.9, fc_maxima * 2]
    zonas_labels = ["Z1 - Muito Leve", "Z2 - Leve", "Z3 - Moderado", "Z4 - Difícil", "Z5 - Máximo"]
    df['zona_fc'] = pd.cut(df['fc_bpm'], bins=zonas_limites, labels=zonas_labels, right=False)
    tempo_por_zona = df['zona_fc'].value_counts().sort_index()
    return tempo_por_zona

def plotar_grafico(df):
    df_plot = df.copy()
    df_plot['distancia_km'] = df_plot['distancia_m'] / 1000.0
    df_plot['pace_suavizado'] = df_plot['pace_min_km'].rolling(window=15, min_periods=1).mean()
    df_plot = df_plot[(df_plot['pace_suavizado'] < 15) & (df_plot['pace_suavizado'] > 2)]
    
    fig, ax1 = plt.subplots(figsize=(15, 7))
    plt.title('Análise do Treino por Distância', fontsize=16)
    
    color = 'tab:blue'
    ax1.set_xlabel('Distância (km)')
    ax1.set_ylabel('Pace (min/km)', color=color, fontsize=12)
    ax1.plot(df_plot['distancia_km'], df_plot['pace_suavizado'], color=color, label='Pace (Suavizado)')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.invert_yaxis()

    ax2 = ax1.twinx()
    color_fc = 'tab:red'
    ax2.set_ylabel('FC (bpm)', color=color_fc, fontsize=12)
    ax2.plot(df_plot['distancia_km'], df_plot['fc_bpm'], color=color_fc, label='Frequência Cardíaca')
    ax2.tick_params(axis='y', labelcolor=color_fc)

    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    
    if df_plot['cadencia_spm'].notna().sum() > 50:
        ax2.plot(df_plot['distancia_km'], df_plot['cadencia_spm'], color='tab:green', linestyle='--', label='Cadência')
        lines2_cad, labels2_cad = ax2.get_legend_handles_labels()
        lines2.append(lines2_cad[-1])
        labels2.append(labels2_cad[-1])

    fig.tight_layout()
    ax1.legend(lines + lines2, labels + labels2, loc='best')
    return fig

# --- Interface do Aplicativo Streamlit ---
st.set_page_config(page_title="Agente de Análise de Treinos", layout="wide")
st.title("🏃‍♂️ Agente de Análise de Treinos")
st.write("Faça o upload do seu arquivo de treino no formato `.fit` para uma análise detalhada.")

uploaded_file = st.file_uploader("Escolha seu arquivo .fit", type="fit")

if uploaded_file is not None:
    try:
        fitfile = fitparse.FitFile(uploaded_file)
        
        timestamps, distancias, heart_rates, cadences = [], [], [], []
        for record in fitfile.get_messages('record'):
            timestamps.append(record.get_value('timestamp'))
            distancias.append(record.get_value('distance'))
            heart_rates.append(record.get_value('heart_rate'))
            cadences.append(record.get_value('cadence'))

        df = pd.DataFrame({
            'timestamp': timestamps, 'distancia_m': distancias,
            'fc_bpm': heart_rates, 'cadencia_spm': cadences
        })

        st.header("Análise Detalhada do Treino")
        
        with st.spinner('Calculando métricas e gerando gráfico...'):
            df = calcular_velocidade_e_pace(df)
            
            # Gráfico
            st.pyplot(plotar_grafico(df))

            # Análise de Zonas de FC
            st.subheader("Análise de Esforço: Zonas de Frequência Cardíaca")
            fc_max_input = st.number_input("Informe sua Frequência Cardíaca Máxima (bpm):", min_value=100, max_value=250, value=183)
            
            if fc_max_input:
                tempo_por_zona = analisar_zonas_fc(df, fc_max_input)
                st.table(tempo_por_zona.apply(lambda x: f"{int(x // 60):02d}:{int(x % 60):02d}"))
    
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")