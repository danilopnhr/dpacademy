# Implementation Plan: Camada Gold e modelo semântico do case gastos

**Branch**: `005-gastos-gold` | **Date**: 2026-11-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-gastos-gold/spec.md`

## Summary

Criar o lakehouse `gold_gastos` com um star schema de dez dimensões e dois fatos
(`fat_despesas`, uma linha por despesa da cota; `fat_emendas`, uma linha por emenda × tipo ×
localidade), reconstruído a cada noite por um único notebook que monta tudo, verifica unicidade,
obrigatórias, integridade, conciliação com a Silver e privacidade, e só então grava (R1, R7). Chaves
substitutas determinísticas por hash da chave natural (R2). Deputado conformado entre os dois fatos,
com partido e UF da linha da despesa (R4); fornecedores com o perfil do Portal e CPF mascarado
(R5); autor da emenda ligado ao deputado por nome normalizado (R6). O orquestrador ganha a etapa da
Gold depois da Silver das duas fontes (R8). Por cima, o modelo semântico `sm-gastos` em Direct Lake
sobre o SQL endpoint, criado em TMDL pela API e reapontado para produção pelo `fabric-cicd` (R9).

## Technical Context

**Language/Version**: PySpark no runtime do Fabric (Spark 3.5, Delta 3.2); TMDL e DAX no modelo
semântico; Python 3.11 nos scripts de CI e testes.

**Primary Dependencies**: notebooks do Fabric com `%run` da biblioteca `comum`; Data Pipeline do
Fabric; `fabric-cicd` 1.4.0 na publicação (sem mudança de versão; atributos `$sqlendpoint` e
`$sqlendpointid` conferidos no pacote).

**Storage**: Delta no `gold_gastos` (V-Order ligado por tabela); leitura de `silver_camara` e
`silver_transparencia` pelo nome qualificado; modelo semântico Direct Lake.

**Testing**: `pytest tests/unit` para as funções puras do `nb-util-010-gold-gastos-comum` (nome,
CPF, CNPJ, grupo da emenda, localidade, UFs) e para a regra nova do validador de nomes; dados e
modelo validados pelo [quickstart.md](./quickstart.md) (T-SQL e DAX pela API).

**Target Platform**: Microsoft Fabric, capacidade Trial, `ws-dev-dpacademy` e `ws-prd-dpacademy`.

**Project Type**: pipeline de dados e modelo semântico (notebooks, pipeline, TMDL e CI no repositório
`dpacademy`).

**Performance Goals**: Gold em até 10 min por noite; rotina inteira antes das 07:00 (SC-005);
consultas do modelo em Direct Lake sem fallback no volume atual.

**Constraints**: uma sessão Spark por vez; custo zero; Trial até ~2026-12-04; Gold em prd até
2026-11-26 (SC-006) e modelo até 2026-11-30 (SC-010); CPF completo fora da Gold (FR-009).

**Scale/Scope**: 1,69 mi de despesas, 55 mil emendas, ~70 mil fornecedores, ~1.300 deputados e
lideranças, 2.900 datas; 12 tabelas no modelo e 12 medidas.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Como o plano atende | Situação |
|---|---|---|
| I. Medalhão | Gold por case (`gold_gastos`), único lugar onde Câmara e Portal se cruzam; star schema com `dim_`/`fat_` e grão documentado em cada fato; o modelo semântico lê só a Gold | ✅ |
| II. Idempotente | Reconstrução determinística: a mesma Silver gera as mesmas tabelas e os mesmos `sk` (R1, R2) | ✅ |
| III. Git | Lakehouse, notebooks, pipeline e modelo criados no ws-dev e versionados pela Git integration; publicação por PR e `fabric-cicd`, com reapontamento do modelo por `parameter.yml` sem GUID de prd; agenda única em prd | ✅ |
| IV. Nomes | `gold_gastos`, `nb-util-010-gold-gastos-comum`, `nb-full-020-gold-gastos-modelo`, `sm-gastos`; tabelas `dim_`/`fat_`; colunas `sk_<entidade>` e `codigo_<entidade>`; `ctl_quality_checks` como tabela de controle, com o validador ajustado para aceitá-la na Gold (R7) | ✅ |
| V. Qualidade | Unicidade, obrigatórias, integridade referencial fato → dimensão, conciliação com a Silver e contagem por execução; falha impede a gravação e a camada seguinte (o modelo continua lendo a versão anterior) | ✅ |
| VI. Segredos | A Gold e o modelo não usam credenciais; o modelo usa SSO; o deploy continua com os secrets do Environment do GitHub | ✅ |
| VII. Custo zero | Só Trial; um notebook por noite; reconstrução total em vez de lógica incremental, mais simples no volume atual | ✅ |

Exceção registrada (não desvio): `dim_data` sem membro "não informado" (R3), porque as datas dos
fatos são obrigatórias e a tabela de datas do modelo exige datas contínuas e não nulas. A
integridade do calendário continua verificada.

**Re-check pós-design**: os contratos mantêm todos os itens acima; nenhuma violação. Complexity
Tracking vazio.

## Project Structure

### Documentation (this feature)

```text
specs/005-gastos-gold/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── gold-tables.md
│   ├── notebooks-e-orquestracao.md
│   └── sm-gastos.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
workspace/                                   # Git integration do ws-dev (branch dev)
├── gold_gastos.Lakehouse/
├── nb-util-010-gold-gastos-comum.Notebook/
├── nb-full-020-gold-gastos-modelo.Notebook/
├── sm-gastos.SemanticModel/                 # TMDL: model, expressions, tables/, relationships
└── pl-010-orq-gastos-diario.DataPipeline/   # muda: atividades gold_gastos e falha_gold_gastos
ci/
├── parameter.yml        # + gold_gastos (lakehouse padrão) e servidor/SQL endpoint do sm-gastos
└── validate_names.py    # ctl_ aceito em lakehouses gold_
tests/unit/
├── test_gold_comum.py   # funções puras da Gold
└── test_validate_names.py   # + ctl_ na Gold
docs/                    # ADR-005: Gold reconstruída, chaves por hash, CPF mascarado, Direct Lake sobre SQL endpoint
README.md                # camada Gold e consumo atualizados
```

**Structure Decision**: mesma organização da 003 e da 004. Os itens do Fabric nascem no ws-dev (o
modelo pela API com TMDL de rascunho) e chegam a `workspace/` pelo commit da Git integration em
`dev`; `ci/`, `tests/`, `docs/` e `specs/` são editados na branch `005-gastos-gold`, que recebe
`dev` antes do PR para `dev` e depois `dev` → `main`.

## Ordem de entrega

1. `gold_gastos` em dev, biblioteca `comum` com testes e ajuste do validador.
2. Dimensões de deputado, partido, UF, tipo de despesa, fornecedor e calendário, e `fat_despesas`
   (US1, US2), validados pelo quickstart §1 e §2.
3. Dimensões de emenda e `fat_emendas` (US3), quickstart §3.
4. Verificações completas e teste de falha (US5), quickstart §4.
5. Orquestrador e `parameter.yml` (US4), quickstart §5. Marco: Gold validada em dev até 2026-11-22.
6. `sm-gastos` em dev (US6), quickstart §6.
7. ADR-005, README, PR para `dev`, PR `dev` → `main`, carga inicial e refresh em prd, conferência da
   primeira noite (Gold até 2026-11-26, modelo até 2026-11-30).

## Complexity Tracking

Sem violações.
