# Quickstart: validação da Silver do case gastos

Roteiro para provar a feature de ponta a ponta. Esquemas em
[contracts/silver-tables.md](./contracts/silver-tables.md); parâmetros e orquestração em
[contracts/notebooks-e-orquestracao.md](./contracts/notebooks-e-orquestracao.md).

## 0. Pré-requisitos

- Bronze de dev com os arquivos de 2021 a 2026 republicados em 2026-11-16 (FR-019; feito em
  2026-11-17, 3,6 min).
- Nenhuma outra sessão Spark aberta na capacidade (research R9).

## 1. Detecção de mudança na Bronze (US4, FR-015)

1. Rodar `nb-incr-040-bronze-camara-despesas` com `origem=arquivo` e `anos` vazio.
   Esperado na primeira vez: 8 lotes `succeeded`, cada um com `source_hash` preenchido.
2. Rodar de novo, logo em seguida. Esperado: 8 lotes `skipped` com `arquivo sem mudança`, zero
   registros, sem nenhuma linha nova em `bronze_camara.despesas`.
3. Rodar com `anos=2026` e `forcar=true`. Esperado: 1 lote `succeeded`.

```sql
SELECT recorte, status, records_written, left(source_hash, 12) AS hash, message
FROM bronze_camara.ctl_ingestion_runs
WHERE recurso = 'despesas' ORDER BY started_at DESC LIMIT 20;
```

## 2. Despesas na Silver (US1, SC-001)

1. Rodar `nb-incr-030-silver-camara-despesas` com `anos` vazio.
2. Comparar por ano com o último lote de arquivo da Bronze:

```sql
WITH b AS (
  SELECT d._recorte, d._batch_id, d.payload FROM bronze_camara.despesas d
  JOIN (SELECT recorte, max_by(batch_id, started_at) AS batch_id FROM bronze_camara.ctl_ingestion_runs
        WHERE recurso = 'despesas' AND origem = 'arquivo' AND status = 'succeeded' GROUP BY recorte) u
    ON d._batch_id = u.batch_id)
SELECT CAST(get_json_object(payload, '$.numAno') AS INT) AS ano, COUNT(*) AS linhas_bronze,
       ROUND(SUM(CAST(get_json_object(payload, '$.vlrLiquido') AS DECIMAL(15,2))), 2) AS liquido_bronze
FROM b GROUP BY 1 ORDER BY 1;

SELECT ano, COUNT(*) AS linhas_silver, SUM(valor_liquido) AS liquido_silver
FROM silver_camara.despesas GROUP BY ano ORDER BY ano;
```

   Esperado: contagem e soma iguais em todos os anos; zero `chave_despesa` repetida; nenhuma
   coluna de CPF (`DESCRIBE silver_camara.despesas`).
3. Rodar de novo sem lote novo. Esperado: todos os anos pulados e a versão da tabela Delta
   inalterada (`DESCRIBE HISTORY`) (SC-004).
4. Simular republicação: rodar o passo 1.3 (`forcar=true` em 2026) e a Silver de novo. Esperado:
   só 2026 processado; se o arquivo do dia tiver linhas novas ou retiradas, a Silver acompanha.

## 3. Cadastros (US2)

Rodar `nb-full-020-silver-camara-cadastros`. Esperado: `legislaturas` 57, `partidos` 38,
`deputados` 929 (ou as contagens do último lote, se mudaram), um registro por código, sem coluna
de CPF.

## 4. Portal (US3, SC-002)

1. Rodar `nb-incr-020-silver-transparencia-emendas`. Esperado: por ano, a mesma quantidade do
   último lote da Bronze (2019: 8.456 … 2026: 5.936 em dev), zero `chave_emenda` repetida, valores
   numéricos (ex.: `1.200.000,00` → `1200000.00`).
2. Rodar `nb-incr-030-silver-transparencia-fornecedores`. Esperado: 68.057 CNPJs em dev, um por
   linha; `encontrado` = 33.967 e não encontrados = 34.090. Rodar de novo: nenhuma linha muda.

## 5. Qualidade (US5, SC-003)

1. Conferir `ctl_quality_checks` nos dois lakehouses: para cada tabela, `unicidade` e
   `obrigatorias` `passed` e uma `contagem` por execução.
2. Teste de falha em dev: rodar a Silver de emendas com um conjunto preparado que duplica uma
   linha (parâmetro de teste definido nas tarefas). Esperado: exceção, `unicidade` `failed` com
   chave de exemplo em `detalhe`, e a tabela `emendas` sem alteração.

## 6. Orquestrador em dev (US4)

Disparar `pl-010-orq-gastos-diario` à mão em dev, com `limite` pequeno nos fornecedores se
necessário. Esperado: as oito atividades na ordem do contrato, a Silver só depois da Bronze, e
uma falha provocada na Bronze do Portal impedindo a Silver do Portal.

## 7. Produção (SC-005, SC-006)

1. Depois do PR `dev` → `main` e do `deploy-prd` verde: conferir em produção os lakehouses Silver,
   os seis notebooks novos, o orquestrador com agenda às 04:00 e as agendas dos pipelines por
   fonte desativadas.
2. Carga inicial manual, fora do horário da rotina: Bronze de despesas com `anos` vazio (grava os
   hashes), depois os quatro notebooks da Silver. Conferir os §2 a §5 com os números de produção.
3. Na manhã seguinte: o orquestrador rodou por agenda, terminou antes das 07:00, só os anos de
   arquivo alterados foram gravados, e `ctl_quality_checks` tem as verificações da noite com
   `environment = 'prd'`.

## Registro da validação

### 2026-11-17: `ws-dev-dpacademy`

- **§1 Detecção de mudança**: primeira carga com `anos` vazio gravou os 8 anos com `source_hash`
  (3,9 min); a segunda terminou com os 8 lotes `skipped`, `arquivo sem mudança`, zero registros
  (2,4 min); `anos=2026`, `forcar=true` gravou 1 lote `succeeded` (1,4 min).
- **§2 Despesas**: primeira carga de 2019 a 2026 em 16,8 min (um `MERGE` por ano). Contagem e soma
  do valor líquido iguais às do último lote da Bronze em todos os anos (ex.: 2024 com 232.926
  linhas e R$ 250.384.236,66; total 1.686.374); uma `chave_despesa` por linha; nenhuma coluna de
  CPF. Reexecução sem lote novo: nenhum ano processado e nenhuma versão Delta nova (1,4 min). Com
  o lote forçado de 2026, só 2026 foi processado e a linhagem passou para o lote novo; 2025 não
  mudou.
- **§3 Cadastros**: 57 legislaturas, 38 partidos e 929 deputados, sem CPF (2,3 min); reexecução
  sem mudança.
- **§4 Portal**: emendas iguais à Bronze em todos os anos (55.044; 2019: 8.456 … 2026: 5.936), uma
  `chave_emenda` por linha (2,8 min). Fornecedores: a primeira execução falhou na verificação de
  obrigatórias porque 89 CNPJs encontrados vêm com razão social vazia na fonte (a regra
  "razão social obrigatória quando encontrado" foi retirada; research R5). Depois: 68.057 CNPJs,
  33.967 encontrados (89 sem nome) e 34.090 não encontrados; reexecução incremental sem mudança.
- **§5 Qualidade**: `emendas` com `anos=2026` e `duplicar_para_teste=true` falhou com
  `unicidade` `failed` (2 linhas, chave de exemplo em `detalhe`), e a tabela ficou na mesma versão
  Delta, com 55.044 linhas. Todas as outras verificações `passed`, com uma `contagem` por execução.
  Achado: com `anos` vazio e sem lote novo, o teste não exercita nada (nenhum ano entra no laço);
  é preciso informar o ano.
- **§6 Orquestrador**: `pl-010-orq-gastos-diario` disparado à mão, `Completed` em 46,9 min, na
  ordem do contrato (Bronze da Câmara 15:35–15:44, Bronze do Portal 15:44–16:03, Silver da Câmara
  16:03–16:18, Silver do Portal 16:18–16:21 UTC). Três atividades falharam na primeira tentativa,
  em ~20 s, com `TooManyRequestsForCapacity` (sessão da atividade anterior ainda não liberada) e
  passaram na retentativa de 5 min. Ajuste: duas retentativas com 180 s de intervalo. Sem as
  esperas, a rotina leva ~32 min com a fila de fornecedores vazia.

### 2026-11-17 e 2026-11-18: `ws-prd-dpacademy`

- **§7.1 Publicação**: `deploy-prd` verde em 2026-11-17 17:01 UTC. Lakehouses `silver_camara` e
  `silver_transparencia`, os seis notebooks e `pl-010-orq-gastos-diario` publicados; agenda do
  orquestrador às 04:00 (Brasília) ativa; agendas dos dois pipelines por fonte desativadas.
- **§7.2 Carga inicial manual** (2026-11-17, 29,5 min): Silver de despesas igual à Bronze nos oito
  anos; 57 legislaturas, 38 partidos e 929 deputados; 55.044 emendas; 15.000 CNPJs (a fila de
  fornecedores de produção começou do zero em 2026-11-17 e avança 15.000 por noite). Todas as
  verificações `passed`, com `environment = 'prd'`.
- **§7.3 Primeira execução agendada** (2026-11-18): `Completed`, 07:00–08:42 UTC (04:00–05:42 em
  Brasília, antes das 07:00). Bronze da Câmara: cadastros gravados, despesas de 2019 a 2025
  `skipped` (`arquivo sem mudança`) e só 2026 gravado (126.967 linhas). Bronze do Portal: emendas
  de 2025 e 2026 (12.259 registros) e mais 15.000 CNPJs (30 lotes, 69 min, a maior parte da
  rotina). Silver: despesas só de 2026 (total 1.687.037), emendas de 2025 e 2026 (total 55.057),
  `pessoa_juridica` com 30.000 CNPJs. `ctl_quality_checks` com 18 verificações da noite, todas
  `passed`, com `environment = 'prd'`. Quatro atividades (`camara_despesas` e três notebooks da
  Silver) falharam na primeira tentativa com `TooManyRequestsForCapacity` (HTTP 430) e passaram
  na retentativa de 180 s, como previsto no §6. Nenhuma execução dos pipelines por fonte.
