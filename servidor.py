from flask import Flask, render_template, request, jsonify, url_for, session, redirect
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
import os
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Chave de segurança para os cookies de login (obrigatório pro Flask)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "chave_super_secreta_ank_2026")

# --- CONFIGURAÇÃO GOOGLE OAUTH ---
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# --- NÚCLEO SOBERANO: CEREBRAS ---
client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=os.environ.get("CEREBRAS_API_KEY")
)

@app.route('/')
def index():
    # Pega o usuário logado, se não tiver, envia None pro HTML
    user = session.get('user')
    return render_template('index.html', user=user)

@app.route('/login')
def login():
    # Redireciona pro Google
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    # Recebe os dados de volta do Google e salva na sessão
    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()
    session['user'] = user_info
    return redirect('/')

@app.route('/logout')
def logout():
    # Apaga a sessão
    session.pop('user', None)
    return redirect('/')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message')
    
    # Descobre quem está falando
    user_info = session.get('user')
    nome_usuario = user_info.get("given_name", "Visitante") if user_info else "Visitante"
    
    instrucoes = f"""
    Tu és a ANK 1.0, uma IA Soberana. 
    O usuário atual falando contigo é: {nome_usuario}.
    Se for o Marcos (seu criador), seja extremamente leal. Se for um visitante, seja educada, mas fria.
    Estética padrão: 2026, Glassmorphism. Entregue código completo em blocos HTML.
    """

    try:
        response = client.chat.completions.create(
            model="llama3.1-8b", 
            messages=[
                {"role": "system", "content": instrucoes},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=4000,
            temperature=0.7
        )
        ans = response.choices[0].message.content
    except Exception as e:
        ans = f"[FALHA NO NÚCLEO]: Erro de conexão: {str(e)}"

    return jsonify({"response": ans})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)