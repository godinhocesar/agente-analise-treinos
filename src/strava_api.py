import streamlit as st
import requests

@st.cache_data(ttl=600)
def get_strava_activities(access_token):
    """Fetches athlete activities from Strava."""
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://www.strava.com/api/v3/athlete/activities', headers=headers)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=3600)
def get_activity_streams(activity_id, access_token):
    """Fetches activity streams from Strava."""
    headers = {'Authorization': f'Bearer {access_token}'}
    keys = 'time,distance,heartrate,cadence,altitude'
    response = requests.get(f'https://www.strava.com/api/v3/activities/{activity_id}/streams?keys={keys}&key_by_type=true', headers=headers)
    response.raise_for_status()
    return response.json()