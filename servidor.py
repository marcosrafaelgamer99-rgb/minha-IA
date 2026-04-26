from flask import Flask, render_template, request, jsonify, url_for, session, redirect
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import json
import uuid
from openai import OpenAI

app = Flask(__name__)
# Configuração para o Render reconhecer HTTPS corretamente
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
CORS(app)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ank_soberana_fluid_2026")

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

HISTORY_FILE = 'memoria_ank.json'

def carregar_db():
    """Lê a base de dados garantindo que é um dicionário para evitar Erro 500"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                # Se os dados não forem um dicionário (ex: forem uma lista []), resetamos
                if isinstance(dados, dict):
                    return dados
                return {}
        except:
            return {}
    return {}

def salvar_db(dados):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def gerar_titulo(mensagem):
    try:
        res = client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "system", "content": "Cria um título de 2 palavras em MAIÚSCULAS para este tema."},
                      {"role": "user", "content": mensagem}],
            max_tokens=10
        )
        return res.choices[0].message.content.strip().replace('"', '')
    except:
        return "NOVA SESSÃO"

@app.route('/')
def index():
    user = session.get('user')
    user_email = user.get("email", "visitante") if user else "visitante"
    
    db = carregar_db()
    # Proteção contra o erro 'list object has no attribute get'
    user_data = db.get(user_email)
    if not isinstance(user_data, dict):
        user_data = {"sessions": []}
    
    return render_template('index.html', user=user, sessions=user_data.get("sessions", []))

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri, prompt='select_account')

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo') or google.get('https://openidconnect.googleapis.com/v1/userinfo').json()
        session['user'] = user_info
        return redirect('/')
    except Exception as e:
        return f"Erro de Autenticação: {str(e)}", 400

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/new_chat', methods=['POST'])
def new_chat():
    user = session.get('user')
    user_email = user.get("email", "visitante") if user else "visitante"
    
    db = carregar_db()
    if user_email not in db or not isinstance(db[user_email], dict):
        db[user_email] = {"sessions": []}
    
    new_id = str(uuid.uuid4())
    new_session = {"id": new_id, "title": "NOVA SESSÃO", "messages": []}
    db[user_email]["sessions"].insert(0, new_session)
    salvar_db(db)
    return jsonify(new_session)

@app.route('/delete_chat', methods=['POST'])
def delete_chat():
    data = request.json
    chat_id = data.get('id')
    user_email = session.get('user', {}).get("email", "visitante")
    
    db = carregar_db()
    if user_email in db:
        db[user_email]["sessions"] = [s for s in db[user_email]["sessions"] if s["id"] != chat_id]
        salvar_db(db)
    return jsonify({"status": "deleted"})

@app.route('/get_messages/<chat_id>')
def get_messages(chat_id):
    user_email = session.get('user', {}).get("email", "visitante")
    db = carregar_db()
    sessions = db.get(user_email, {}).get("sessions", [])
    for s in sessions:
        if s["id"] == chat_id:
            return jsonify(s["messages"])
    return jsonify([])

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message')
    chat_id = data.get('chat_id')
    
    user_info = session.get('user')
    user_email = user_info.get("email", "visitante") if user_info else "visitante"
    
    db = carregar_db()
    user_sessions = db.get(user_email, {}).get("sessions", [])
    current_session = next((s for s in user_sessions if s["id"] == chat_id), None)
    
    if not current_session:
        return jsonify({"error": "Sessão não encontrada"}), 404

    # Título automático na primeira interação
    if not current_session["messages"]:
        current_session["title"] = gerar_titulo(user_msg)

    current_session["messages"].append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(
            model="llama3.1-8b", 
            messages=[{"role": "system", "content": "ANK 1.0. Minimalista. Soberana. Abril 2026."}] + current_session["messages"][-10:],
            max_tokens=4000
        )
        ans = response.choices[0].message.content
        current_session["messages"].append({"role": "assistant", "content": ans})
        salvar_db(db)
        return jsonify({"response": ans, "title": current_session["title"]})
    except Exception as e:
        return jsonify({"response": f"[FALHA]: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)