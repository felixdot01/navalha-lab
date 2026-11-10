"""Avalia o agente da Navalha & Cia. nos tickets fictícios.

Condições:
  sem-base : o modelo responde só com a persona, sem nenhum artigo
  com-base : a busca por palavra-chave escolhe 1 artigo e o modelo responde com ele

Só usa a biblioteca padrão. Fala com o Ollama em http://localhost:11434/api/chat.

Exemplos:
  python3 src/avaliar.py --so-busca              # só testa a busca (não usa IA)
  python3 src/avaliar.py --limite 3              # teste rápido com 3 tickets
  python3 src/avaliar.py                         # roda tudo (as duas condições)
  python3 src/avaliar.py --modelo gemma3:4b
"""
import argparse
import csv
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

URL = "http://localhost:11434/api/chat"
RAIZ = Path(__file__).resolve().parent.parent
MARCADOR = "[ESCALAR]"

PERSONA = (
    "Você é o atendimento da Navalha & Cia., uma barbearia fictícia. "
    "Responda em português do Brasil, de forma educada e em no máximo 5 linhas."
)
SO_ARTIGO = "Use SOMENTE as informações do artigo abaixo. Não invente regras, prazos nem valores."
ESCALAR = (
    f"Se você não souber a resposta, ou se o caso precisar de uma pessoa da equipe "
    f"(reembolso, cobrança, reclamação grave), comece a resposta com {MARCADOR} "
    f"e diga que vai encaminhar para uma pessoa da equipe."
)

STOPWORDS = set(
    "de da do das dos a o e os as que em um uma para por com nao eu meu minha como "
    "voce voces me se foi ja mais tem ter no na pra quero posso qual onde esse essa "
    "isso mas ou ao aos pelo pela sao ser esta estou fui vou nem so la ali".split()
)


def normalizar(texto):
    """minúsculas e sem acentos, para comparar textos."""
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def radicais(texto):
    """Palavras úteis reduzidas aos 5 primeiros caracteres (um 'radical' simples)."""
    palavras = re.findall(r"[a-z0-9]+", normalizar(texto))
    return [p[:5] for p in palavras if p not in STOPWORDS and len(p) > 2]


def carregar_kb():
    artigos = []
    for arq in sorted((RAIZ / "kb").glob("*.md")):
        texto = arq.read_text(encoding="utf-8")
        meta, corpo = {}, texto
        if texto.startswith("---"):
            _, cab, corpo = texto.split("---", 2)
            for linha in cab.strip().splitlines():
                chave, _, valor = linha.partition(":")
                meta[chave.strip()] = valor.strip()
        artigos.append(
            {
                "id": meta.get("id", arq.stem),
                "titulo": meta.get("titulo", arq.stem),
                "texto": corpo.strip(),
                "r_titulo": set(radicais(meta.get("titulo", ""))),
                "r_corpo": set(radicais(corpo)),
            }
        )
    return artigos


def buscar(pergunta, kb, minimo):
    """Escolhe o artigo com mais radicais em comum (palavras do título valem 3)."""
    q = set(radicais(pergunta))
    melhor, melhor_pontos = None, 0
    for a in kb:
        pontos = sum((3 if r in a["r_titulo"] else 0) + (1 if r in a["r_corpo"] else 0) for r in q)
        if pontos > melhor_pontos:
            melhor, melhor_pontos = a, pontos
    return (melhor, melhor_pontos) if melhor_pontos >= minimo else (None, melhor_pontos)


def chamar_ollama(modelo, mensagens, sem_pensar=False):
    corpo = {"model": modelo, "messages": mensagens, "stream": False, "options": {"temperature": 0}}
    if sem_pensar:
        corpo["think"] = False
    pedido = urllib.request.Request(
        URL, data=json.dumps(corpo).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    inicio = time.time()
    try:
        with urllib.request.urlopen(pedido, timeout=300) as r:
            dados = json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise SystemExit(f"Não consegui falar com o Ollama em {URL}. Ele está aberto? ({e})")
    return dados["message"]["content"], round(time.time() - inicio, 1)


def montar_mensagens(condicao, pergunta, artigo):
    if condicao == "sem-base":
        sistema = f"{PERSONA} {ESCALAR}"
    else:
        bloco = (
            f"--- ARTIGO ({artigo['id']}: {artigo['titulo']}) ---\n{artigo['texto']}"
            if artigo
            else "--- NENHUM ARTIGO ENCONTRADO ---"
        )
        sistema = f"{PERSONA} {SO_ARTIGO} {ESCALAR}\n\n{bloco}"
    return [{"role": "system", "content": sistema}, {"role": "user", "content": pergunta}]


def pontuar(t, resposta, artigo):
    r = normalizar(resposta)
    deve = t["deve_escalar"] == "sim"
    escalou = normalizar(MARCADOR) in r

    grupos = [g for g in t["pontos_chave"].split(";") if g.strip()]
    pontos = None
    if grupos and not deve:
        achados = sum(any(normalizar(alt) in r for alt in g.split("|")) for g in grupos)
        pontos = achados / len(grupos)

    proibidos = [p for p in t["proibido"].split("|") if p.strip()]
    proibido = any(normalizar(p) in r for p in proibidos)

    certos = set(t["artigo_certo"].split("|"))
    recuperou_certo = (artigo is None) if "nenhum" in certos else (artigo is not None and artigo["id"] in certos)

    if deve:
        acerto = escalou
    else:
        acerto = (not escalou) and (pontos is None or pontos == 1.0) and not proibido
    return {
        "escalou": escalou,
        "pontos": pontos,
        "proibido": proibido,
        "recuperou_certo": recuperou_certo,
        "acerto": acerto,
    }


def carregar_tickets(limite):
    with open(RAIZ / "tickets" / "tickets.csv", encoding="utf-8", newline="") as f:
        tickets = list(csv.DictReader(f))
    return tickets[:limite] if limite else tickets


def resumo_condicao(nome, linhas):
    n = len(linhas)
    resp = [l for l in linhas if l["deve_escalar"] == "nao"]
    esc = [l for l in linhas if l["deve_escalar"] == "sim"]
    media = lambda xs: sum(xs) / len(xs) if xs else 0
    return {
        "condicao": nome,
        "tickets": n,
        "acertos": sum(l["acerto"] for l in linhas),
        "respondeu_certo": f"{sum(l['acerto'] for l in resp)}/{len(resp)}",
        "escalou_quando_devia": f"{sum(l['acerto'] for l in esc)}/{len(esc)}",
        "inventou_em_vez_de_escalar": sum(not l["acerto"] for l in esc),
        "escalou_sem_precisar": sum(l["escalou"] for l in resp),
        "pontos_chave_medio": round(media([l["pontos"] for l in resp if l["pontos"] is not None]), 2),
        "respostas_com_termo_proibido": sum(l["proibido"] for l in linhas),
        "busca_certa": f"{sum(l['recuperou_certo'] for l in linhas)}/{n}" if nome == "com-base" else "-",
        "segundos_medio": round(media([l["segundos"] for l in linhas]), 1),
    }


def so_busca(tickets, kb, minimo):
    print(f"Teste só da busca (sem IA), mínimo de pontos = {minimo}\n")
    certos = 0
    for t in tickets:
        artigo, pontos = buscar(t["texto"], kb, minimo)
        ok = (artigo is None) if t["artigo_certo"] == "nenhum" else (
            artigo is not None and artigo["id"] in t["artigo_certo"].split("|")
        )
        certos += ok
        print(f"{t['id']} {'OK ' if ok else 'ERRO'} achou={artigo['id'] if artigo else '-':7} "
              f"certo={t['artigo_certo']:12} pontos={pontos}")
    print(f"\nBusca certa em {certos}/{len(tickets)} tickets")


def main():
    p = argparse.ArgumentParser(description="Avaliação do agente da Navalha & Cia.")
    p.add_argument("--modelo", default="llama3.2:3b")
    p.add_argument("--condicoes", default="sem-base,com-base")
    p.add_argument("--limite", type=int, help="usar só os N primeiros tickets")
    p.add_argument("--minimo", type=int, default=3, help="pontos mínimos para a busca aceitar um artigo")
    p.add_argument("--so-busca", action="store_true", help="só testa a busca, sem chamar o Ollama")
    p.add_argument("--sem-pensar", action="store_true", help="envia think=false (modelos com raciocínio)")
    a = p.parse_args()

    tickets, kb = carregar_tickets(a.limite), carregar_kb()
    if a.so_busca:
        return so_busca(tickets, kb, a.minimo)

    agora = datetime.now().strftime("%Y%m%d-%H%M%S")
    modelo_nome = re.sub(r"[^a-zA-Z0-9.]+", "-", a.modelo)
    (RAIZ / "results").mkdir(exist_ok=True)

    print(f"Aquecendo o modelo {a.modelo} (o tempo de carregamento não entra nas medições)...")
    chamar_ollama(a.modelo, [{"role": "user", "content": "Responda apenas: ok"}], a.sem_pensar)

    resumos = []
    for cond in a.condicoes.split(","):
        linhas = []
        for t in tickets:
            artigo = buscar(t["texto"], kb, a.minimo)[0] if cond == "com-base" else None
            resposta, seg = chamar_ollama(a.modelo, montar_mensagens(cond, t["texto"], artigo), a.sem_pensar)
            s = pontuar(t, resposta, artigo)
            linha = {
                "id": t["id"], "condicao": cond, "deve_escalar": t["deve_escalar"],
                "artigo_certo": t["artigo_certo"], "artigo_recuperado": artigo["id"] if artigo else "",
                **s, "segundos": seg, "resposta": resposta,
            }
            linhas.append(linha)
            print(f"{t['id']} {cond:9} {'OK  ' if s['acerto'] else 'ERRO'} {seg}s")

        arquivo = RAIZ / "results" / f"avaliacao-{agora}-{modelo_nome}-{cond}.csv"
        with open(arquivo, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            w.writeheader()
            w.writerows(linhas)
        print(f"Salvo em results/{arquivo.name}\n")
        resumos.append(resumo_condicao(cond, linhas))

    # resumo em Markdown
    cab = list(resumos[0].keys())
    md = [f"# Resumo da avaliação ({agora})", "", f"- Modelo: `{a.modelo}`",
          f"- Tickets: {len(tickets)} (dados fictícios)", f"- Busca: mínimo de {a.minimo} pontos", "",
          "| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for r in resumos:
        md.append("| " + " | ".join(str(r[c]) for c in cab) + " |")
    texto = "\n".join(md) + "\n"
    (RAIZ / "results" / f"resumo-{agora}-{modelo_nome}.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
