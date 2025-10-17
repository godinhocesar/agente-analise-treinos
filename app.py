import streamlit as st
import pyrebase # A nossa nova ferramenta de autenticação
import json

# Importa os módulos da nossa estrutura
from src.firestore import init_firestore_connection
from src.ui import (
    display_sidebar,
    display_strava_authentication, 
    display_workout_analysis_tab, 
    display_progress_dashboard_tab
)

# --- Configuração da Conexão com o Firebase ---
try:
    # --- ALTERAÇÃO PRINCIPAL AQUI ---
    # Cria uma cópia do dicionário de credenciais para poder modificá-lo
    firebase_creds_dict = dict(st.secrets["firebase_credentials"])
    
    # Pyrebase precisa da chave privada no formato correto
    if 'private_key' in firebase_creds_dict:
        firebase_creds_dict['private_key'] = firebase_creds_dict['private_key'].replace('\\n', '\n')
    
    # Adiciona a chave da API Web que vamos buscar à consola
    firebase_config = {
        "apiKey": st.secrets["firebase_config"]["apiKey"],
        "authDomain": f"{firebase_creds_dict['project_id']}.firebaseapp.com",
        "projectId": firebase_creds_dict['project_id'],
        "storageBucket": f"{firebase_creds_dict['project_id']}.appspot.com",
        "databaseURL": f"https://{firebase_creds_dict['project_id']}-default-rtdb.firebaseio.com/",
        "serviceAccount": firebase_creds_dict
    }
    firebase = pyrebase.initialize_app(firebase_config)
    auth = firebase.auth()
except Exception as e:
    st.error(f"Erro ao inicializar a conexão com o Firebase: {e}")
    st.stop()


def main():
    """Função principal para executar a aplicação Streamlit."""
    st.set_page_config(page_title="Plataforma de Treino Inteligente", layout="wide")
    
    st.title("🏃‍♂️ Plataforma de Treino Inteligente")

    # Se o utilizador ainda não está logado na sessão
    if 'user' not in st.session_state:
        # Cria duas abas para Login e Registo
        login_tab, register_tab = st.tabs(["Login", "Registar"])

        with login_tab:
            st.subheader("Faça o seu Login")
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Palavra-passe", type="password", key="login_password")
            if st.button("Login"):
                try:
                    user = auth.sign_in_with_email_and_password(email, password)
                    st.session_state['user'] = user # Guarda as informações do utilizador na sessão
                    st.rerun() # Recarrega a página para o estado "logado"
                except Exception as e:
                    st.error("Email ou palavra-passe incorretos.")

        with register_tab:
            st.subheader("Crie a sua Conta")
            new_email = st.text_input("Email", key="register_email")
            new_password = st.text_input("Palavra-passe", type="password", key="register_password")
            if st.button("Registar"):
                try:
                    user = auth.create_user_with_email_and_password(new_email, new_password)
                    st.success("Conta criada com sucesso! Por favor, faça o login na aba 'Login'.")
                except Exception as e:
                    st.error(f"Não foi possível criar a conta: {e}")
    else:
        # --- Interface Principal (APÓS LOGIN BEM-SUCEDIDO) ---
        user_info = st.session_state['user']
        # Podemos obter o email do utilizador logado
        user_email = user_info['email']

        with st.sidebar:
            st.write(f"Bem-vindo, {user_email}")
            if st.button("Logout"):
                del st.session_state['user'] # Apaga os dados da sessão
                st.rerun()
        
        db = init_firestore_connection()
        
        sono_duracao, sono_profundo, sono_score, stress, energia = display_sidebar()
        token_info = display_strava_authentication()

        if token_info:
            user_id = token_info.get('athlete', {}).get('id')
            tab1, tab2 = st.tabs(["📊 Análise de Treino", "📈 Dashboard de Progresso"])

            with tab1:
                display_workout_analysis_tab(db, token_info, sono_duracao, sono_profundo, sono_score)

            with tab2:
                display_progress_dashboard_tab(db, user_id)

if __name__ == "__main__":
    main()