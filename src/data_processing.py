import pandas as pd
import numpy as np
from datetime import timedelta, datetime, time

def calcular_velocidade_e_pace(df):
    """Calculates velocity and pace from a DataFrame of workout data."""
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
    """Analyzes heart rate zones from a DataFrame of workout data."""
    if 'fc_bpm' not in df.columns or 'timestamp' not in df.columns:
        return pd.Series(dtype='float64')
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

def calcular_parciais_km(df):
    """Calculates per-kilometer splits from a DataFrame of workout data."""
    if 'delta_tempo_s' not in df.columns or 'distancia_m' not in df.columns:
        return pd.DataFrame()
    df_parciais = df.dropna(subset=['delta_tempo_s', 'distancia_m']).copy()
    if df_parciais.empty:
        return pd.DataFrame()
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
    """Formats seconds into a 'minutes:seconds' string."""
    minutos = int(segundos // 60)
    segundos = int(segundos % 60)
    return f"{minutos:02d}:{segundos:02d}"

def formatar_tempo_hms(segundos):
    """Formats seconds into an 'HH:MM:SS' string."""
    return str(timedelta(seconds=int(segundos)))

def process_strava_streams(streams, start_date):
    """Processes Strava activity streams into a DataFrame."""
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

# --- NOVIDADE ---
def gerar_analise_ia(tempo_por_zona, df_parciais, sono_duracao, sono_profundo, sono_score):
    """Gera uma análise de texto inteligente baseada nos dados do treino e subjetivos."""
    insights = []
    
    if sono_duracao < time(6, 0):
        insights.append(f"**Ponto de Atenção (Sono):** A sua duração de sono foi de apenas **{sono_duracao.strftime('%Hh%Mmin')}**, o que é insuficiente para uma boa recuperação. O ideal para atletas é entre 7 e 9 horas.")
    if sono_profundo < time(0, 45):
         insights.append(f"**Ponto Crítico (Sono Profundo):** Você teve apenas **{sono_profundo.strftime('%M minutos')}** de sono profundo. Esta é a fase mais importante para a reparação muscular. Uma quantidade tão baixa aumenta o risco de lesões e overtraining.")

    if tempo_por_zona is not None and not tempo_por_zona.empty:
        total_tempo = tempo_por_zona.sum()
        tempo_z4_z5 = tempo_por_zona.get("Z4 - Difícil", 0) + tempo_por_zona.get("Z5 - Máximo", 0)
        percentual_alta_intensidade = (tempo_z4_z5 / total_tempo) * 100 if total_tempo > 0 else 0
        
        tipo_treino = "de intensidade moderada"
        if percentual_alta_intensidade > 40: tipo_treino = "de alta intensidade (Tiros/Variação)"
        elif percentual_alta_intensidade < 20: tipo_treino = "de baixa intensidade (Leve/Regenerativo)"
        insights.append(f"**Diagnóstico do Treino:** Este foi um treino {tipo_treino}, com **{percentual_alta_intensidade:.0f}%** do tempo gasto em zonas de esforço elevadas.")

        if percentual_alta_intensidade > 50 and sono_duracao < time(6, 0):
            insights.append(f"**ALERTA DO TREINADOR:** Você executou um treino muito intenso após uma noite de sono insuficiente. O seu corpo está sob um stress considerável. **É crucial que a sua próxima noite de sono seja reparadora e o seu próximo treino seja muito leve (Zona 2) ou de descanso completo.**")
    else:
        insights.append("**Diagnóstico do Treino:** Não foi possível analisar o esforço do treino por falta de dados de Frequência Cardíaca.")

    if not insights:
        return "Parece que tudo está em ordem! O treino foi bem executado e os seus indicadores de recuperação estão bons. Continue assim!"

    return "\n\n".join(f"- {insight}" for insight in insights)