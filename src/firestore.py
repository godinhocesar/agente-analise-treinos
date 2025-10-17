import streamlit as st
import google.cloud.firestore
from google.oauth2 import service_account
import pandas as pd

@st.cache_resource
def init_firestore_connection():
    """Initializes a connection to Google Firestore."""
    creds_dict = st.secrets["firebase_credentials"]
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    db = google.cloud.firestore.Client(credentials=creds)
    return db

def save_analysis_to_firestore(db, user_id, activity_id, metrics):
    """Saves a workout analysis to Firestore."""
    doc_ref = db.collection("users").document(str(user_id)).collection("activities").document(str(activity_id))
    doc_ref.set(metrics)

@st.cache_data(ttl=300)
def get_analyses_from_firestore(_db, user_id):
    """Retrieves workout analyses from Firestore."""
    activities_ref = _db.collection("users").document(str(user_id)).collection("activities")
    all_activities = [doc.to_dict() for doc in activities_ref.stream()]

    if not all_activities:
        return pd.DataFrame()

    df = pd.DataFrame(all_activities)
    if 'activity_date' not in df.columns:
        return pd.DataFrame()
        
    df['activity_date'] = pd.to_datetime(df['activity_date'])
    df.sort_values(by='activity_date', ascending=False, inplace=True)
    return df