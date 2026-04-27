from flask import Flask, render_template, request, jsonify, url_for, session, redirect
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import json
import uuid
from openai import OpenAI

app = Flask(__name__)
# Configuração obrigatória para o Render (HTTPS)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
CORS(app)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ank_soberana_checkout_2026")

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
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                return dados if isinstance(dados, dict) else {}
        except: return {}
    return {}

def salvar_db(dados):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def gerar_titulo(mensagem):
    try:
        res = client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "system", "content": "Resuma a mensagem em 2 palavras. Título curto em maiúsculas."},
                      {"role": "user", "content": mensagem}],
            max_tokens=8
        )
        return res.choices[0].message.content.upper().replace('"', '')
    except: return "NOVA SESSÃO"

# ==========================================
# ROTAS DE PÁGINAS (FRONTEND)
# ==========================================

@app.route('/')
def index():
    user = session.get('user')
    user_email = user.get("email", "visitante") if user else "visitante"
    db = carregar_db()
    user_data = db.get(user_email, {"sessions": []})
    return render_template('index.html', user=user, sessions=user_data["sessions"])

# -> ESTA É A ROTA QUE ESTAVA A FALTAR E CAUSOU O ERRO 404 <-
@app.route('/checkout')
def checkout():
    user = session.get('user')
    # Carrega a página de checkout.html que vamos criar abaixo
    return render_template('checkout.html', user=user)

# ==========================================
# ROTAS DE AUTENTICAÇÃO (GOOGLE)
# ==========================================

@app.route('/login')
def login():
    return google.authorize_redirect(url_for('authorize', _external=True), prompt='select_account')

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        session['user'] = token.get('userinfo') or google.get('https://openidconnect.googleapis.com/v1/userinfo').json()
        return redirect('/')
    except Exception as e:
        return f"Erro Crítico de Login: {str(e)}", 400

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

# ==========================================
# ROTAS DE DADOS (BACKEND / CHAT)
# ==========================================

@app.route('/new_chat', methods=['POST'])
def new_chat():
    u_email = session.get('user', {}).get("email", "visitante")
    db = carregar_db()
    if u_email not in db: db[u_email] = {"sessions": []}
    new_id = str(uuid.uuid4())
    new_sess = {"id": new_id, "title": "NOVA SESSÃO", "messages": []}
    db[u_email]["sessions"].insert(0, new_sess)
    salvar_db(db)
    return jsonify(new_sess)

@app.route('/delete_chat', methods=['POST'])
def delete_chat():
    cid = request.json.get('id')
    u_email = session.get('user', {}).get("email", "visitante")
    db = carregar_db()
    if u_email in db:
        db[u_email]["sessions"] = [s for s in db[u_email]["sessions"] if s["id"] != cid]
        salvar_db(db)
    return jsonify({"status": "ok"})

@app.route('/get_messages/<chat_id>')
def get_messages(chat_id):
    u_email = session.get('user', {}).get("email", "visitante")
    db = carregar_db()
    for s in db.get(u_email, {}).get("sessions", []):
        if s["id"] == chat_id: return jsonify(s["messages"])
    return jsonify([])

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg, cid = data.get('message'), data.get('chat_id')
    user_info = session.get('user')
    u_email = user_info.get("email", "visitante") if user_info else "visitante"
    
    db = carregar_db()
    sessions = db.get(u_email, {}).get("sessions", [])
    sess = next((s for s in sessions if s["id"] == cid), None)
    
    if not sess: return jsonify({"error": "No session"}), 404
    if not sess["messages"]: sess["title"] = gerar_titulo(msg)
    
    sess["messages"].append({"role": "user", "content": msg})
    
    try:
        res = client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "system", "content": "ANK 1.0 Soberana. Abril 2026. Responda de forma elegante, direta e técnica."}] + sess["messages"][-12:],
            max_tokens=4000
        )
        ans = res.choices[0].message.content
        sess["messages"].append({"role": "assistant", "content": ans})
        salvar_db(db)
        return jsonify({"response": ans, "title": sess["title"]})
    except Exception as e: return jsonify({"response": f"ERRO DE CONEXÃO: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))