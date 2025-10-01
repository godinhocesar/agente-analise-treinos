import fitparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

ARQUIVO_FIT = 'treino.fit'

def formatar_tempo_min_seg(segundos_totais):
    """Função para converter segundos em formato MM:SS."""
    if segundos_totais is None: return "00:00"
    minutos = int(segundos_totais // 60)
    segundos = int(segundos_totais % 60)
    return f"{minutos:02d}:{segundos:02d}"

def analisar_treino_completo(caminho_arquivo, fc_maxima_usuario):
    try:
        # --- Seção de Coleta e Cálculo (igual à versão anterior) ---
        fitfile = fitparse.FitFile(caminho_arquivo)
        print("Analisando e processando os dados...")
        timestamps, distancias, heart_rates, cadences = [], [], [], []
        for record in fitfile.get_messages('record'):
            timestamps.append(record.get_value('timestamp'))
            distancias.append(record.get_value('distance'))
            heart_rates.append(record.get_value('heart_rate'))
            cadences.append(record.get_value('cadence'))

        df = pd.DataFrame({'timestamp': timestamps, 'distancia_m': distancias, 'fc_bpm': heart_rates, 'cadencia_spm': cadences})
        df.dropna(subset=['timestamp', 'distancia_m'], inplace=True)
        df['delta_distancia_m'] = df['distancia_m'].diff()
        df['delta_tempo_s'] = df['timestamp'].diff().dt.total_seconds()
        df['velocidade_ms'] = df['delta_distancia_m'] / df['delta_tempo_s']
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df['velocidade_ms'] = df['velocidade_ms'].ffill()

        # --- NOVIDADE: Análise de Zonas de Frequência Cardíaca ---
        print("Calculando tempo nas zonas de Frequência Cardíaca...")
        
        # Definindo os limites das zonas com base na sua FC Máxima
        zonas = [
            (0, fc_maxima_usuario * 0.6, "Z1 - Muito Leve"),
            (fc_maxima_usuario * 0.6, fc_maxima_usuario * 0.7, "Z2 - Leve"),
            (fc_maxima_usuario * 0.7, fc_maxima_usuario * 0.8, "Z3 - Moderado"),
            (fc_maxima_usuario * 0.8, fc_maxima_usuario * 0.9, "Z4 - Difícil"),
            (fc_maxima_usuario * 0.9, fc_maxima_usuario * 2, "Z5 - Máximo") # Limite superior alto
        ]
        
        # Criando os "bins" (faixas) e "labels" (rótulos) para a classificação
        bins = [z[0] for z in zonas] + [zonas[-1][1]]
        labels = [z[2] for z in zonas]
        
        # Classifica cada ponto de dado em uma zona
        df['zona_fc'] = pd.cut(df['fc_bpm'], bins=bins, labels=labels, right=False)
        
        # Calcula o tempo em cada zona (assumindo 1 ponto de dado por segundo, aprox.)
        tempo_por_zona = df['zona_fc'].value_counts().sort_index()
        
        print("\n--- Relatório de Zonas de Frequência Cardíaca ---")
        total_tempo = tempo_por_zona.sum()
        for zona, tempo in tempo_por_zona.items():
            percentual = (tempo / total_tempo) * 100
            print(f"{zona:<15}: {formatar_tempo_min_seg(tempo)} ({percentual:.1f}%)")
        print("--------------------------------------------------\n")

        # --- Seção de Gráfico (igual à versão anterior) ---
        df_plot = df.dropna(subset=['velocidade_ms', 'fc_bpm']).copy()
        df_plot['distancia_km'] = df_plot['distancia_m'] / 1000.0
        df_plot['pace_min_km'] = 16.667 / df_plot['velocidade_ms']
        df_plot['pace_suavizado'] = df_plot['pace_min_km'].rolling(window=15, min_periods=1).mean()
        df_plot = df_plot[(df_plot['pace_suavizado'] < 15) & (df_plot['pace_suavizado'] > 2)]

        fig, ax1 = plt.subplots(figsize=(15, 7))
        # ... (o resto do código do gráfico é idêntico ao anterior)
        plt.title('Análise do Treino por Distância (Pace Suavizado)', fontsize=16)
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
        lines, labels_ax1 = ax1.get_legend_handles_labels()
        lines2, labels_ax2 = ax2.get_legend_handles_labels()
        if df_plot['cadencia_spm'].notna().sum() > 50:
            ax2.plot(df_plot['distancia_km'], df_plot['cadencia_spm'], color='tab:green', linestyle='--', label='Cadência')
            lines2_cad, labels2_cad = ax2.get_legend_handles_labels()
            lines2.append(lines2_cad[-1])
            labels_ax2.append(labels2_cad[-1])
        fig.tight_layout()
        ax1.legend(lines + lines2, labels_ax1 + labels_ax2, loc='best')
        
        nome_grafico = "grafico_treino_suavizado.png"
        plt.savefig(nome_grafico)
        print(f"Gráfico salvo com sucesso como '{nome_grafico}'!")

    except Exception as e:
        print(f"Ocorreu um erro: {e}")

# --- IMPORTANTE: Defina sua Frequência Cardíaca Máxima aqui ---
# Com base nos seus treinos, 180-183 bpm parece um bom valor. Vamos usar 183.
FC_MAXIMA = 183
analisar_treino_completo(ARQUIVO_FIT, FC_MAXIMA)