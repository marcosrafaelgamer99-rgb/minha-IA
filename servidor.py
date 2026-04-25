from flask import Flask, render_template, request, jsonify, url_for, session, redirect
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from openai import OpenAI

app = Flask(__name__)

# --- CORREÇÃO VITAL PARA O RENDER ---
# Avisa o Flask que estamos atrás de um proxy seguro (HTTPS)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

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
    # Redireciona pro Google garantindo que usa HTTPS
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    try:
        # Recebe o token do Google
        token = google.authorize_access_token()
        
        # Extrai a informação do usuário de forma segura
        user_info = token.get('userinfo')
        if not user_info:
            # Fallback caso o token não traga a info embutida
            resp = google.get('https://openidconnect.googleapis.com/v1/userinfo')
            user_info = resp.json()
            
        session['user'] = user_info
        return redirect('/')
    except Exception as e:
        # Em vez do Erro 500 em branco, mostra o que falhou
        return f"<h3>Falha no protocolo de Login ANK:</h3><p>{str(e)}</p><a href='/'>Voltar ao Sistema</a>", 400

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
    Estética padrão: 2026, Glassmorphism. Entregue código completo em blocos.
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
        ans = f"[FALHA NO NÚCLEO]: Erro de conexão neural: {str(e)}"

    return jsonify({"response": ans})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)