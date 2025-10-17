import streamlit as st
import requests
from datetime import datetime, timedelta

def get_strava_credentials():
    """Lê as credenciais do Strava a partir dos segredos."""
    try:
        client_id = st.secrets["strava"]["client_id"]
        client_secret = st.secrets["strava"]["client_secret"]
        return client_id, client_secret
    except KeyError:
        st.error("As chaves do Strava (client_id, client_secret) não foram encontradas nos segredos.")
        st.stop()

# --- NOVIDADE: Função para renovar o token ---
def refresh_strava_token(refresh_token):
    """Usa o refresh token para obter um novo access token."""
    client_id, client_secret = get_strava_credentials()
    response = requests.post('https://www.strava.com/oauth/token', data={
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    })
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=600)
def get_strava_activities(access_token):
    """Busca as atividades do atleta."""
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://www.strava.com/api/v3/athlete/activities', headers=headers)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=3600)
def get_activity_streams(activity_id, access_token):
    """Busca os dados detalhados de uma atividade."""
    headers = {'Authorization': f'Bearer {access_token}'}
    keys = 'time,distance,heartrate,cadence,altitude'
    response = requests.get(f'https://www.strava.com/api/v3/activities/{activity_id}/streams?keys={keys}&key_by_type=true', headers=headers)
    response.raise_for_status()
    return response.json()