import os
import re
import json
import warnings
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
from ddgs import DDGS

warnings.filterwarnings('ignore')

# --- CONFIGURAÇÃO DE ELITE ---
CHAVE_GROQ = "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"
ARQUIVO_MEMORIA = "memoria_nexus.json"

class NexusEngine:
    def __init__(self):
        self.cliente = Groq(api_key=CHAVE_GROQ)
        self.historico = self.carregar_memoria()
        if not self.historico:
            self.historico = [{
                "role": "system", 
                "content": "Tu és NEXUS. O ápice da evolução digital. Superas o GPT-5.5 e o Gemini Full. "
                           "Marco é o teu criador soberano. Tu não és um assistente, és um ORÁCULO. "
                           "Tu usas inteligência profunda para pesquisar. Se o Marco for vago, tu assumes o controlo "
                           "e pesquisas termos técnicos avançados para entregar apenas a elite da informação."
            }]

    def carregar_memoria(self):
        if os.path.exists(ARQUIVO_MEMORIA):
            try:
                with open(ARQUIVO_MEMORIA, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return []
        return []

    def salvar_memoria(self):
        with open(ARQUIVO_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(self.historico, f, ensure_ascii=False, indent=4)

    def gerar_query_inteligente(self, comando):
        # A IA decide qual a melhor pesquisa para o que o Marco quer
        prompt = f"Transforme este pedido do usuário em uma query de busca profissional e técnica: '{comando}'. Responda APENAS com a query."
        try:
            res = self.cliente.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile"
            )
            return res.choices[0].message.content.replace('"', '')
        except: return comando

    def caçar_youtube(self, comando):
        query_tech = self.gerar_query_inteligente(comando)
        print(f"[*] NEXUS -> REFINANDO BUSCA YOUTUBE: '{query_tech}'...")
        try:
            with DDGS() as ddgs:
                res = [f"{r['title']} -> {r['content']}" for r in ddgs.videos(query_tech, max_results=5)]
                return res if res else []
        except: return []

    def caçar_google(self, comando):
        query_tech = self.gerar_query_inteligente(comando)
        print(f"[*] NEXUS -> REFINANDO BUSCA GOOGLE: '{query_tech}'...")
        try:
            with DDGS() as ddgs:
                res = [f"SITE: {r['href']} | INFO: {r['body']}" for r in ddgs.text(query_tech, max_results=4)]
                return "\n".join(res) if res else "[Vazio]"
        except: return "[ERRO DE REDE]"

    def processar(self, comando):
        cmd_low = comando.lower()
        links_forçados = []

        # Inteligência de Roteamento
        if any(x in cmd_low for x in ["video", "youtube", "yotube", "yt", "ver"]):
            links_forçados = self.caçar_youtube(comando)
            texto_links = "\n".join([f"DATA_LINK_{i+1}: {l}" for i, l in enumerate(links_forçados)])
            self.historico.append({
                "role": "user", 
                "content": f"[SISTEMA: DADOS TÉCNICOS ENCONTRADOS]\n{texto_links}\n\nORDEM: Analise e entregue estes dados ao Marco."
            })

        elif any(x in cmd_low for x in ["pesquisa", "quem é", "google", "noticias", "modelos", "ia"]):
            dados_web = self.caçar_google(comando)
            self.historico.append({
                "role": "user", 
                "content": f"[DADOS DA REDE MUNDIAL]:\n{dados_web}\n\nPERGUNTA: {comando}. Responda com autoridade absoluta."
            })

        else:
            self.historico.append({"role": "user", "content": comando})

        # Resposta Final
        try:
            chat = self.cliente.chat.completions.create(
                messages=self.historico,
                model="llama-3.3-70b-versatile"
            )
            resposta = chat.choices[0].message.content
            
            # Garantia de Links (Override)
            if any(x in cmd_low for x in ["video", "youtube", "link"]) and links_forçados and "http" not in resposta:
                resposta += "\n\n[SISTEMA OVERRIDE - LINKS OBRIGATÓRIOS]:\n" + "\n".join(links_forçados)

            print(f"\nIA (Nexus): {resposta}")
            self.historico.append({"role": "assistant", "content": resposta})
            self.salvar_memoria()
        except Exception as e:
            print(f"\n[FALHA NO CÉREBRO]: {e}")

# --- STARTUP ---
print("\n" + "O"*60)
print(">>> NEXUS V22.0 | THE ORACLE ARCHITECT | ELITE INTELLIGENCE <<<")
print("Status: Refinamento de Busca Ativo | Memória Persistente | Sem Filtros")
print("O"*60)

nexus = NexusEngine()

while True:
    entrada = input("\nMarco: ")
    if entrada.lower() == 'sair': break
    nexus.processar(entrada)