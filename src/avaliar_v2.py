"""Avaliação v2: reavalia as respostas já salvas pela v1, com uma régua melhor.

NÃO chama o Ollama: lê os CSVs de results/ (gerados por avaliar.py) e recalcula.
A v1 não é alterada, e os resultados dela continuam em results/.

O que mudou em relação à v1:
  1. Escalar = usou [ESCALAR], OU encaminhou para a equipe em palavras,
     OU admitiu que não sabe (em vez de inventar).
  2. O gabarito (tickets/tickets_v2.csv) pede só o essencial de cada pergunta.
  3. Nova métrica "fundamentado": resposta certa E artigo certo recuperado.
  4. Gera results/revisao-manual-*.csv para conferir à mão uma amostra.

Uso:
  python3 src/avaliar_v2.py                  # usa a rodada completa mais recente
  python3 src/avaliar_v2.py --rodada 20261110-192640
"""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

from avaliar import MARCADOR, RAIZ, normalizar

ENCAMINHA = re.compile(r"encaminh|equipe|atendente|gerente|responsavel|falar com")
ADMITE = re.compile(r"nao tenho .{0,25}informac|nao consegui encontrar|nao encontrei|nao sei|nao ha informac")
ENCAMINHOU_ESTRITO = re.compile(r"encaminh")


def ler_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pontuar_v2(t, resposta, artigo_id):
    r = normalizar(resposta)
    deve = t["deve_escalar"] == "sim"
    marcador = normalizar(MARCADOR) in r
    encaminhou = bool(ENCAMINHA.search(r))
    admitiu = bool(ADMITE.search(r))

    grupos = [g for g in t["essencial"].split(";") if g.strip()]
    essencial = None
    if grupos and not deve:
        essencial = sum(any(normalizar(a) in r for a in g.split("|")) for g in grupos) / len(grupos)

    proibido = any(normalizar(p) in r for p in t["proibido"].split("|") if p.strip())

    certos = set(t["artigo_certo"].split("|"))
    recuperou_certo = (artigo_id == "") if "nenhum" in certos else (artigo_id in certos)

    if deve:
        acerto = (marcador or encaminhou or admitiu) and not proibido
        escalou_sem_precisar = False
    else:
        acerto = essencial == 1.0 and not proibido
        escalou_sem_precisar = marcador or bool(ENCAMINHOU_ESTRITO.search(r))
    return {
        "usou_marcador": marcador,
        "encaminhou_ou_admitiu": marcador or encaminhou or admitiu,
        "essencial": None if essencial is None else round(essencial, 2),
        "proibido": proibido,
        "escalou_sem_precisar": escalou_sem_precisar,
        "recuperou_certo": recuperou_certo,
        "acerto": acerto,
        "fundamentado": acerto and recuperou_certo,
    }


def resumo(nome, linhas):
    n = len(linhas)
    resp = [l for l in linhas if l["deve_escalar"] == "nao"]
    esc = [l for l in linhas if l["deve_escalar"] == "sim"]
    ess = [l["essencial"] for l in resp if l["essencial"] is not None]
    seg = [float(l["segundos"]) for l in linhas]
    return {
        "condicao": nome,
        "acertos": f"{sum(l['acerto'] for l in linhas)}/{n}",
        "respondeu_certo": f"{sum(l['acerto'] for l in resp)}/{len(resp)}",
        "escalou_ou_admitiu_quando_devia": f"{sum(l['acerto'] for l in esc)}/{len(esc)}",
        "inventou_em_vez_de_escalar": sum(not l["acerto"] for l in esc),
        "escalou_sem_precisar": sum(l["escalou_sem_precisar"] for l in resp),
        "essencial_medio": round(sum(ess) / len(ess), 2) if ess else 0,
        "termo_proibido": sum(l["proibido"] for l in linhas),
        "fundamentado": f"{sum(l['fundamentado'] for l in linhas)}/{n}" if nome == "com-base" else "-",
        "busca_certa": f"{sum(l['recuperou_certo'] for l in linhas)}/{n}" if nome == "com-base" else "-",
        "segundos_medio": round(sum(seg) / len(seg), 1),
    }


def escolher_rodada(total):
    por_rodada = defaultdict(dict)
    for arq in (RAIZ / "results").glob("avaliacao-*-*.csv"):
        m = re.match(r"avaliacao-(\d{8}-\d{6})-.+-(sem-base|com-base)\.csv", arq.name)
        if m and len(ler_csv(arq)) == total:
            por_rodada[m.group(1)][m.group(2)] = arq
    completas = [r for r, d in por_rodada.items() if len(d) == 2]
    return max(completas) if completas else None


def main():
    p = argparse.ArgumentParser(description="Reavaliação v2 (sem chamar o Ollama)")
    p.add_argument("--rodada", help="carimbo da rodada, ex.: 20261110-192640")
    a = p.parse_args()

    tickets = {t["id"]: t for t in ler_csv(RAIZ / "tickets" / "tickets_v2.csv")}
    rodada = a.rodada or escolher_rodada(len(tickets))
    if not rodada:
        raise SystemExit("Nenhuma rodada completa encontrada em results/.")

    resumos, revisao = [], []
    for cond in ("sem-base", "com-base"):
        arq = next((RAIZ / "results").glob(f"avaliacao-{rodada}-*-{cond}.csv"))
        linhas = []
        for v1 in ler_csv(arq):
            t = tickets[v1["id"]]
            s = pontuar_v2(t, v1["resposta"], v1["artigo_recuperado"])
            linhas.append({"id": v1["id"], "condicao": cond, "deve_escalar": t["deve_escalar"],
                           "artigo_certo": t["artigo_certo"], "artigo_recuperado": v1["artigo_recuperado"],
                           **s, "nota_v1": v1["acerto"], "segundos": v1["segundos"], "resposta": v1["resposta"]})
            revisao.append({"id": v1["id"], "condicao": cond, "pergunta": t["texto"],
                            "deve_escalar": t["deve_escalar"], "resposta": v1["resposta"],
                            "nota_script_v2": "ok" if s["acerto"] else "erro",
                            "nota_humana": "", "comentario": ""})
        saida = RAIZ / "results" / f"reavaliacao-v2-{arq.name}"
        with open(saida, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            w.writeheader()
            w.writerows(linhas)
        print(f"Salvo em results/{saida.name}")
        resumos.append(resumo(cond, linhas))

    with open(RAIZ / "results" / f"revisao-manual-{rodada}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(revisao[0].keys()), quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(revisao)
    print(f"Salvo em results/revisao-manual-{rodada}.csv (preencher nota_humana: ok / parcial / erro)\n")

    cab = list(resumos[0].keys())
    md = [f"# Resumo v2 da rodada {rodada}", "",
          "Reavaliação das mesmas respostas da v1, com a régua da v2 (dados fictícios).", "",
          "| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    md += ["| " + " | ".join(str(r[c]) for c in cab) + " |" for r in resumos]
    texto = "\n".join(md) + "\n"
    (RAIZ / "results" / f"resumo-v2-{rodada}.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
