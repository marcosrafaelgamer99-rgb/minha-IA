from flask import Flask, render_template, request, jsonify, url_for, session, redirect
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import json
import uuid
import re
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
LIMITES_TOKENS = {"Grátis": 500000, "Pro": 5000000, "Plus": 50000000}

# ==========================================
# FERRAMENTAS DA IA (GOOGLE E YOUTUBE)
# ==========================================
def pesquisar_google(query):
    try:
        from duckduckgo_search import DDGS
        resultados = DDGS().text(query, max_results=3)
        texto_resultado = "\n".join([f"- {r['title']}: {r['body']} (Fonte: {r['href']})" for r in resultados])
        return f"[RESULTADOS DA WEB OBTIDOS AGORA]:\n{texto_resultado}\n\nResponda ao utilizador com base nestes dados recentes."
    except ImportError:
        return "[SISTEMA: O pacote 'duckduckgo-search' não está instalado no servidor. Avise o utilizador.]"
    except Exception as e:
        return f"[SISTEMA: Erro na busca web: {str(e)}]"

def extrair_id_youtube(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

def ler_legenda_youtube(url):
    video_id = extrair_id_youtube(url)
    if not video_id: return "[SISTEMA: URL do YouTube inválida fornecida.]"
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcricao = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en'])
        # Pega apenas os primeiros 5 minutos de texto para não estourar os tokens
        texto_completo = " ".join([t['text'] for t in transcricao])[:8000]
        return f"[TRANSCRIÇÃO DO VÍDEO OBTIDA]:\n{texto_completo}\n\nResponda ao utilizador com base no conteúdo deste vídeo."
    except ImportError:
        return "[SISTEMA: O pacote 'youtube-transcript-api' não está instalado no servidor. Avise o utilizador.]"
    except Exception as e:
        return f"[SISTEMA: Não foi possível ler as legendas. Pode não ter legendas ativas. Erro: {str(e)}]"

# ==========================================
# BASE DE DADOS (SEM GHOST BUG)
# ==========================================
def carregar_db():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                return dados if isinstance(dados, dict) else {}
        except: return {}
    return {}

def salvar_db(db):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

def obter_usuario(db, email):
    if email not in db:
        db[email] = {"sessions": [], "plano": "Grátis", "tokens": LIMITES_TOKENS["Grátis"]}
    return db[email]

# ==========================================
# ROTAS FRONTEND E OAUTH
# ==========================================
@app.route('/')
def index():
    user = session.get('user')
    user_email = user.get("email", "visitante") if user else "visitante"
    db = carregar_db()
    if user:
        user_data = obter_usuario(db, user_email)
        salvar_db(db)
    else:
        user_data = {"sessions": [], "plano": "Visitante", "tokens": 0}
    return render_template('index.html', user=user, sessions=user_data.get("sessions", []), plano=user_data.get("plano", "Grátis"), tokens=user_data.get("tokens", 0))

@app.route('/checkout')
def checkout():
    user = session.get('user')
    if not user: return redirect('/login') 
    return render_template('checkout.html', user=user)

@app.route('/api/upgrade_plano', methods=['POST'])
def upgrade_plano():
    user = session.get('user')
    if not user: return jsonify({"error": "Não autenticado"}), 401
    novo_plano = request.json.get('plan')
    db = carregar_db()
    user_data = obter_usuario(db, user["email"])
    user_data["plano"] = novo_plano
    user_data["tokens"] = LIMITES_TOKENS.get(novo_plano, 500000)
    salvar_db(db)
    return jsonify({"status": "sucesso", "plano": novo_plano})

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
# GESTÃO DE SESSÕES
# ==========================================
@app.route('/new_chat', methods=['POST'])
def new_chat():
    u_email = session.get('user', {}).get("email", "visitante")
    db = carregar_db()
    user_data = obter_usuario(db, u_email)
    new_id = str(uuid.uuid4())
    new_sess = {"id": new_id, "title": "NOVA SESSÃO", "messages": [], "pinned": False, "archived": False}
    user_data["sessions"].insert(0, new_sess)
    salvar_db(db)
    return jsonify(new_sess)

@app.route('/api/toggle_pin', methods=['POST'])
def toggle_pin():
    cid = request.json.get('id')
    u_email = session.get('user', {}).get("email", "visitante")
    db = carregar_db()
    if u_email in db:
        for s in db[u_email].get("sessions", []):
            if s["id"] == cid:
                s["pinned"] = not s.get("pinned", False)
                break
        salvar_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/toggle_archive', methods=['POST'])
def toggle_archive():
    cid = request.json.get('id')
    u_email = session.get('user', {}).get("email", "visitante")
    db = carregar_db()
    if u_email in db:
        for s in db[u_email].get("sessions", []):
            if s["id"] == cid:
                s["archived"] = not s.get("archived", False)
                break
        salvar_db(db)
    return jsonify({"status": "ok"})

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

# ==========================================
# MOTOR DA IA (CHAT + AGENTE)
# ==========================================
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg_original = data.get('message')
    cid = data.get('chat_id')
    user = session.get('user')
    u_email = user.get("email", "visitante") if user else "visitante"
    
    if u_email == "visitante":
        return jsonify({"error": "Faça login para interagir."}), 401
    
    db = carregar_db()
    user_data = obter_usuario(db, u_email)
    
    if user_data["tokens"] <= 0:
        return jsonify({"response": "LIMITE DE TOKENS EXCEDIDO. Atualize o seu plano.", "tokens_restantes": 0})
    
    sessions = user_data.get("sessions", [])
    sess = next((s for s in sessions if s["id"] == cid), None)
    if not sess: return jsonify({"error": "Sessão não encontrada"}), 404

    # === AGENTE INTERCEPTADOR (YOUTUBE & GOOGLE) ===
    msg_processada = msg_original
    msg_lower = msg_original.lower()
    
    if "youtube" in msg_lower and "http" in msg_lower:
        # Extrai URL do youtube se existir na mensagem
        url_match = re.search(r'(https?://[^\s]+)', msg_original)
        if url_match:
            dados_youtube = ler_legenda_youtube(url_match.group(1))
            msg_processada = f"{msg_original}\n\n{dados_youtube}"
            
    elif "google" in msg_lower or "pesquise" in msg_lower:
        # Se pede para pesquisar, o Python vai à net raspar dados!
        termo_busca = msg_original.replace("pesquise no google", "").replace("busque no google", "").strip()
        dados_web = pesquisar_google(termo_busca if termo_busca else msg_original)
        msg_processada = f"{msg_original}\n\n{dados_web}"

    # Salva a mensagem visual (limpa)
    if not sess.get("messages"):
        try:
            res = client.chat.completions.create(model="llama3.1-8b", messages=[{"role": "system", "content": "Resumo em 2 palavras apenas."}, {"role": "user", "content": msg_original}], max_tokens=8)
            sess["title"] = res.choices[0].message.content.upper().replace('"', '')
        except: sess["title"] = "SESSÃO SOBERANA"
    
    # Gravamos a mensagem secreta (com os dados da web) no histórico para a IA ler, mas guardamos a limpa.
    sess["messages"].append({"role": "user", "content": msg_processada})
    
    plano_atual = user_data.get("plano", "Grátis")
    sys_prompt = "ANK 1.0 Soberana. Responda de forma elegante, baseada nos dados fornecidos se existirem."
    if plano_atual == "Pro": sys_prompt += " O utilizador é PRO. Responda com profundidade."
    elif plano_atual == "Plus": sys_prompt += " O utilizador é PLUS. Responda como a elite absoluta."
    
    try:
        res = client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "system", "content": sys_prompt}] + sess["messages"][-10:],
            max_tokens=4000
        )
        ans = res.choices[0].message.content
        
        # Volta a guardar a mensagem limpa para não sujar a tela do utilizador se ele recarregar a página
        sess["messages"][-1]["content"] = msg_original
        sess["messages"].append({"role": "assistant", "content": ans})
        
        tokens_gastos = (len(msg_processada) // 4) + (len(ans) // 4) + 12
        user_data["tokens"] -= tokens_gastos
        if user_data["tokens"] < 0: user_data["tokens"] = 0
        
        salvar_db(db)
        return jsonify({"response": ans, "title": sess["title"], "tokens_restantes": user_data["tokens"]})
        
    except Exception as e: 
        sess["messages"][-1]["content"] = msg_original # Reverte em caso de erro
        return jsonify({"response": f"ERRO DE NÚCLEO: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))