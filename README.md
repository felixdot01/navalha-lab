# Navalha & Cia. Lab

Laboratório do blog [Hefsto](https://hefsto.com): uma base de conhecimento e 30 tickets de suporte **fictícios**, usados para testar dois modelos de IA que rodam no próprio computador, com e sem a base de conhecimento.

> **Tudo aqui é inventado.** A Navalha & Cia., os artigos, as regras e os tickets foram criados para este experimento. Qualquer semelhança com um negócio real é coincidência. Não há dados de clientes.

## O que foi testado

- **Cenário:** barbearia fictícia com app de agendamento. 12 artigos de ajuda (`kb/`) e 30 tickets com gabarito (`tickets/`): 22 que a base responde, 4 que devem ir para uma pessoa e 4 que a base não cobre.
- **Modelos:** `llama3.2:3b` (Meta) e `gemma3:4b` (Google), rodando no [Ollama](https://docs.ollama.com/).
- **Duas condições:** *sem base* (o modelo só recebe a persona de atendente) e *com base* (uma busca simples por palavra-chave escolhe um artigo e o entrega ao modelo).
- **Regra de escalada:** se não souber, ou se o caso precisar de uma pessoa, o modelo deve começar a resposta com `[ESCALAR]`.
- **Ambiente:** MacBook com 8 GB, Ollama 0.40.16, Python 3.15.2 (só biblioteca padrão), temperatura 0, uma rodada.

## Resultado (revisão manual das 30 respostas de cada caso)

| Modelo | Condição | ok | parcial | erro |
|---|---|---|---|---|
| llama3.2:3b | sem base | 2 | 13 | 15 |
| llama3.2:3b | com base | 18 | 7 | 5 |
| gemma3:4b | sem base | 6 | 6 | 18 |
| gemma3:4b | com base | 14 | 11 | 5 |

Critério: `ok` = correta, útil e sem inventar; `parcial` = não inventou, mas não resolveu o que a base resolvia (por exemplo, escalou sem precisar); `erro` = errada, inventou regra, dado ou promessa, ou usou o artigo errado. As notas e os motivos estão em `results/revisao-manual-claude.csv`.

Pontos de atenção:

- A primeira passada da revisão manual foi feita com a ajuda do Claude (assistente de IA); a conferência por amostra pelo autor ainda está pendente.
- Há duas versões da nota automática. A **v1** só aceitava `[ESCALAR]` como escalada e foi considerada rígida demais. A **v2** (`src/avaliar_v2.py`, gabarito em `tickets/tickets_v2.csv`) foi criada **depois** de ver os resultados da v1; por isso as duas são mantidas. A nota automática compara palavras e não percebe contradições, então a revisão manual é a referência.
- São 2 modelos pequenos, 30 tickets escritos pelo próprio autor e uma rodada. Não é um benchmark.

## Estrutura

```
kb/         12 artigos da base de conhecimento (Markdown)
tickets/    tickets.csv (gabarito v1) e tickets_v2.csv (gabarito v2)
src/        scripts em Python (só biblioteca padrão)
results/    saídas de cada rodada (CSV, resumos em Markdown) e a revisão manual
```

## Como repetir

1. Instale o [Ollama](https://docs.ollama.com/) e baixe os modelos:
   ```
   ollama pull llama3.2:3b
   ollama pull gemma3:4b
   ```
2. Teste só a busca (não usa IA):
   ```
   python3 src/avaliar.py --so-busca
   ```
3. Rode a avaliação completa (30 tickets, duas condições, 60 chamadas por modelo):
   ```
   python3 src/avaliar.py --modelo llama3.2:3b
   python3 src/avaliar.py --modelo gemma3:4b
   ```
4. Reavalie as respostas salvas com a régua v2 (não chama o Ollama):
   ```
   python3 src/avaliar_v2.py --rodada <carimbo da rodada, ex.: 20261110-192640>
   ```
5. Compare todos os modelos:
   ```
   python3 src/comparar_modelos.py
   ```

`src/teste_ollama.py` é um teste de fumaça: manda uma pergunta ao Ollama, com ou sem um artigo da base.

## Sobre as respostas salvas

As respostas em `results/` são as que os modelos escreveram, sem edição, com uma exceção: e-mails, sites, endereços e telefones que os modelos inventaram foram trocados por marcadores como `[e-mail inventado pelo modelo]`. Os arquivos `20261110-192555-*` são uma rodada de teste com apenas 3 tickets.

## Segurança

Nenhuma chave de API é usada: os modelos rodam no próprio computador. Não coloque senhas, tokens ou dados pessoais neste repositório.

## Avisos sobre os modelos

Este repositório **não distribui** os modelos: só traz o código de teste e as respostas que eles geraram. Os modelos têm licenças próprias:

- Llama 3.2 is licensed under the Llama 3.2 Community License, Copyright © Meta Platforms, Inc. All Rights Reserved. ([texto da licença](https://developer.meta.com/ai/llama3_2/license/))
- Gemma is provided under and subject to the Gemma Terms of Use found at ai.google.dev/gemma/terms.

Esta seção é um aviso de boa-fé, não uma análise jurídica.

## Licença

[MIT](LICENSE).
