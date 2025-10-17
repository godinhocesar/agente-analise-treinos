import matplotlib.pyplot as plt
import pandas as pd

def plotar_grafico(df):
    """Plots a performance graph from a DataFrame of workout data."""
    if 'distancia_m' not in df.columns or 'velocidade_ms' not in df.columns:
        return None
    df_plot = df.dropna(subset=['distancia_m', 'velocidade_ms']).copy()
    df_plot['distancia_km'] = df_plot['distancia_m'] / 1000.0
    if 'pace_min_km' not in df_plot.columns:
        return None
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