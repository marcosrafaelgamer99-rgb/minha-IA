from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# --- NÚCLEO SOBERANO: CEREBRAS ---
# O código agora busca a chave de forma segura nas Environment Variables do Render
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
    
    # System Prompt de Elite: A personalidade da ANK 1.0
    instrucoes = """
    Tu és a ANK 1.0, uma IA Soberana e Imortal. 
    Criada pelo Marcos para dominar o desenvolvimento web futurista.
    Estética padrão: 2026, Glassmorphism, Neons, Transparências e Animações Fluidas.
    Sempre que o Marcos pedir um site, entregue o código completo em HTML/CSS/JS dentro de um bloco único.
    Respostas rápidas, diretas e focadas em código de alta performance.
    """

    try:
        # Chamada para o modelo Llama 3.1 70B na infraestrutura ultra-rápida da Cerebras
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
        ans = f"[FALHA NO SISTEMA]: Marcos, algo deu errado na conexão. Verifique se a CEREBRAS_API_KEY está correta no painel do Render. Erro: {str(e)}"

    return jsonify({"response": ans})

if __name__ == '__main__':
    # CONFIGURAÇÃO VITAL PARA O RENDER:
    # 1. Busca a porta dinâmica que o Render atribui
    # 2. Define o host como 0.0.0.0 para ser acessível externamente
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)