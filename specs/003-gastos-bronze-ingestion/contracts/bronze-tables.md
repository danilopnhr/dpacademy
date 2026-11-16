# Contrato: tabelas da Bronze do case gastos

Consumidor: a feature de Silver de cada fonte. Mudar uma coluna aqui é mudança de contrato.

## Colunas comuns às tabelas de dados

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `payload` | STRING | registro da fonte em JSON, nomes de campo como a fonte devolve; linhas de CSV viram JSON com os nomes do cabeçalho e valores texto |
| `_ingested_at` | TIMESTAMP | momento da gravação do lote (UTC), igual para todo o lote |
| `_source_endpoint` | STRING | endpoint sem a base e sem a chave (`/deputados/204379/despesas`) ou a URL do arquivo anual |
| `_batch_id` | STRING | UUID do lote; igual ao `batch_id` em `ctl_ingestion_runs` |
| `_origem` | STRING | `api` ou `arquivo` |
| `_recorte` | STRING | JSON com os parâmetros do lote, ex.: `{"ano":2026,"mes":10,"deputado":204379}` |

Tabelas Delta, append-only, sem particionamento (o maior volume, ~1,3 mi de linhas, não
justifica).

## `bronze_camara`

| Tabela | Colunas extras | Origem |
|---|---|---|
| `legislaturas` | — | API |
| `partidos` | — | API |
| `deputados` | — | API (detalhe por id) |
| `despesas` | — | API (`_origem = api`) ou arquivo anual (`_origem = arquivo`) |
| `ctl_ingestion_runs` | ver abaixo | controle |

## `bronze_transparencia`

| Tabela | Colunas extras | Origem |
|---|---|---|
| `emendas` | — | API |
| `pessoa_juridica` | `_cnpj` STRING (14 dígitos consultados), `_resultado` STRING (`encontrado` ou `nao_encontrado`) | API; `payload` nulo quando `nao_encontrado` |
| `ctl_ingestion_runs` | ver abaixo | controle |

`_cnpj` existe porque o CNPJ não encontrado não tem `payload` de onde tirá-lo, e a fila
(research R10) precisa excluí-lo.

## `ctl_ingestion_runs` (mesmo esquema nos dois lakehouses)

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `run_id` | STRING | UUID da execução do notebook (vários lotes por execução) |
| `batch_id` | STRING | UUID do lote; chave da tabela |
| `fonte` | STRING | `camara` ou `transparencia` |
| `recurso` | STRING | `legislaturas`, `partidos`, `deputados`, `despesas`, `emendas`, `pessoa_juridica` |
| `origem` | STRING | `api` ou `arquivo` |
| `recorte` | STRING | JSON com os parâmetros do lote |
| `status` | STRING | `running`, `succeeded`, `failed`, `skipped` |
| `started_at` | TIMESTAMP | início do lote (UTC) |
| `ended_at` | TIMESTAMP | fim do lote (UTC); nulo enquanto `running` |
| `records_collected` | BIGINT | registros recebidos da fonte |
| `records_written` | BIGINT | registros gravados (0 quando `failed`) |
| `requests_made` | INT | requisições HTTP feitas, incluindo retentativas |
| `retries` | INT | retentativas |
| `expected_total` | BIGINT | total informado pela fonte (`X-Total-Count` ou linhas do arquivo), nulo se a fonte não informa |
| `message` | STRING | motivo da falha ou aviso, sanitizado, até 1.000 caracteres; nunca contém a chave |
| `environment` | STRING | `dev` ou `prd`, extraído do nome do workspace `ws-<ambiente>-dpacademy` em tempo de execução (research R9 da feature 002) |

Gravação: `INSERT` com `running` antes da primeira requisição; `MERGE` por `batch_id` no fim.
