import streamlit as st

from src.firestore import init_firestore_connection
from src.ui import display_strava_authentication, display_workout_analysis_tab, display_progress_dashboard_tab

def main():
    """Main function to run the Streamlit application."""
    st.set_page_config(page_title="Plataforma de Treino Inteligente", layout="wide")
    db = init_firestore_connection()

    st.title("🏃‍♂️ Plataforma de Treino Inteligente")

    token_info = display_strava_authentication()

    if token_info:
        user_id = token_info.get('athlete', {}).get('id')
        tab1, tab2 = st.tabs(["📊 Análise de Treino", "📈 Dashboard de Progresso"])

        with tab1:
            display_workout_analysis_tab(db, token_info)

        with tab2:
            display_progress_dashboard_tab(db, user_id)

if __name__ == "__main__":
    main()