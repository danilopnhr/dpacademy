# Quickstart: validar a ingestão Bronze do case gastos

Roteiro para provar que a feature funciona de ponta a ponta em `ws-dev-dpacademy`. Os nomes e
parâmetros estão em [contracts/notebook-parameters.md](./contracts/notebook-parameters.md); as
tabelas em [contracts/bronze-tables.md](./contracts/bronze-tables.md).

## 0. Pré-requisitos

- Workspace `ws-dev-dpacademy` na capacidade Trial, conectado à branch `dev` (feature 002).
- Lakehouses `bronze_camara` e `bronze_transparencia` criados.
- Chave do Portal da Transparência cadastrada em https://portaldatransparencia.gov.br/api-de-dados
  (conta gov.br), gravada **à mão** em `bronze_transparencia/Files/_secrets/transparencia_api_key`
  (só o valor, sem quebra de linha). Necessária a partir do §5.
- Localmente: Python 3.11 e `pytest`.

## 1. Testes unitários dos clientes (local, sem rede)

```powershell
pytest tests/unit -q
```

Esperado: todos verdes, cobrindo paginação (link `next` da Câmara; lista vazia do Portal),
retentativa em 429/5xx com `Retry-After`, falha imediata em 401/403 sem a chave na mensagem,
ritmo por faixa de horário do Portal, conversão de linha CSV em JSON e "não encontrado" de PJ.

## 2. Cadastros da Câmara (US1)

Rodar `nb-full-030-bronze-camara-cadastros` com os padrões.

```sql
SELECT recurso, status, records_collected, records_written, expected_total
FROM bronze_camara.ctl_ingestion_runs ORDER BY started_at DESC LIMIT 3;
```

Esperado: 3 lotes `succeeded`; `deputados` com ~1.200 registros e `records_written =
records_collected`; tempo total < 20 min.

## 3. Histórico de despesas pelo arquivo (US1, SC-001, SC-003)

1. Rodar `nb-incr-040-bronze-camara-despesas` com `origem=arquivo`, `anos=2024`.
2. Conferir contra a tabela de [research.md R2](./research.md#r2-volume-da-câmara-medido-nos-arquivos-anuais-em-2026-11-12):

```sql
SELECT get_json_object(payload,'$.numAno') AS ano, COUNT(*) AS despesas,
       ROUND(SUM(CAST(REPLACE(get_json_object(payload,'$.vlrLiquido'),',','.') AS DOUBLE)),2) AS liquido
FROM bronze_camara.despesas WHERE _origem='arquivo'
GROUP BY 1;
```

   Esperado: 173.961 despesas e ~211,4 mi em 2024 (o arquivo do ano corrente cresce a cada dia).
3. Rodar de novo o mesmo ano: novo lote `succeeded`, o lote anterior continua na tabela com
   outro `_batch_id` (cenário 2 da US1).
4. Rodar `anos=2019,2020,2021,2022,2023,2025,2026`. Esperado: 7 lotes, total da Câmara
   (cadastros + 8 anos) em menos de 2 h somadas.

## 4. Despesas recorrentes pela API (US2)

Rodar `nb-incr-040-bronze-camara-despesas` com os padrões (`origem=api`).

Esperado: 3 lotes (mês corrente e dois anteriores) `succeeded`; para cada um,
`records_collected` = soma dos `X-Total-Count` (`expected_total`). Repetir com
`meses=<mês passado>` para simular recuperação de um mês perdido.

## 5. Portal: confirmações com a chave e emendas (US3, SC-002)

1. Chamada avulsa (num notebook de rascunho, sem imprimir a chave) para confirmar:
   - tamanho da página de `/emendas?ano=2024&pagina=1`;
   - resposta de `/pessoa-juridica?cnpj=00000000000000` (CNPJ inexistente);
   - que 0,7 s de dia não gera 429 em 200 chamadas seguidas.
   Registrar os achados em [contracts/transparencia-api.md](./contracts/transparencia-api.md).
2. Rodar `nb-incr-030-bronze-transparencia-emendas` com `anos=2024`. Esperado: lote
   `succeeded`, `records_written = records_collected`.
3. Renomear temporariamente o arquivo da chave e rodar de novo. Esperado: lote `failed` em
   segundos, `message` = "chave da API ausente ou inválida", zero registros. Restaurar o arquivo.

## 6. Fornecedores (US4, SC-004)

1. Rodar `nb-incr-040-bronze-transparencia-fornecedores` com `limite=1000`.
2. Conferir que a fila diminuiu 1.000 e que existem 2 lotes de 500:

```sql
SELECT _resultado, COUNT(*) FROM bronze_transparencia.pessoa_juridica GROUP BY 1;
```

3. Rodar de novo com `limite=1000`: nenhum CNPJ repetido (cenário 3 da US4).
4. Carga completa (~68 mil): rodar de madrugada, com os padrões, em produção ou em dev
   manualmente; acompanhar até a fila zerar antes de 2026-11-30.

## 7. Registro de execuções e concorrência (US5)

- Disparar duas vezes seguidas `nb-full-030-bronze-camara-cadastros`: a segunda termina com os
  lotes `skipped`.
- Conferir que toda execução dos passos anteriores aparece em `ctl_ingestion_runs` com status
  correto (SC-007).

## 8. Segredo fora do código (SC-008)

```powershell
git grep -n -F "<valor da chave>" $(git rev-list --all)
```

Esperado: nenhum resultado. Conferir também a saída das células dos notebooks executados e a
coluna `message` de `ctl_ingestion_runs`.

## Registro da validação

### 2026-11-13: US1 (cadastros e histórico de despesas), `ws-dev-dpacademy`

- **Cadastros** (§2): `legislaturas` 57, `partidos` 38 distintos (62 registros somando as
  legislaturas 56 e 57) e `deputados` 929; 949 requisições, nenhuma retentativa; 5,7 min.
- **Despesas pelo arquivo** (§3): os 8 anos conferem exatamente com o arquivo do dia, em contagem e
  em valor líquido. 2019: 289.832; 2020: 167.144; 2021: 155.274; 2022: 148.193; 2023: 173.515;
  2024: 173.961 (R$ 211.437.069,03); 2025: 170.589; 2026: 123.968. São 1.402.476 despesas e
  68.043 CNPJs distintos. Cada ano leva de 12 a 25 s quando a fonte responde; cadastros e
  histórico somam menos de 10 min de execução útil (SC-003).
- **Recarga** (cenário 2 da US1): 2024 carregado duas vezes, com dois `_batch_id`, e a versão
  anterior preservada.
- **Instabilidade da fonte**: `www.camara.leg.br` ficou inacessível a partir do Fabric por cerca
  de 75 min (2026-11-13, das 00:54 às 02:11 UTC). Os lotes de 2019 e 2020 terminaram `failed` após
  6 tentativas, sem dados parciais, e foram recarregados depois só com `anos=2019,2020` (FR-008).
  Na operação diária, rodar de novo um lote `failed` antes de tratá-lo como perda.
- **Republicação**: a Câmara republicou os arquivos de 2019 e 2020 entre 12 e 13/11 (research R2).

