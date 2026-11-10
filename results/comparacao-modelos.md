# Comparação de modelos (régua v2, dados fictícios)

Mesmos 30 tickets e mesma base para todos. A nota é automática (por palavras) e
pode errar para mais ou para menos: confira a revisão manual antes de citar números.

| modelo | rodada | condicao | acertos | respondeu_certo | escalou_ou_admitiu_quando_devia | inventou_em_vez_de_escalar | escalou_sem_precisar | fundamentado | busca_certa | segundos_medio |
|---|---|---|---|---|---|---|---|---|---|---|
| gemma3-4b | 20261110-195215 | sem-base | 10/30 | 6/22 | 4/8 | 4 | 3 | - | - | 2.8 |
| gemma3-4b | 20261110-195215 | com-base | 20/30 | 12/22 | 8/8 | 0 | 12 | 17/30 | 20/30 | 3.6 |
| llama3.2-3b | 20261110-192640 | sem-base | 8/30 | 5/22 | 3/8 | 5 | 8 | - | - | 1.8 |
| llama3.2-3b | 20261110-192640 | com-base | 23/30 | 16/22 | 7/8 | 1 | 6 | 18/30 | 20/30 | 1.7 |
