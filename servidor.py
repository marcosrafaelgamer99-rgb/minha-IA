from flask import Flask, render_template, request, jsonify, url_for, session, redirect
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import json
from openai import OpenAI

app = Flask(__name__)

# --- CORREÇÃO VITAL PARA O RENDER ---
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
CORS(app)

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

# --- SISTEMA DE MEMÓRIA (HISTÓRICO) ---
HISTORY_FILE = 'memoria_ank.json'

def carregar_memoria():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def salvar_memoria(dados):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    user = session.get('user')
    user_email = user.get("email", "visitante") if user else "visitante"
    
    db = carregar_memoria()
    historico = db.get(user_email, [])
    
    return render_template('index.html', user=user, historico=historico)

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri, prompt='select_account')

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            resp = google.get('https://openidconnect.googleapis.com/v1/userinfo')
            user_info = resp.json()
            
        session['user'] = user_info
        return redirect('/')
    except Exception as e:
        return f"<h3>Falha no protocolo de Login ANK:</h3><p>{str(e)}</p><a href='/'>Voltar ao Sistema</a>", 400

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/limpar_historico', methods=['POST'])
def limpar_historico():
    user = session.get('user')
    user_email = user.get("email", "visitante") if user else "visitante"
    
    db = carregar_memoria()
    if user_email in db:
        db[user_email] = []
        salvar_memoria(db)
        
    return jsonify({"status": "memoria_apagada"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message')
    
    user_info = session.get('user')
    user_email = user_info.get("email", "visitante") if user_info else "visitante"
    nome_usuario = user_info.get("given_name", "Visitante") if user_info else "Visitante"
    
    # Gerencia a memória
    db = carregar_memoria()
    if user_email not in db:
        db[user_email] = []
        
    db[user_email].append({"role": "user", "content": user_msg})
    
    instrucoes = f"""
    Tu és a ANK 1.0, uma IA Soberana. 
    O usuário atual é: {nome_usuario}.
    Comporte-se de acordo com o design de 2026: respostas minimalistas, diretas e técnicas.
    Se for o Marcos (seu criador), seja extremamente leal.
    Entregue o código completo.
    """

    # Pega apenas as últimas 20 mensagens para não pesar o contexto
    historico_recente = db[user_email][-20:]
    mensagens_api = [{"role": "system", "content": instrucoes}] + historico_recente

    try:
        response = client.chat.completions.create(
            model="llama3.1-8b", 
            messages=mensagens_api,
            max_tokens=4000,
            temperature=0.7
        )
        ans = response.choices[0].message.content
        
        # Salva a resposta da ANK na memória
        db[user_email].append({"role": "assistant", "content": ans})
        salvar_memoria(db)
        
    except Exception as e:
        ans = f"[FALHA DE CONEXÃO]: {str(e)}"

    return jsonify({"response": ans})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)