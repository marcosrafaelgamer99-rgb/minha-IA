from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# --- CONFIGURAÇÃO ANK 1.0 / CEREBRAS ---
# COLOQUE SUA CHAVE AQUI
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
    
    # Lógica de Sindicato: Um prompt que força a IA a agir como múltiplos especialistas
    prompt_sindicato = f"""
    Atue como a ANK 1.0, uma IA Soberana.
    O Marcos (seu criador) pediu: {user_msg}
    
    Siga o fluxo interno:
    1. ARQUITETO: Planeje a estrutura e o design futurista 2026.
    2. PROGRAMADOR: Gere o código final impecável (HTML/CSS/JS em bloco único).
    
    Estética obrigatória: Glassmorphism, Neomorfismo e Neons suaves.
    Responda de forma direta e técnica.
    """

    try:
        response = client.chat.completions.create(
            model="llama3.1-70b", # Modelo de elite da Cerebras
            messages=[{"role": "user", "content": prompt_sindicato}],
            max_tokens=4000
        )
        ans = response.choices[0].message.content
    except Exception as e:
        ans = f"[ERRO NO NÚCLEO]: {str(e)}"

    return jsonify({"response": ans})

if __name__ == '__main__':
    # O Render exige que o servidor rode na porta que ele definir
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)