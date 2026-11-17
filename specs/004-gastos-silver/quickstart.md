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

(preenchido durante a implementação)
