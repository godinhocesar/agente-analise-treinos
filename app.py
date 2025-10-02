import streamlit as st
import fitparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta

# --- Funções de Análise (nossa lógica principal) ---
# (As funções de cálculo e plotagem permanecem as mesmas da v1.3)
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
    df_fc = df.dropna(subset=['fc_bpm']).copy()
    zonas_limites = [0, fc_maxima * 0.6, fc_maxima * 0.7, fc_maxima * 0.8, fc_maxima * 0.9, fc_maxima * 2]
    zonas_labels = ["Z1 - Muito Leve", "Z2 - Leve", "Z3 - Moderado", "Z4 - Difícil", "Z5 - Máximo"]
    df_fc['zona_fc'] = pd.cut(df_fc['fc_bpm'], bins=zonas_limites, labels=zonas_labels, right=False)
    tempo_por_zona = df_fc['zona_fc'].value_counts().sort_index()
    return tempo_por_zona

def plotar_grafico(df):
    df_plot = df.dropna(subset=['distancia_m', 'velocidade_ms', 'fc_bpm']).copy()
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

def formatar_tempo_min_seg(segundos):
    minutos = int(segundos // 60)
    segundos = int(segundos % 60)
    return f"{minutos:02d}:{segundos:02d}"

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

            # --- NOVIDADE: Painel de Métricas ---
            st.subheader("Painel de Métricas Gerais")
            
            # Cálculos das métricas
            tempo_total = (df_com_pace['timestamp'].iloc[-1] - df_com_pace['timestamp'].iloc[0]).total_seconds()
            distancia_total_km = df_com_pace['distancia_m'].iloc[-1] / 1000.0
            pace_medio_decimal = tempo_total / 60 / distancia_total_km if distancia_total_km > 0 else 0
            
            fc_media = df_com_pace['fc_bpm'].mean()
            fc_max = df_com_pace['fc_bpm'].max()
            
            cad_media = df_com_pace['cadencia_spm'].mean()
            cad_max = df_com_pace['cadencia_spm'].max()

            # Comprimento da Pernada (Stride Length) em cm
            # Velocidade média em m/s / (Cadência média em spm / 120)