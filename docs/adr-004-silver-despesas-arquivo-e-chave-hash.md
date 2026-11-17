# ADR-004: despesas da Silver pelo arquivo anual, com chave pelo hash da linha

- **Status:** aceita
- **Data:** 2026-11-17
- **Feature:** [004-gastos-silver](../specs/004-gastos-silver/spec.md) (research R1, R2, R4 e R6)

## Contexto

A Câmara publica as despesas da cota parlamentar de dois jeitos: o arquivo anual (um CSV por ano,
regerado todo dia) e a API, consultada por deputado e mês. A Bronze guarda as duas origens
(feature 003). A Silver precisa de uma versão única de cada despesa, e a constituição pede
deduplicação por chave e carga por `MERGE` (Princípio I).

Uma comparação em produção, em 2026-11-17, mostrou que as origens não são equivalentes:

- nos documentos presentes nas duas origens, a API inverte o sinal do valor líquido (o arquivo
  soma +R$ 21,05 mi em 09 a 11/2026 e a API, −R$ 20,97 mi);
- 912 registros da API usam um identificador em formato GUID, sem correspondência no arquivo;
- as despesas de liderança só existem no arquivo.

Também não existe chave natural: o identificador do documento repete em 209.878 linhas
(`0` marca telefonia e serviços postais, e as passagens aéreas repetem o mesmo id por trecho), e
mesmo combinando 10 campos sobram linhas repetidas. Nenhuma linha, porém, é idêntica a outra.
As emendas do Portal têm o mesmo problema, com códigos genéricos como `S/I` e `REL. GERAL`.

Por fim, a Câmara regera os arquivos de todos os anos todos os dias, mesmo os de anos fechados,
então a data de modificação e o `etag` mudam diariamente.

## Decisão

1. A Silver de despesas usa só o arquivo anual. A coleta pela API sai da rotina diária e fica
   disponível por disparo manual.
2. A chave de despesas e emendas é o SHA-256 do registro publicado (`chave_despesa`,
   `chave_emenda`). Cada ano é tratado como uma foto completa do último lote: o `MERGE` insere as
   linhas novas, atualiza a linhagem das que continuam e apaga as que sumiram daquele ano.
3. A Bronze só grava um arquivo anual quando o SHA-256 do CSV descompactado muda em relação ao
   último lote bem-sucedido do ano (coluna `source_hash` em `ctl_ingestion_runs`). Sem mudança, o
   lote termina `skipped` com a mensagem `arquivo sem mudança`.

## Alternativas consideradas

- **API como origem oficial**: rejeitada pelo sinal invertido, pelos ids GUID e pela falta das
  lideranças.
- **Conciliar as duas origens**: rejeitada; não há chave comum para os GUIDs e a regra ficaria
  frágil.
- **Chave composta de campos**: rejeitada; sempre sobram repetições, e um campo novo na fonte
  quebraria a regra.
- **Detectar mudança por data, `etag` ou tamanho**: rejeitada; data e `etag` mudam todo dia, e uma
  correção de valor pode manter o tamanho.
- **Recarregar todos os anos todo dia**: rejeitada; acrescentaria 1,7 mi de linhas por noite a uma
  Bronze append-only.

## Consequências

- A Silver de despesas bate exatamente com o último arquivo de cada ano, em contagem e em valor
  (conferido em dev em 2026-11-17 para 2019 a 2026).
- Uma correção na fonte troca a linha antiga pela nova, com outra chave; a Gold não pode usar a
  `chave_despesa` como identificador estável ao longo do tempo, só dentro da versão atual.
- A Silver fica até um dia atrás da API, porque o arquivo é regerado de madrugada. A rotina diária
  roda às 04:00, depois da regeneração.
- A rotina noturna fica mais curta: sai a coleta da API (~20 min) e os anos sem mudança não são
  regravados.
