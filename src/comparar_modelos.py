"""Compara todos os modelos já avaliados, usando a régua v2.

Não chama o Ollama: lê os CSVs de results/ gerados por avaliar.py
(só rodadas completas: 30 tickets, nas duas condições).

Uso:
  python3 src/comparar_modelos.py
"""
import re
from collections import defaultdict

from avaliar import RAIZ
from avaliar_v2 import ler_csv, pontuar_v2, resumo


def main():
    tickets = {t["id"]: t for t in ler_csv(RAIZ / "tickets" / "tickets_v2.csv")}
    rodadas = defaultdict(dict)
    for arq in sorted((RAIZ / "results").glob("avaliacao-*.csv")):
        m = re.match(r"avaliacao-(\d{8}-\d{6})-(.+)-(sem-base|com-base)\.csv", arq.name)
        if m and len(ler_csv(arq)) == len(tickets):
            rodadas[(m.group(1), m.group(2))][m.group(3)] = arq

    linhas_tabela = []
    for (rodada, modelo), arqs in sorted(rodadas.items(), key=lambda x: (x[0][1], x[0][0])):
        if len(arqs) < 2:
            continue
        for cond in ("sem-base", "com-base"):
            linhas = []
            for v1 in ler_csv(arqs[cond]):
                t = tickets[v1["id"]]
                s = pontuar_v2(t, v1["resposta"], v1["artigo_recuperado"])
                linhas.append({"deve_escalar": t["deve_escalar"], "segundos": v1["segundos"], **s})
            r = resumo(cond, linhas)
            linhas_tabela.append({"modelo": modelo, "rodada": rodada, **r})

    if not linhas_tabela:
        raise SystemExit("Nenhuma rodada completa encontrada em results/.")

    cab = ["modelo", "rodada", "condicao", "acertos", "respondeu_certo",
           "escalou_ou_admitiu_quando_devia", "inventou_em_vez_de_escalar",
           "escalou_sem_precisar", "fundamentado", "busca_certa", "segundos_medio"]
    md = ["# Comparação de modelos (régua v2, dados fictícios)", "",
          "Mesmos 30 tickets e mesma base para todos. A nota é automática (por palavras) e",
          "pode errar para mais ou para menos: confira a revisão manual antes de citar números.", "",
          "| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    md += ["| " + " | ".join(str(l[c]) for c in cab) + " |" for l in linhas_tabela]
    texto = "\n".join(md) + "\n"
    (RAIZ / "results" / "comparacao-modelos.md").write_text(texto, encoding="utf-8")
    print(texto)
    print("Salvo em results/comparacao-modelos.md")


if __name__ == "__main__":
    main()
