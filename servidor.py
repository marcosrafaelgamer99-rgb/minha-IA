from flask import Flask, render_template, request, jsonify, url_for, session, redirect
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import json
import uuid
import time
from openai import OpenAI

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
CORS(app)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ank_soberana_pix_2026")

# --- OAUTH GOOGLE ---
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# --- NÚCLEO CEREBRAS ---
client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=os.environ.get("CEREBRAS_API_KEY")
)

HISTORY_FILE = 'memoria_ank.json'

# --- LIMITES SOBERANOS 2026 ---
LIMITES_TOKENS = {
    "Grátis": 500000,
    "Pro": 5000000,
    "Plus": 50000000
}

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

def init_user_if_needed(email):
    db = carregar_db()
    if email not in db:
        db[email] = {
            "sessions": [], 
            "plano": "Grátis", 
            "tokens": LIMITES_TOKENS["Grátis"]
        }
        salvar_db(db)
    return db[email]

def atualizar_plano_usuario(email, novo_plano):
    db = carregar_db()
    init_user_if_needed(email)
    db[email]["plano"] = novo_plano
    # Reseta os tokens de acordo com o novo plano
    db[email]["tokens"] = LIMITES_TOKENS.get(novo_plano, 500000)
    salvar_db(db)

# ==========================================
# ROTAS FRONTEND
# ==========================================
@app.route('/')
def index():
    user = session.get('user')
    user_email = user.get("email", "visitante") if user else "visitante"
    
    if user:
        user_data = init_user_if_needed(user_email)
    else:
        user_data = {"sessions": [], "plano": "Visitante", "tokens": 0}
        
    return render_template('index.html', 
                           user=user, 
                           sessions=user_data.get("sessions", []), 
                           plano=user_data.get("plano", "Grátis"),
                           tokens=user_data.get("tokens", 0))

@app.route('/checkout')
def checkout():
    user = session.get('user')
    if not user:
        return redirect('/login') 
    return render_template('checkout.html', user=user)

# ==========================================
# API DE UPGRADE (VIA CUPOM OU PIX)
# ==========================================
@app.route('/api/upgrade_plano', methods=['POST'])
def upgrade_plano():
    """Rota usada pelo checkout para efetivar o plano no banco de dados"""
    user = session.get('user')
    if not user: return jsonify({"error": "Não autenticado"}), 401
    
    data = request.json
    novo_plano = data.get('plan')
    
    atualizar_plano_usuario(user["email"], novo_plano)
    return jsonify({"status": "sucesso", "plano": novo_plano})

# ==========================================
# ROTAS OAUTH
# ==========================================
@app.route('/login')
def login(): return google.authorize_redirect(url_for('authorize', _external=True), prompt='select_account')

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    session['user'] = token.get('userinfo') or google.get('https://openidconnect.googleapis.com/v1/userinfo').json()
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

# ==========================================
# GESTÃO DO CHAT E TOKENS
# ==========================================
@app.route('/new_chat', methods=['POST'])
def new_chat():
    u_email = session.get('user', {}).get("email", "visitante")
    db = carregar_db()
    init_user_if_needed(u_email)
    
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
    user = session.get('user')
    u_email = user.get("email", "visitante") if user else "visitante"
    
    if u_email == "visitante":
        return jsonify({"error": "Faça login para interagir."}), 401
    
    db = carregar_db()
    user_data = init_user_if_needed(u_email)
    
    if user_data["tokens"] <= 0:
        return jsonify({"response": "LIMITE DE TOKENS EXCEDIDO. Por favor, atualize o seu plano para continuar operando.", "tokens_restantes": 0})
    
    sessions = user_data.get("sessions", [])
    sess = next((s for s in sessions if s["id"] == cid), None)
    
    if not sess: return jsonify({"error": "Sessão não encontrada"}), 404
    if not sess["messages"]:
        try:
            res = client.chat.completions.create(model="llama3.1-8b", messages=[{"role": "system", "content": "Resumo de 2 palavras. Apenas o resumo."}, {"role": "user", "content": msg}], max_tokens=8)
            sess["title"] = res.choices[0].message.content.upper().replace('"', '')
        except: sess["title"] = "NOVA SESSÃO"
    
    sess["messages"].append({"role": "user", "content": msg})
    
    plano_atual = user_data.get("plano", "Grátis")
    sys_prompt = "ANK 1.0 Soberana. Abril 2026. Responda de forma elegante e técnica."
    
    if plano_atual == "Pro": sys_prompt += " O utilizador é PRO. Responda com mais profundidade."
    elif plano_atual == "Plus": sys_prompt += " O utilizador é PLUS. Responda como a elite absoluta."
    
    try:
        res = client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "system", "content": sys_prompt}] + sess["messages"][-12:],
            max_tokens=4000
        )
        ans = res.choices[0].message.content
        sess["messages"].append({"role": "assistant", "content": ans})
        
        # --- CÁLCULO REAL DE TOKENS ---
        # Estimativa: 1 token a cada 4 caracteres
        tokens_gastos = (len(msg) // 4) + (len(ans) // 4) + 12
        user_data["tokens"] -= tokens_gastos
        if user_data["tokens"] < 0: user_data["tokens"] = 0
        
        salvar_db(db)
        return jsonify({"response": ans, "title": sess["title"], "tokens_restantes": user_data["tokens"]})
        
    except Exception as e: return jsonify({"response": f"ERRO DE NÚCLEO: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))