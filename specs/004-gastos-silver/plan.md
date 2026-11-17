# Implementation Plan: Camada Silver do case gastos

**Branch**: `004-gastos-silver` | **Date**: 2026-11-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-gastos-silver/spec.md`

## Summary

Criar `silver_camara` e `silver_transparencia` com seis tabelas tipadas, em português e
deduplicadas, carregadas por `MERGE` incremental a partir dos lotes `succeeded` da Bronze, com
verificações de unicidade, obrigatórias e contagem em `ctl_quality_checks`. As despesas vêm só do
arquivo anual (R1), com chave SHA-256 da linha e cada ano tratado como foto completa (R4, R6). Na
Bronze, as despesas passam a recarregar só os arquivos cujo conteúdo mudou, pelo hash do CSV
(R2). Um orquestrador único, `pl-010-orq-gastos-diario`, roda às 04:00 a Bronze da Câmara, a do
Portal e a Silver das duas fontes, em sequência (R3, R7).

## Technical Context

**Language/Version**: PySpark no runtime do Fabric (Spark 3.5, Delta 3.2); Python 3.11 nos
scripts de CI e testes.

**Primary Dependencies**: notebooks do Fabric com `%run` das bibliotecas `comum`; Data Pipeline do
Fabric; `fabric-cicd` 1.4.0 na publicação (sem mudança).

**Storage**: Delta nos lakehouses `silver_camara` e `silver_transparencia`; leitura de
`bronze_camara` e `bronze_transparencia` pelo nome qualificado.

**Testing**: `pytest tests/unit` para o Python puro novo do `nb-util-010-bronze-camara-cliente`
(hash do CSV e escolha dos anos a gravar), carregado como módulo pelo `conftest.py` da 003; as
conversões e o `MERGE`, que são Spark, são validados pelos dados no `quickstart.md`.

**Target Platform**: Microsoft Fabric, capacidade Trial, `ws-dev-dpacademy` e `ws-prd-dpacademy`.

**Project Type**: pipeline de dados (notebooks, pipelines e CI no repositório `dpacademy`).

**Performance Goals**: Silver das duas fontes em menos de 20 min por noite; rotina inteira antes
das 07:00 (SC-005).

**Constraints**: uma sessão Spark por vez (R9); custo zero; Trial até ~2026-12-04; Silver em
produção até 2026-11-24 (SC-006).

**Scale/Scope**: ~1,7 mi de despesas (2019–2026), 55 mil emendas, 68 mil fornecedores, cerca de
1.000 linhas de cadastros.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Como o plano atende | Situação |
|---|---|---|
| I. Medalhão | Silver por fonte, uma tabela por entidade, tipada, `snake_case` em português, dedup por chave, `MERGE`; sem `dim_`/`fat_`; cruzamento entre fontes fica para a Gold | ✅ |
| II. Idempotente | Reexecução sem lote novo não muda nada (R6); Bronze só grava arquivo com conteúdo novo e continua append-only | ✅ |
| III. Git | Itens criados no ws-dev e versionados pela Git integration; publicação por PR e `fabric-cicd`; agenda só em prd via `ci/schedules.json` | ✅ |
| IV. Nomes | Lakehouses `silver_<fonte>`, notebooks `nb-<mode>-<999>-silver-<fonte>-<assunto>` (assunto de um termo), pipeline `pl-010-orq-gastos-diario`, tabelas com o nome da entidade e `ctl_quality_checks` | ✅ |
| V. Qualidade | Unicidade, obrigatórias e contagem por execução em toda tabela Silver; falha interrompe antes do `MERGE` e antes da camada seguinte | ✅ |
| VI. Segredos | A Silver não usa chave; o Portal continua lendo a chave de `Files/_secrets` só na Bronze | ✅ |
| VII. Custo zero | Só Trial; a mudança na Bronze reduz o uso noturno (sem 20 min de API e sem regravar arquivos iguais) | ✅ |

Chave da despesa e da emenda: a constituição pede "deduplicação por chave natural". Como a fonte
não oferece chave natural única (R4), a chave é o hash da linha publicada, que identifica cada
linha da mesma forma que uma chave natural faria. Registrado aqui como interpretação, não como
desvio: a dedup continua acontecendo por chave, com a verificação de unicidade do Princípio V.

**Re-check pós-design**: os contratos mantêm todos os itens acima; nenhuma violação. Complexity
Tracking vazio.

## Project Structure

### Documentation (this feature)

```text
specs/004-gastos-silver/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── silver-tables.md
│   └── notebooks-e-orquestracao.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
workspace/                                   # Git integration do ws-dev (branch dev)
├── silver_camara.Lakehouse/
├── silver_transparencia.Lakehouse/
├── nb-util-010-silver-camara-comum.Notebook/
├── nb-full-020-silver-camara-cadastros.Notebook/
├── nb-incr-030-silver-camara-despesas.Notebook/
├── nb-util-010-silver-transparencia-comum.Notebook/
├── nb-incr-020-silver-transparencia-emendas.Notebook/
├── nb-incr-030-silver-transparencia-fornecedores.Notebook/
├── pl-010-orq-gastos-diario.DataPipeline/
├── nb-incr-040-bronze-camara-despesas.Notebook/      # muda: hash e anos vazio
├── nb-util-020-bronze-camara-gravacao.Notebook/      # muda: source_hash
└── pl-010-bronze-camara-gastos.DataPipeline/         # muda: origem=arquivo
ci/
├── parameter.yml        # + GUIDs de dev dos dois lakehouses Silver
└── schedules.json       # só pl-010-orq-gastos-diario às 04:00
tests/unit/
└── test_camara_cliente.py   # + hash do CSV e anos a gravar
backlog/backlog.csv      # épicos do case gastos
docs/                    # ADR-004 (origem das despesas e chave por hash); ADR-002 com dev-protegida
```

**Structure Decision**: mesma organização da 003. Os itens do Fabric nascem no ws-dev e chegam a
`workspace/` pelo commit da Git integration em `dev`; `ci/`, `tests/`, `docs/`, `backlog/` e
`specs/` são editados na branch `004-gastos-silver`, que recebe `dev` antes do PR para `dev` e
depois `dev` → `main`.

## Ordem de entrega

1. Bronze: `source_hash`, detecção de mudança e quickstart §1 (desbloqueia a rotina nova).
2. Lakehouses Silver e bibliotecas `comum`.
3. Despesas (US1) → cadastros (US2) → emendas e fornecedores (US3), cada uma validada pelo
   quickstart antes da seguinte.
4. Teste de falha de qualidade (US5).
5. Orquestrador, `ci/schedules.json`, `ci/parameter.yml` e teste em dev (US4).
6. Docs, backlog, PR para `dev`, PR `dev` → `main`, carga inicial em prd e conferência da primeira
   noite (até 2026-11-24).

## Complexity Tracking

Sem violações.
