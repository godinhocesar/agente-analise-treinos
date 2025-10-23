🏃‍♂️ Plataforma de Treino Inteligente


Bem-vindo à Plataforma de Treino Inteligente! Este é um projeto em desenvolvimento de uma aplicação web para análise detalhada de treinos de corrida, com o objetivo de se tornar um treinador de IA para atletas amadores.

A plataforma conecta-se à sua conta do Strava, importa as suas atividades de corrida e fornece um dashboard completo com métricas de desempenho, análise de ritmo por quilómetro, gráficos de evolução e análise de esforço por zonas de frequência cardíaca.

✨ Funcionalidades Atuais

Conexão Segura com o Strava: Autenticação via OAuth2 para importar os seus dados de forma segura.

Dashboard de Análise: Métricas detalhadas para cada treino (distância, pace, FC, cadência, etc.).

Análise de Parciais: Tabela de ritmo (pace) e FC média para cada quilómetro do seu treino.

Gráficos de Desempenho: Visualização do seu pace, FC e cadência ao longo da distância.

Análise de Zonas de Esforço: Relatório detalhado do tempo gasto em cada zona de frequência cardíaca.

Memória de Longo Prazo: As análises são guardadas numa base de dados (Firestore) para acompanhamento do progresso.

Dashboard de Progresso: Gráficos que mostram a sua evolução ao longo do tempo.

🛠️ Como Executar o Projeto Localmente

Siga os passos abaixo para rodar a aplicação no seu computador.

1. Pré-requisitos

Python 3.9+ instalado.

Uma conta no Strava e na Google Firebase.

2. Instalação

Clone ou faça o download deste repositório. Na pasta do projeto, crie e ative um ambiente virtual:

# Criar o ambiente virtual
python3 -m venv venv

# Ativar o ambiente virtual (macOS/Linux)
source venv/bin/activate


Instale as dependências necessárias:

pip install -r requirements.txt


3. Configuração das Chaves Secretas

Para que a aplicação se conecte às APIs do Strava e do Firebase, você precisa de fornecer as suas chaves de acesso.

Na raiz do projeto, crie uma pasta chamada .streamlit.

Dentro de .streamlit, crie um ficheiro chamado secrets.toml.

Copie e cole o conteúdo do ficheiro secrets.example.toml neste novo ficheiro e substitua os placeholders com as suas chaves reais.

4. Executar a Aplicação

Com o ambiente virtual ativado, execute o seguinte comando no terminal:

streamlit run app.py


A aplicação será aberta automaticamente no seu navegador no endereço http://localhost:8501.