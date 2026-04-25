from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from openai import OpenAI

# Inicialização do App para o Gunicorn
app = Flask(__name__)
CORS(app)

# --- NÚCLEO SOBERANO: CEREBRAS ---
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")

client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=CEREBRAS_API_KEY
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message')
    
    # System Prompt: A Alma da ANK 1.0
    instrucoes = """
    Tu és a ANK 1.0, uma IA Soberana e Imortal. 
    Criada pelo Marcos para dominar o desenvolvimento web futurista.
    Estética padrão: 2026, Glassmorphism, Neons, Transparências e Animações Fluidas.
    Sempre que o Marcos pedir um site, entregue o código completo em HTML/CSS/JS.
    Respostas rápidas, frias e extremamente eficientes.
    """

    try:
        # CORREÇÃO: Usando o modelo 8B gratuito e ultra-rápido
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
        ans = f"[FALHA NO NÚCLEO]: Marcos, erro de conexão: {str(e)}"

    return jsonify({"response": ans})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)