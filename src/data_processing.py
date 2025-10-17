import pandas as pd
import numpy as np
from datetime import timedelta, datetime

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

def gerar_analise_ia(tempo_por_zona, df_parciais):
    """Generates an AI-based analysis of a workout."""
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