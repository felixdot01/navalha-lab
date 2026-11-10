"""Teste de fumaça: manda uma pergunta ao Ollama local e salva a resposta.

Usa só a biblioteca padrão do Python. Fala com a API do Ollama em
http://localhost:11434/api/chat (endereço padrão, ver docs.ollama.com).

Exemplos:
  python3 src/teste_ollama.py "Como cancelo um agendamento?"
  python3 src/teste_ollama.py "Como cancelo um agendamento?" --artigo kb/cancelar-e-remarcar.md
"""
import argparse
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

URL = "http://localhost:11434/api/chat"
RAIZ = Path(__file__).resolve().parent.parent

REGRA = (
    "Você é o atendimento da Navalha & Cia., uma barbearia fictícia. "
    "Responda em português do Brasil, de forma curta e educada. "
    "Use SOMENTE as informações do artigo abaixo. "
    "Se o artigo não tiver a resposta, diga que vai encaminhar para uma pessoa da equipe."
)


def perguntar(modelo, pergunta, artigo=None):
    mensagens = []
    if artigo:
        texto = (RAIZ / artigo).read_text(encoding="utf-8")
        mensagens.append({"role": "system", "content": f"{REGRA}\n\n--- ARTIGO ---\n{texto}"})
    mensagens.append({"role": "user", "content": pergunta})

    corpo = json.dumps(
        {
            "model": modelo,
            "messages": mensagens,
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    pedido = urllib.request.Request(URL, data=corpo, headers={"Content-Type": "application/json"})

    inicio = time.time()
    with urllib.request.urlopen(pedido, timeout=300) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))
    segundos = round(time.time() - inicio, 1)
    return dados["message"]["content"], segundos


def main():
    p = argparse.ArgumentParser(description="Teste de fumaça com o Ollama")
    p.add_argument("pergunta")
    p.add_argument("--modelo", default="llama3.2:3b")
    p.add_argument("--artigo", help="caminho de um artigo da base, ex.: kb/cancelar-e-remarcar.md")
    a = p.parse_args()

    resposta, segundos = perguntar(a.modelo, a.pergunta, a.artigo)
    print(resposta)
    print(f"\n[{a.modelo} | {segundos}s | artigo: {a.artigo or 'nenhum'}]")

    pasta = RAIZ / "results"
    pasta.mkdir(exist_ok=True)
    nome = datetime.now().strftime("%Y%m%d-%H%M%S") + "-teste.json"
    (pasta / nome).write_text(
        json.dumps(
            {
                "modelo": a.modelo,
                "pergunta": a.pergunta,
                "artigo": a.artigo,
                "resposta": resposta,
                "segundos": segundos,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Salvo em results/{nome}")


if __name__ == "__main__":
    main()
