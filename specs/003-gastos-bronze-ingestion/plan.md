# Implementation Plan: Ingestão Bronze do case gastos (Câmara + Portal da Transparência)

**Branch**: `003-gastos-bronze-ingestion` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-gastos-bronze-ingestion/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Coletar para a Bronze os dados do case `gastos`:

- **Câmara** (sem chave): legislaturas, partidos, detalhe dos deputados das legislaturas 56 e 57 e
  despesas da cota parlamentar. O histórico de 2019 a 2026, cerca de 1,27 milhão de despesas, vem
  dos arquivos anuais (um download por ano). A carga diária usa a API, mês a mês, com janela de
  três meses.
- **Portal da Transparência** (chave gratuita): emendas parlamentares por ano e cadastro de pessoa
  jurídica dos ~68 mil CNPJs que aparecem nas despesas.

Cada fonte tem um cliente em Python puro (ritmo, retentativas, paginação), testado localmente, e
um notebook de gravação PySpark. A gravação é um append Delta atômico por lote, com o registro em
`ctl_ingestion_runs`. Toda tabela guarda o registro da fonte como JSON em `payload`, mais as
colunas de auditoria. Isso permite as duas origens da despesa (arquivo e API) na mesma tabela. A
chave do Portal fica num arquivo na área Files do lakehouse, fora do Git. Os dois pipelines diários
só têm agenda em produção.

## Technical Context

**Language/Version**: Python 3.11 (Fabric Runtime 1.3, PySpark 3.5)

**Primary Dependencies**: `requests`, `zipfile` e `csv` (já no runtime ou na biblioteca padrão),
`notebookutils` e Delta Lake (nativos do Fabric); localmente, `pytest`

**Storage**:
- Delta em `bronze_camara`: `legislaturas`, `partidos`, `deputados`, `despesas` e
  `ctl_ingestion_runs`.
- Delta em `bronze_transparencia`: `emendas`, `pessoa_juridica` e `ctl_ingestion_runs`.
- Arquivos anuais em `bronze_camara/Files/_landing/cotas/`.
- Chave em `bronze_transparencia/Files/_secrets/transparencia_api_key`.

**Testing**: `pytest` local para os dois clientes (APIs simuladas); roteiro no Fabric em
[quickstart.md](./quickstart.md)

**Target Platform**: Microsoft Fabric, workspace `ws-dev-dpacademy` (desenvolvimento) e
`ws-prd-dpacademy` (agendas), capacidade Trial

**Project Type**: pipeline de dados (itens do Fabric versionados pela Git integration)

**Performance Goals**:
- **Câmara completa** em menos de 2 h somadas (SC-003): ~11 min de cadastros e ~5 min por ano de
  arquivo.
- **Carga diária da Câmara**: ~877 deputados × 3 meses ≈ 2.600 chamadas, ou ~20 min.
- **Fornecedores**: ~68 mil chamadas, ou ~4 h 45 min de madrugada, em duas madrugadas antes de
  2026-11-30 (SC-004).

**Constraints**:
- Portal: ~90 req/min de dia, com limite maior de madrugada.
- Câmara: limite não documentado, então o cliente faz no máximo 4 req/s, uma por vez.
- Custo zero.
- A chave nunca vai para o Git nem para logs.
- Lote atômico (tudo ou nada).
- O Trial termina por volta de 2026-12-05.

**Scale/Scope**: ~1,27 mi de despesas, ~1.200 deputados, ~68 mil PJ e as emendas de 8 anos
(volume a medir no quickstart §5). A Bronze toda deve ficar abaixo de 1 GB em Delta.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio (v3.0.0) | Verificação | Resultado |
|---|---|---|
| I. Arquitetura Medalhão | Grava só na Bronze, em um lakehouse por fonte. `payload` sem transformação e com os nomes de campo da fonte. Colunas `_ingested_at`, `_source_endpoint` e `_batch_id`. Append-only. | ⚠️ Desvio justificado: a fila de fornecedores lê a `bronze_camara` (Complexity Tracking) |
| II. Ingestão Idempotente | Lotes por endpoint, janela (ano ou mês) e recorte. Paginação até o fim (link `next` ou lista vazia). Lote atômico. Retentativa com espera em 429 e 5xx. Ritmo dentro do limite de cada fonte. Mesmo código para histórico e carga diária. O histórico pelo arquivo anual grava na mesma tabela com as mesmas colunas de auditoria. Um recurso novo entra por configuração do notebook da fonte. | ✅ |
| III. Fabric Versionado no Git | Itens criados em `ws-dev-dpacademy` e sincronizados para `workspace/`. Agendas só em `ws-prd-dpacademy`. Em dev, tudo roda à mão. | ✅ |
| IV. Nomenclatura | `bronze_camara` e `bronze_transparencia`. Notebooks `nb-util-010/020`, `nb-full-030` e `nb-incr-030/040` por fonte. `pl-010-bronze-<fonte>-gastos`. Tabelas com o nome da entidade, sem prefixo, e `ctl_ingestion_runs`. | ✅ |
| V. Qualidade Verificável | Na Bronze: chave natural presente no `payload`, coletado igual ao gravado, comparação com `X-Total-Count` ou com o arquivo anual, e o registro de execuções. Unicidade, nulos e integridade começam na Silver. | ✅ (escopo da Bronze) |
| VI. Segredos Fora do Código | Chave do Portal em Files, fora do Git. Nunca é impressa nem gravada em `ctl_ingestion_runs`, e as mensagens são sanitizadas. A Câmara não usa chave. Verificação por `git grep` (quickstart §8) e no `pr-validation` (dependência da feature 002, abaixo). | ✅ com risco aceito (research R5) |
| VII. Custo Zero e Simplicidade | Fontes gratuitas e Trial. Sem Key Vault, sem `.whl` e sem bibliotecas novas. Cada fonte é autocontida, sem motor genérico prematuro. | ✅ |

**Gate pré-pesquisa**: aprovado com um desvio justificado. **Gate pós-design** (depois do data
model e dos contratos): aprovado, sem desvios novos.

**Dependências de outras features**:
- **Feature 002**:
  - o `ci/parameter.yml` e o `deploy-config` passam a referenciar `bronze_camara` e
    `bronze_transparencia` no lugar de `bronze_balldontlie`;
  - o `pr-validation` passa a procurar o valor da chave do Portal, guardado num secret do GitHub,
    no lugar da chave da balldontlie;
  - o validador de nomes (`ci/validate_names.py`, usado também pelo `ci/deploy.py`) ainda exige
    prefixo de liga (`LIGAS = {"nba"}`) e bloquearia `despesas` no deploy. Ajustá-lo à regra da
    constituição v3.0.0 é tarefa fundacional desta feature.
- **Agendas em produção**: entram em `ci/schedules.json` e precisam do fluxo de publicação da
  feature 002 ativo.
- **Pré-requisitos da 002 ainda abertos**: repositório no GitHub, branch `dev` e `ws-dev-dpacademy`
  conectado ao Git (tarefas T001, T002 e T005 da 002).

## Project Structure

### Documentation (this feature)

```text
specs/003-gastos-bronze-ingestion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── camara-api.md
│   ├── transparencia-api.md
│   ├── bronze-tables.md
│   └── notebook-parameters.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks (ainda não criado)
```

### Source Code (repository root)

```text
workspace/                                              # escrito pela Git integration (não editar à mão)
├── bronze_camara.Lakehouse/
├── bronze_transparencia.Lakehouse/
├── nb-util-010-bronze-camara-cliente.Notebook/         # Python puro: HTTP, ritmo, retry, paginação, arquivo anual
├── nb-util-020-bronze-camara-gravacao.Notebook/        # PySpark: append atômico, ctl_ingestion_runs, trava
├── nb-full-030-bronze-camara-cadastros.Notebook/
├── nb-incr-040-bronze-camara-despesas.Notebook/
├── nb-util-010-bronze-transparencia-cliente.Notebook/  # Python puro: HTTP com chave, ritmo por horário, retry, paginação
├── nb-util-020-bronze-transparencia-gravacao.Notebook/
├── nb-incr-030-bronze-transparencia-emendas.Notebook/
├── nb-incr-040-bronze-transparencia-fornecedores.Notebook/
├── pl-010-bronze-camara-gastos.DataPipeline/
└── pl-010-bronze-transparencia-gastos.DataPipeline/

tests/
└── unit/
    ├── conftest.py                                     # carrega o notebook-content.py dos clientes
    ├── test_camara_cliente.py
    └── test_transparencia_cliente.py

docs/
└── adr-003-segredo-api-em-lakehouse-files.md
```

**Structure Decision**: o código de produção são itens do Fabric, criados em `ws-dev-dpacademy`
(pela interface ou pelo MCP do Fabric) e trazidos ao repositório pela Git integration em
`workspace/`. Fora de `workspace/` ficam os testes locais, a ADR do segredo, o ajuste em
`ci/validate_names.py` (com o teste correspondente) e as entradas de `ci/parameter.yml` e
`ci/schedules.json`. O número 003 segue a ADR-002 existente.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| A ingestão do Portal (`nb-incr-040-bronze-transparencia-fornecedores`) lê CNPJs de `bronze_camara.despesas` para montar a fila, um cruzamento de fontes antes da Gold (Princípio I) | O Portal não tem cadastro de PJ em lote. Sem a lista de CNPJs das despesas, não há o que consultar. A leitura só decide o que coletar; nenhum dado da Câmara é gravado na Bronze do Portal | Passar a lista como parâmetro do pipeline: o cruzamento continua, só que fora do notebook, e 68 mil CNPJs não cabem num parâmetro. Ler da Silver: a `silver_camara` ainda não existe. A fila passa a ler da Silver quando ela existir (registrado em research R10) |
