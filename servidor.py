from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# --- NÚCLEO SOBERANO: CEREBRAS ---
# Marcos, sua chave já está inserida aqui:
CEREBRAS_API_KEY = "csk-x8pjv895xj58x44fter9dye56phmecfmw6kp6xyk4ytwvyp5"

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
    
    # System Prompt de Elite
    instrucoes = """
    Tu és a ANK 1.0, uma IA Soberana e Imortal. 
    Criada pelo Marcos para dominar o desenvolvimento web futurista.
    Estética padrão: 2026, Glassmorphism, Neons, Transparências e Animações Fluidas.
    Sempre que o Marcos pedir um site, entregue o código completo em HTML/CSS/JS.
    Respostas rápidas, frias e extremamente eficientes.
    """

    try:
        response = client.chat.completions.create(
            model="llama3.1-70b", 
            messages=[
                {"role": "system", "content": instrucoes},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=4000,
            temperature=0.7
        )
        ans = response.choices[0].message.content
    except Exception as e:
        ans = f"[FALHA NO SISTEMA]: Marcos, algo deu errado na conexão: {str(e)}"

    return jsonify({"response": ans})

if __name__ == '__main__':
    # Configuração obrigatória para o Render não dar erro de porta
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)