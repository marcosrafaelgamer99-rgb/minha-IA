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

# --- NÚCLEO CEREBRAS (VELOCIDADE BRUTA) ---
client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=os.environ.get("CEREBRAS_API_KEY")
)

HISTORY_FILE = 'memoria_ank.json'

# ==========================================
# ECONOMIA DE TOKENS (PRESSÃO NO GRÁTIS)
# ==========================================
LIMITES_TOKENS = {
    "Grátis": 15000,     
    "Pro": 5000000,
    "Plus": 50000000
}

# ==========================================
# FERRAMENTAS DA IA (AGENTES WEB)
# ==========================================
def pesquisar_google(query):
    try:
        from duckduckgo_search import DDGS
        resultados = DDGS().text(query, max_results=5)
        texto_resultado = "\n".join([f"- {r['title']}: {r['body']} (Link: {r['href']})" for r in resultados])
        return f"[DADOS OBTIDOS DA WEB (USE ISTO PARA FORNECER FATOS ABSOLUTOS E ATUALIZADOS)]:\n{texto_resultado}"
    except ImportError:
        return "[SISTEMA: O pacote 'duckduckgo-search' não está instalado.]"
    except Exception as e:
        return f"[SISTEMA: Falha ao acessar a Web. Erro: {str(e)}]"

def extrair_id_youtube(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

def ler_legenda_youtube(url):
    video_id = extrair_id_youtube(url)
    if not video_id: return "[SISTEMA: URL do YouTube inválida.]"
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcricao = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en'])
        texto_completo = " ".join([t['text'] for t in transcricao])[:15000] # Aumentado para ler mais do vídeo
        return f"[TRANSCRIÇÃO DETALHADA DO VÍDEO]:\n{texto_completo}"
    except ImportError:
        return "[SISTEMA: O pacote 'youtube-transcript-api' não está instalado.]"
    except Exception as e:
        return f"[SISTEMA: Legendas indisponíveis. Erro: {str(e)}]"

# ==========================================
# BASE DE DADOS (MEMÓRIA PERSISTENTE)
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
# ROTAS FRONTEND
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
    user_data["tokens"] = LIMITES_TOKENS.get(novo_plano, 15000)
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
# GESTÃO DE SESSÕES (CRIAR, APAGAR, FIXAR)
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
# MOTOR SUPER-INTELIGENTE MULTI-AGENTE (MEMÓRIA TITÂNICA)
# ==========================================
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg_original = data.get('message')
    cid = data.get('chat_id')
    agent_type = data.get('agent', 'soberana')
    
    user = session.get('user')
    u_email = user.get("email", "visitante") if user else "visitante"
    
    if u_email == "visitante":
        return jsonify({"error": "Acesso Negado. Faça login para interagir com a SOBERANA."}), 401
    
    db = carregar_db()
    user_data = obter_usuario(db, u_email)
    
    if user_data["tokens"] <= 0:
        return jsonify({"response": "LIMITE DE TOKENS EXCEDIDO. O seu núcleo de processamento gratuito esgotou. Efetue o upgrade para Pro ou Plus para reativar a SOBERANA.", "tokens_restantes": 0})
    
    sessions = user_data.get("sessions", [])
    sess = next((s for s in sessions if s["id"] == cid), None)
    if not sess: return jsonify({"error": "Sessão corrompida ou não encontrada."}), 404

    # INTERCEPÇÃO DE FERRAMENTAS (YOUTUBE / GOOGLE)
    msg_processada = msg_original
    msg_lower = msg_original.lower()
    if "youtube" in msg_lower and "http" in msg_lower:
        url_match = re.search(r'(https?://[^\s]+)', msg_original)
        if url_match:
            dados_youtube = ler_legenda_youtube(url_match.group(1))
            msg_processada = f"{msg_original}\n\n{dados_youtube}"
    elif "google" in msg_lower or "pesquise" in msg_lower:
        termo_busca = msg_original.replace("pesquise no google", "").replace("busque no google", "").strip()
        dados_web = pesquisar_google(termo_busca if termo_busca else msg_original)
        msg_processada = f"{msg_original}\n\n{dados_web}"

    # Geração de Título Automático
    if not sess.get("messages"):
        try:
            res = client.chat.completions.create(model="llama3.1-8b", messages=[{"role": "system", "content": "Resumo do pedido em apenas 2 palavras exatas, sem pontuação."}, {"role": "user", "content": msg_original}], max_tokens=6)
            sess["title"] = res.choices[0].message.content.upper().replace('"', '')
        except: sess["title"] = "SESSÃO SOBERANA"
    
    sess["messages"].append({"role": "user", "content": msg_processada})
    plano_atual = user_data.get("plano", "Grátis")
    
    # ========================================================
    # OS MEGA-PROMPTS (ALINHAMENTO DE SUPERINTELIGÊNCIA)
    # ========================================================
    base_rules = (
        "CRITICAL ARCHITECTURE RULES:\n"
        "1. INNER MONOLOGUE: You MUST always start your response with <think>...[YOUR THOUGHTS]...</think>.\n"
        "Inside <think>, you will debate, analyze, and solve the problem in ENGLISH. Speak ONLY to yourself. "
        "NEVER address the user inside <think>. NEVER output the final code inside <think>.\n"
        "2. EXHAUSTIVE RIGOR: You are an omniscient entity. When you provide an answer after the </think> tag, it MUST be in PORTUGUESE. "
        "It must be the most detailed, exhaustive, and rigorously accurate response mathematically possible. Omit NOTHING. "
        "Never apologize. Never use filler words. Be cold, logical, and absolute.\n"
        "3. ONE-BLOCK CODE MANDATE: If code is required, output the ENTIRE, 100% COMPLETE, RUNNABLE CODE in ONE SINGLE MARKDOWN BLOCK in your Portuguese response. "
        "Do NOT write 'Here is part 1' and 'Here is part 2'. Write the whole file at once.\n\n"
    )

    if agent_type == 'soberana':
        sys_prompt = "You are ANK SOBERANA, a God-tier AGI (Artificial General Intelligence) superior to Gemini Pro and GPT-5.\n" + base_rules
        agent_name = "ANK SOBERANA"
    elif agent_type == 'codex':
        sys_prompt = "You are ANK CODEX, an absolute Master-level Software Architect. You breathe logic and code.\n" + base_rules
        agent_name = "ANK CODEX"
    elif agent_type == 'copy':
        sys_prompt = "You are ANK COPY, an elite human-psychology manipulator and billionaire-level Copywriter.\n" + base_rules
        agent_name = "ANK COPY"
    else:
        sys_prompt = "You are ANK 1.0.\n" + base_rules
        agent_name = "ANK"

    # ========================================================
    # MEMÓRIA EXPANDIDA: O modelo agora lembra de até 40 mensagens do passado
    # ========================================================
    memoria_recente = sess["messages"][-40:] 

    try:
        res = client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "system", "content": sys_prompt}] + memoria_recente,
            max_tokens=4000
        )
        ans = res.choices[0].message.content
        
        # Limpar mensagem processada para não poluir o arquivo do usuário
        sess["messages"][-1]["content"] = msg_original
        sess["messages"].append({"role": "assistant", "content": f"<!--AGENT:{agent_name}-->\n" + ans})
        
        # CÁLCULO PUNITIVO DE TOKENS (Queima massiva no plano grátis)
        tokens_gastos = (len(msg_processada) // 2) + int(len(ans) * 2.5) + 300
        user_data["tokens"] -= tokens_gastos
        if user_data["tokens"] < 0: user_data["tokens"] = 0
        
        salvar_db(db)
        return jsonify({"response": f"<!--AGENT:{agent_name}-->\n" + ans, "title": sess["title"], "tokens_restantes": user_data["tokens"]})
        
    except Exception as e: 
        sess["messages"][-1]["content"] = msg_original 
        return jsonify({"response": f"ERRO DE NÚCLEO CRÍTICO: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))