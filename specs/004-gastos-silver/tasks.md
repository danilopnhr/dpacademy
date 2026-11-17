---

description: "Lista de tarefas da feature 004: camada Silver do case gastos"
---

# Tasks: Camada Silver do case gastos (Câmara + Portal da Transparência)

**Input**: Design documents from `/specs/004-gastos-silver/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: `pytest` só para o Python puro novo do cliente da Câmara (hash do CSV e anos a gravar),
como define o plano. Os notebooks com Spark são validados pelo quickstart no Fabric.

**Organization**: tarefas agrupadas por história de usuário (US1 a US5 da spec).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa incompleta)
- **[Story]**: história de usuário da tarefa (US1 a US5)

## Path Conventions

- Itens do Fabric são criados ou alterados no `ws-dev-dpacademy` a partir de rascunhos locais
  (`Publish-FabNotebook`, com `DPACADEMY_NOTEBOOKS_DIR` para os testes) e chegam ao repositório
  pelo **commit da Git integration** em `dev`, em `workspace/<nome>.<Tipo>/`. A pasta
  `workspace/` MUST NOT ser editada à mão (Princípio III).
- Arquivos fora de `workspace/` (`specs/`, `tests/`, `ci/`, `docs/`, `backlog/`) são editados na
  branch `004-gastos-silver`, que recebe `dev` antes do PR.
- Notebooks da Silver fazem `%run` da biblioteca `comum` da própria fonte; o lakehouse padrão é o
  Silver da fonte; a Bronze é lida pelo nome qualificado.
- Uma sessão Spark por vez na capacidade (research R9): nunca rodar notebook e sessão de
  diagnóstico ao mesmo tempo.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: lakehouses e configuração de publicação

- [X] T001 Criar a branch `004-gastos-silver` a partir de `dev` e recarregar a Bronze de dev com `nb-incr-040-bronze-camara-despesas` `origem=arquivo`, `anos=2021,...,2026` (FR-019; feito em 2026-11-17, 3,6 min)
- [ ] T002 Criar os lakehouses `silver_camara` e `silver_transparencia` em `ws-dev-dpacademy` e fazer commit pela Git integration em `dev` (resulta em `workspace/silver_camara.Lakehouse/` e `workspace/silver_transparencia.Lakehouse/`); anotar os GUIDs de dev
- [ ] T003 Acrescentar a `ci/parameter.yml` as entradas `find_value` dos GUIDs de dev de `silver_camara` e `silver_transparencia` com `replace_value.prd` = `$items.Lakehouse.silver_camara.$id` e `$items.Lakehouse.silver_transparencia.$id` (research R8)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: bibliotecas comuns da Silver, usadas por todas as histórias

- [ ] T004 Criar `nb-util-010-silver-camara-comum` conforme `contracts/notebooks-e-orquestracao.md`: `ambiente()`; `lotes_validos(recurso, origem=None)` lendo `bronze_camara.ctl_ingestion_runs` com `status = 'succeeded'`; `vazio_nulo`, `valor_ponto` e `valor_br` → `DECIMAL(15,2)` (conversão que falha vira nulo), `data` → `DATE`; `garantir_ctl()` criando `ctl_quality_checks` com as colunas do contrato (`run_id`, `checked_at`, `tabela`, `verificacao`, `status`, `linhas_com_problema`, `linhas_tabela`, `detalhe`, `environment`); `verificar(df, tabela, chave, obrigatorias, run_id, detalhe)` gravando `unicidade` e `obrigatorias` (passa com 0 linhas com problema; `detalhe` com até 5 chaves de exemplo quando falha); `mesclar_particao(df, tabela, chave, condicao_particao)` com `MERGE` que insere, atualiza a linhagem e apaga `WHEN NOT MATCHED BY SOURCE` só dentro da partição (`None` = tabela toda), criando a tabela na primeira execução; `registrar_contagem`; `encerrar(run_id, resultados)` com `notebookutils.notebook.exit` em JSON e exceção se alguma verificação falhou; commit pela Git integration
- [ ] T005 [P] Criar `nb-util-010-silver-transparencia-comum` com o mesmo contrato do T004, lendo `bronze_transparencia.ctl_ingestion_runs`; commit pela Git integration

**Checkpoint**: bibliotecas prontas; as histórias podem começar.

---

## Phase 3: User Story 1 - Despesas da cota parlamentar confiáveis (Priority: P1) 🎯 MVP

**Goal**: `silver_camara.despesas` com uma linha por despesa do último arquivo de cada ano.

**Independent Test**: quickstart §2: contagem e soma do valor líquido por ano iguais às do último
lote de arquivo da Bronze; zero chave repetida; sem CPF.

- [ ] T006 [US1] Criar `nb-incr-030-silver-camara-despesas` (parâmetro `anos`; vazio = anos cujo último lote `succeeded` de `origem = 'arquivo'` difere do `_batch_id` na Silver; lista = só esses anos, sempre reprocessados) conforme `contracts/silver-tables.md`: só `_origem = 'arquivo'` (FR-004); `chave_despesa` = SHA-256 hex do `payload`; colunas e tipos do contrato; `documento_fornecedor` só dígitos e `tipo_documento_fornecedor` `CNPJ` (14 dígitos), `CPF` (11) ou nulo; `cpf` e `nuCarteiraParlamentar` não lidos (FR-008); obrigatórias `chave_despesa`, `ano`, `mes`, `nome_parlamentar`, `tipo_despesa`, `valor_documento`, `valor_liquido`; por ano: `verificar` → `mesclar_particao` com partição `ano = <ano>` → `registrar_contagem`; commit pela Git integration
- [ ] T007 [US1] Rodar `nb-incr-030-silver-camara-despesas` em dev e executar quickstart §2 (passos 1 a 3); registrar em `specs/004-gastos-silver/quickstart.md` § Registro da validação

**Checkpoint**: despesas na Silver conferidas contra a Bronze (MVP).

---

## Phase 4: User Story 2 - Cadastros da Câmara (Priority: P2)

**Goal**: `legislaturas`, `partidos` e `deputados` na versão mais recente, sem CPF.

**Independent Test**: quickstart §3: 57, 38 e 929 linhas em dev, um registro por código, sem CPF.

- [ ] T008 [US2] Criar `nb-full-020-silver-camara-cadastros` (parâmetro `recursos`, padrão `legislaturas,partidos,deputados`) conforme `contracts/silver-tables.md`: por recurso, o último lote `succeeded`; se o `_batch_id` da Silver já é esse, pula; `deputados` lê `ultimoStatus.*` e não lê `cpf`; obrigatórias do `data-model.md`; `verificar` → `mesclar_particao` na tabela toda → `registrar_contagem`; commit pela Git integration
- [ ] T009 [US2] Rodar em dev e executar quickstart §3; registrar no quickstart

---

## Phase 5: User Story 3 - Emendas e fornecedores do Portal (Priority: P3)

**Goal**: `emendas` pela última versão de cada ano e `pessoa_juridica` pela última de cada CNPJ.

**Independent Test**: quickstart §4: emendas por ano iguais à Bronze; 68.057 CNPJs em dev
(33.967 encontrados).

- [ ] T010 [P] [US3] Criar `nb-incr-020-silver-transparencia-emendas` (parâmetro `anos`, mesma regra do T006) conforme `contracts/silver-tables.md`: `chave_emenda` = SHA-256 hex do `payload`; valores `1.200.000,00` → `DECIMAL(15,2)` por `valor_br`; obrigatórias `chave_emenda`, `ano`, `tipo_emenda`, `autor`, `valor_empenhado`, `valor_liquidado`, `valor_pago`; partição `ano = <ano>`; commit pela Git integration
- [ ] T011 [P] [US3] Criar `nb-incr-030-silver-transparencia-fornecedores` (parâmetro `completo`, padrão `false`) conforme `contracts/silver-tables.md`: linhas da Bronze com `_ingested_at` maior que o máximo da Silver (todas se `completo=true` ou tabela vazia), a mais recente por `_cnpj`; `encontrado` = `_resultado = 'encontrado'`; booleanos do payload; obrigatórias `cnpj`, `encontrado` e `razao_social` quando `encontrado`; `MERGE` por `cnpj` sem remoção; commit pela Git integration
- [ ] T012 [US3] Rodar os dois notebooks em dev e executar quickstart §4; registrar no quickstart

---

## Phase 6: User Story 4 - Atualização diária encadeada (Priority: P4)

**Goal**: Bronze de despesas só com arquivos alterados, sem API na rotina; orquestrador único às
04:00 em produção.

**Independent Test**: quickstart §1 (detecção de mudança) e §6 (orquestrador em dev).

### Tests for User Story 4

- [ ] T013 [P] [US4] Em `tests/unit/test_camara_cliente.py`, testes de `hash_csv(caminho)` (mesmo conteúdo → mesmo hash; um byte diferente → hash diferente; arquivo maior que o bloco de leitura) e `anos_padrao(hoje)` (2019 até o ano de `hoje` no fuso `America/Sao_Paulo`, inclusive na virada de ano em UTC); devem falhar antes do T014

### Implementation for User Story 4

- [ ] T014 [US4] Acrescentar `hash_csv` e `anos_padrao` ao `nb-util-010-bronze-camara-cliente` (Python puro); commit pela Git integration e rodar T013 até passar
- [ ] T015 [US4] No `nb-util-020-bronze-camara-gravacao`: `garantir_tabelas()` acrescenta `source_hash STRING` a `ctl_ingestion_runs` com `ALTER TABLE ... ADD COLUMNS` quando ausente; `finalizar_lote(..., source_hash=None)`; `ultimo_hash(recurso, recorte)` devolve o `source_hash` do último lote `succeeded` com aquele recorte; commit pela Git integration
- [ ] T016 [US4] No `nb-incr-040-bronze-camara-despesas`: parâmetro `forcar` (padrão `false`); `origem=arquivo` com `anos` vazio usa `anos_padrao`; por ano, calcula `hash_csv` do CSV extraído e, se igual a `ultimo_hash` e sem `forcar`, termina o lote `skipped` com `message = 'arquivo sem mudança'` e zero registros; senão grava e salva o hash; `origem=api` sem mudança; commit pela Git integration
- [ ] T017 [US4] Rodar quickstart §1 em dev (primeira carga com hash, segunda `skipped`, `forcar=true`); registrar no quickstart
- [ ] T018 [US4] No `pl-010-bronze-camara-gastos`, passar `origem=arquivo` à atividade de despesas; commit pela Git integration
- [ ] T019 [US4] Criar `pl-010-orq-gastos-diario` em `ws-dev-dpacademy` conforme `contracts/notebooks-e-orquestracao.md`: oito atividades de notebook (timeout 2 h, uma retentativa após 300 s), Bronze da Câmara → Bronze do Portal com `Completed`, Silver de cada fonte só com `Succeeded` da Bronze da fonte e depois da última Bronze, Silver em sequência, atividade Fail no fim se qualquer atividade falhar; sem agenda em dev; commit pela Git integration
- [ ] T020 [US4] Em `ci/schedules.json`, trocar as duas entradas por `pl-010-orq-gastos-diario`, `DataPipeline`, `Pipeline`, `enabled: true`, `times: ["04:00"]`, `time_zone` `E. South America Standard Time` (research R3)
- [ ] T021 [US4] Disparar `pl-010-orq-gastos-diario` em dev (quickstart §6, com `limite` pequeno nos fornecedores se precisar) e conferir a ordem e as dependências; registrar no quickstart

---

## Phase 7: User Story 5 - Qualidade verificável e registrada (Priority: P5)

**Goal**: falha de qualidade registrada e interrompendo a rotina, sem gravar dados ruins.

**Independent Test**: quickstart §5.

- [ ] T022 [US5] Acrescentar ao `nb-incr-020-silver-transparencia-emendas` o parâmetro de teste `duplicar_para_teste` (padrão `false`; `true` duplica uma linha do conjunto preparado antes das verificações) e rodar em dev com `true`: execução falha, `unicidade` `failed` com chave de exemplo em `detalhe`, `emendas` inalterada (versão Delta igual); rodar de novo com `false`; commit pela Git integration
- [ ] T023 [US5] Conferir `ctl_quality_checks` nos dois lakehouses (quickstart §5.1) e registrar no quickstart

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T024 [P] Escrever `docs/adr-004-silver-despesas-arquivo-e-chave-hash.md`: origem das despesas (research R1), chave SHA-256 com foto por ano (R4, R6) e detecção de mudança pelo hash do CSV (R2)
- [ ] T025 [P] Em `docs/adr-002-cicd-fabric-cicd.md`, registrar o ruleset `dev-protegida` (sem exclusão e sem force push na `dev`) e o motivo (exclusão automática da `dev` no merge do PR #4)
- [ ] T026 [P] Atualizar `README.md` e `docs/padrao-nomenclatura.md` com os lakehouses, tabelas, notebooks e o orquestrador da Silver; em `specs/003-gastos-bronze-ingestion/contracts/bronze-tables.md` e `data-model.md`, nota apontando para a coluna `source_hash` e para a regra de versão revista nesta feature
- [ ] T027 [P] Reescrever `backlog/backlog.csv` trocando os épicos da NBA pelos do case `gastos` (Bronze, Silver, Gold e Consumo) com as issues de cada um (FR-020)
- [ ] T028 Rodar `pytest tests/unit -q` e `python ci/validate_names.py workspace` (zero violações); trazer `dev` para `004-gastos-silver`; abrir o PR para `dev`, concluir e abrir o PR `dev` → `main`
- [ ] T029 Depois do `deploy-prd` verde, executar quickstart §7 em produção: itens publicados, agenda do orquestrador às 04:00 e agendas por fonte desativadas; carga inicial manual (Bronze de despesas com `anos` vazio, depois os quatro notebooks da Silver) fora do horário da rotina; na manhã seguinte, conferir a primeira execução agendada (SC-005, SC-006); registrar no quickstart

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T002 antes de T003
- **Foundational (Phase 2)**: depende de T002
- **US1, US2 e US3**: dependem da Phase 2; independentes entre si
- **US4**: T013 a T018 independem da Silver e podem começar já; T019 a T021 dependem de US1, US2 e US3 (os notebooks que o orquestrador chama)
- **US5**: depende de T010
- **Polish**: T024 a T027 a qualquer momento; T028 e T029 no fim

### User Story Dependencies

```text
Setup ─► Foundational ─┬─► US1 (P1) ─┐
                       ├─► US2 (P2) ─┼─► US4 orquestrador (T019–T021) ─► Polish
                       └─► US3 (P3) ─┘        ▲
US4 Bronze (T013–T018) ───────────────────────┘
US3 ─► US5
```

### Within Each User Story

- Teste antes do código do cliente (T013 → T014)
- Biblioteca antes dos notebooks; notebook antes do quickstart que o valida
- Notebooks antes do orquestrador; orquestrador antes da agenda em `ci/schedules.json`

### Parallel Opportunities

- T004 e T005 (bibliotecas de fontes diferentes)
- T010 e T011 (notebooks diferentes do Portal)
- T013 e qualquer tarefa da Silver (arquivo de teste fora do Fabric)
- T024 a T027 (documentos diferentes)
- As execuções no Fabric (T007, T009, T012, T017, T021) nunca em paralelo: uma sessão Spark por vez

## Implementation Strategy

### MVP First

1. Phase 1 e 2.
2. US1 (despesas) e validação do quickstart §2: é o fato central da Gold.

### Incremental Delivery

1. US4 Bronze (T013 a T018) logo no início, porque muda a rotina noturna e não depende da Silver.
2. US1 → US2 → US3, cada uma validada antes da seguinte.
3. US5, orquestrador (T019 a T021), Polish.
4. PRs e produção até 2026-11-24 (SC-006).
