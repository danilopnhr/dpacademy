---

description: "Lista de tarefas da feature 003: ingestão Bronze do case gastos"
---

# Tasks: Ingestão Bronze do case gastos (Câmara + Portal da Transparência)

**Input**: Design documents from `/specs/003-gastos-bronze-ingestion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: incluídos para os clientes HTTP e para o validador de nomes, porque o plano define
`pytest` local (research R7) e o quickstart §1 depende deles. Os notebooks com Spark são
validados pelo quickstart no Fabric.

**Organization**: tarefas agrupadas por história de usuário (US1 a US5 da spec).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa incompleta)
- **[Story]**: história de usuário da tarefa (US1 a US5)

## Path Conventions

- Itens do Fabric são criados no workspace `ws-dev-dpacademy` (interface ou MCP do Fabric) e
  chegam ao repositório pelo **commit da Git integration** em `workspace/<nome>.<Tipo>/`. A pasta
  `workspace/` MUST NOT ser editada à mão (Princípio III).
- Arquivos fora de `workspace/` (`tests/`, `ci/`, `docs/`, `.github/`) são editados na branch
  `003-gastos-bronze-ingestion`, criada a partir de `dev`.
- Notebooks de carga fazem `%run` do cliente e da gravação da própria fonte; o lakehouse padrão
  de cada notebook é o da sua fonte.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: ambiente, lakehouses e segredo

- [X] T001 Conferir os pré-requisitos da feature 002: repositório `dpacademy` no GitHub, branch `dev` e `ws-dev-dpacademy` conectado ao Git na pasta `workspace/` (tarefas T001, T002 e T005 de `specs/002-naming-standard-cicd/tasks.md`); se faltarem, executá-las primeiro. Criar a branch `003-gastos-bronze-ingestion` a partir de `dev`
- [X] T002 Criar os lakehouses `bronze_camara` e `bronze_transparencia` em `ws-dev-dpacademy` e fazer commit pelo controle de código do Fabric em `dev` (resulta em `workspace/bronze_camara.Lakehouse/` e `workspace/bronze_transparencia.Lakehouse/`); anotar os GUIDs de dev dos dois para T007
- [ ] T003 [P] Cadastrar a chave da API em https://portaldatransparencia.gov.br/api-de-dados com a conta gov.br e gravar só o valor, sem quebra de linha, em `bronze_transparencia/Files/_secrets/transparencia_api_key` no `ws-dev-dpacademy`, pela interface do lakehouse (research R5); nunca colar a chave em notebook, terminal com histórico ou arquivo do repositório
- [ ] T004 [P] Criar o repository secret `TRANSPARENCIA_API_KEY` no GitHub (Settings → Secrets and variables → Actions), usado só pela busca de segredos do `pr-validation`; se o `BDL_NBA_API_KEY` (T016 da 002) já existir, apagá-lo

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: CI alinhado à constituição v3.0.0 e base de testes

**⚠️ CRITICAL**: o deploy de produção bloqueia tabelas sem prefixo de liga até T006 terminar

- [X] T005 [P] Atualizar o item (f) de `tests/unit/test_validate_names.py` para a regra da constituição v3.0.0: em `bronze_camara`, `despesas`, `deputados` e `ctl_ingestion_runs` são válidas; em `bronze_transparencia`, `pessoa_juridica` é válida; `Despesas`, `despesas-2024` e `despésas` são inválidas; `dim_tempo` válida e `despesas` inválida em `gold_gastos`; trocar nos itens (a) a (c) os exemplos `balldontlie`/`nba` por `camara`/`gastos` (`nb-incr-040-bronze-camara-despesas`, `nb-util-010-bronze-transparencia-cliente`, `pl-010-orq-gastos-diario`, `sm-gastos`, `rpt-gastos-parlamentares`, colisão `nb-full-010-gold-gastos-dimensoes` + `nb-incr-010-gold-gastos-fatos`)
- [X] T006 Alterar `ci/validate_names.py`: remover `LIGAS`; em `validate_table_name`, tabelas de `bronze_*` e `silver_*` passam a exigir só `snake_case` sem acento (o nome da entidade da fonte, Princípio IV), com `ctl_` continuando aceito; mensagem "tabela de <lakehouse> precisa estar em snake_case, sem acentos"; Gold sem mudança; até T005 passar com `pytest tests/unit -q`
- [X] T007 [P] Em `ci/parameter.yml`, trocar a entrada do `bronze_balldontlie` por duas entradas `find_replace` (GUID de dev do `bronze_camara` → `$items.Lakehouse.bronze_camara.$id`; GUID de dev do `bronze_transparencia` → `$items.Lakehouse.bronze_transparencia.$id`), conforme `specs/002-naming-standard-cicd/contracts/deploy-config.md`
- [X] T008 [P] Em `.github/workflows/pr-validation.yml`, trocar a busca do valor de `BDL_NBA_API_KEY` pela do secret `TRANSPARENCIA_API_KEY` em todo o histórico, sem imprimir o valor
- [X] T009 [P] Criar `tests/unit/conftest.py` com a fixture `carregar_notebook(nome)` que lê `workspace/<nome>.Notebook/notebook-content.py`, descarta linhas de metadados e comandos mágicos do Fabric (`# METADATA`, `# CELL`, `# MARKDOWN`, linhas iniciadas por `%`) e executa o restante num módulo novo, devolvendo o módulo; falha com mensagem clara se o arquivo não existir (ainda não sincronizado)
- [X] T010 [P] Escrever `docs/adr-003-segredo-api-em-lakehouse-files.md`: decisão, motivo, risco aceito e migração futura de research R5; caminho `bronze_transparencia/Files/_secrets/transparencia_api_key`; envio manual em dev e em produção; a Câmara não usa chave

**Checkpoint**: `pytest tests/unit -q` verde e CI sem referência à balldontlie

---

## Phase 3: User Story 1 - Histórico da cota parlamentar (Priority: P1) 🎯 MVP

**Goal**: cadastros da Câmara e despesas de 2019 a 2026 na `bronze_camara`, sem chave

**Independent Test**: carregar 2024 e conferir 173.961 despesas e ~R$ 211,4 mi de valor líquido (quickstart §3)

### Tests for User Story 1

- [X] T011 [P] [US1] Escrever `tests/unit/test_camara_cliente.py` (com `requests` simulado e `time.sleep` substituído), carregando `nb-util-010-bronze-camara-cliente` pela fixture de T009, cobrindo: paginação seguindo `links[rel=next]` até não haver `next`; `expected_total` lido de `X-Total-Count`; detalhe por id devolvendo `dados` objeto; intervalo mínimo de 0,25 s entre requisições; retentativa em 429 respeitando `Retry-After`; 5xx e erro de conexão com esperas 15, 30, 60, 120 e 240 s e falha após 5 tentativas; outros 4xx falhando na hora com o corpo truncado em 300 caracteres; contadores `requests_made` e `retries`; `baixar_cotas(ano, destino)` gravando o zip e devolvendo `None` em 404; `normalizar_cabecalho` removendo o BOM de `﻿txNomeParlamentar`

### Implementation for User Story 1

- [X] T012 [US1] Criar o notebook `nb-util-010-bronze-camara-cliente` em `ws-dev-dpacademy`, só com Python puro (sem Spark e sem `notebookutils`), conforme `contracts/camara-api.md` e research R8: classe `ClienteCamara` com `get(caminho, params) -> (dados, total)`, `paginar(caminho, params)` (gerador de registros, `itens=100`), `detalhe(caminho)`, ritmo mínimo de 0,25 s, retentativas e contadores; funções `baixar_cotas(ano, destino)` (URL `https://www.camara.leg.br/cotas/Ano-<AAAA>.csv.zip`) e `normalizar_cabecalho(nome)`; fazer commit pelo Fabric (gera `workspace/nb-util-010-bronze-camara-cliente.Notebook/notebook-content.py`) e rodar T011 até passar
- [X] T013 [US1] Criar o notebook `nb-util-020-bronze-camara-gravacao` (PySpark) conforme `contracts/bronze-tables.md` e research R8 e R9: `ambiente()` extraindo `dev`/`prd` de `ws-<ambiente>-dpacademy`; `garantir_tabelas()` com `CREATE TABLE IF NOT EXISTS` das tabelas de dados (`payload STRING`, `_ingested_at TIMESTAMP`, `_source_endpoint STRING`, `_batch_id STRING`, `_origem STRING`, `_recorte STRING`) e de `ctl_ingestion_runs` com todas as colunas do contrato; `iniciar_lote(fonte, recurso, origem, recorte)` que marca como `failed` (motivo `stale`) linhas `running` do recurso com mais de 6 h, devolve `skipped` se houver `running` com menos de 6 h e senão grava `running`; `gravar_lote(tabela, registros, ...)` com um único append e o mesmo `_ingested_at` para o lote todo; `finalizar_lote(batch_id, status, contagens, message)` com `MERGE` por `batch_id`; `message` sanitizada e cortada em 1.000 caracteres; commit pelo Fabric
- [X] T014 [US1] Criar o notebook `nb-full-030-bronze-camara-cadastros` com os parâmetros de `contracts/notebook-parameters.md` (`recursos`, `legislaturas`): um lote por recurso; `legislaturas` e `partidos` paginados por inteiro; `deputados` = ids distintos de `/deputados?idLegislatura=<cada legislatura>` seguidos do detalhe `/deputados/{id}` de cada um; registro sem `id` no `payload` faz o lote terminar `failed`; `_recorte` com os parâmetros; `expected_total` do `X-Total-Count`; saída `notebookutils.notebook.exit` com o JSON do contrato e exceção no fim se algum lote falhar; commit pelo Fabric
- [X] T015 [US1] Criar o notebook `nb-incr-040-bronze-camara-despesas` com o modo `origem=arquivo` (parâmetros `origem`, `anos`; `anos` obrigatório nesse modo): para cada ano, um lote que baixa o zip em `Files/_landing/cotas/Ano-<AAAA>.csv.zip` (sobrescrevendo), descompacta, lê com `spark.read.csv` (`sep=';'`, `header=True`, `encoding='UTF-8'`, `multiLine=True`, `quote='"'`, `escape='"'`, todas as colunas texto), renomeia colunas com `normalizar_cabecalho`, monta `payload = to_json(struct(*))`, `_origem='arquivo'`, `_source_endpoint` = URL do arquivo, `_recorte={"ano":AAAA}`, `expected_total` = linhas lidas, aviso em `message` com a contagem de linhas sem `ideDocumento`; zip inexistente (404) = zero registros, aviso e `succeeded`; deixar o modo `api` levantando `NotImplementedError` até T020; commit pelo Fabric
- [X] T016 [US1] Validar no Fabric os §2 e §3 do `quickstart.md` em `ws-dev-dpacademy`: cadastros; 2024 com 173.961 despesas e ~R$ 211,4 mi; recarga de 2024 gerando um segundo `_batch_id`; anos 2019 a 2023, 2025 e 2026 com total da Câmara abaixo de 2 h somadas (SC-001, SC-003); anotar os tempos medidos no fim do `quickstart.md`

**Checkpoint**: MVP: ~1,27 mi de despesas e cadastros na Bronze, conferidos contra o arquivo da fonte

---

## Phase 4: User Story 2 - Atualização recorrente da cota parlamentar (Priority: P2)

**Goal**: carga diária pela API, mês a mês, com janela de três meses

**Independent Test**: carregar o mês anterior e conferir `records_collected` = `expected_total` (quickstart §4)

### Tests for User Story 2

- [X] T017 [US2] Acrescentar a `tests/unit/test_camara_cliente.py` os casos de `meses_padrao(hoje)` (mês corrente e os dois anteriores; `2026-01-15` → `2025-11, 2025-12, 2026-01`) e `ler_meses("2026-08,2026-09")` (lista de `(ano, mes)`; formato inválido levanta `ValueError`)

### Implementation for User Story 2

- [X] T018 [US2] Acrescentar ao notebook `nb-util-010-bronze-camara-cliente` as funções `meses_padrao(hoje)` (data no fuso `America/Sao_Paulo`) e `ler_meses(texto)`; commit pelo Fabric e rodar T017 até passar
- [X] T019 [US2] Implementar no `nb-incr-040-bronze-camara-despesas` o modo `origem=api` (parâmetros `meses`, `legislatura`; `meses` vazio → `meses_padrao`): um lote por mês; fila = ids de `/deputados?idLegislatura=<legislatura>`; para cada deputado, `paginar('/deputados/{id}/despesas', {ano, mes})`; `payload` = objeto da API, `_origem='api'`, `_source_endpoint='/deputados/{id}/despesas'`, `_recorte={"ano","mes","deputado"}`; `expected_total` = soma dos `X-Total-Count`; registro sem `codDocumento` faz o lote falhar; commit pelo Fabric
- [X] T020 [US2] Criar o pipeline `pl-010-bronze-camara-gastos` em `ws-dev-dpacademy`: atividade `nb-full-030-bronze-camara-cadastros` → `nb-incr-040-bronze-camara-despesas` (padrões) com dependência "Completed"; atividade Fail final quando qualquer uma das duas falhar, para o pipeline terminar com falha (contracts/notebook-parameters.md); sem agenda em dev; commit pelo Fabric
- [X] T021 [P] [US2] Acrescentar a `ci/schedules.json` a entrada `{"item": "pl-010-bronze-camara-gastos", "type": "DataPipeline", "job_type": "Pipeline", "enabled": true, "times": ["05:00"], "time_zone": "E. South America Standard Time"}`
- [ ] T022 [US2] Validar o §4 do `quickstart.md` em dev: padrões (3 lotes) e `meses=<mês passado>`; conferir `records_collected = expected_total` por lote; rodar o pipeline à mão uma vez

**Checkpoint**: US1 e US2 operando; a Câmara fica completa sem depender do Portal

---

## Phase 5: User Story 3 - Emendas parlamentares (Priority: P3)

**Goal**: emendas de 2019 até o ano corrente na `bronze_transparencia`, com a chave protegida

**Independent Test**: carregar 2024 e conferir `records_written = records_collected`; com a chave renomeada, falha imediata sem a chave na mensagem (quickstart §5)

### Tests for User Story 3

- [ ] T023 [P] [US3] Escrever `tests/unit/test_transparencia_cliente.py` (com `requests` simulado e relógio injetável), carregando `nb-util-010-bronze-transparencia-cliente`, cobrindo: header `chave-api-dados` enviado; chave lida de um caminho de arquivo passado ao construtor e ausente de `repr`, das mensagens de exceção e de `message`; 401 e 403 falhando na hora com "chave da API ausente ou inválida" e sem retentativa; arquivo de chave inexistente ou vazio com a mesma mensagem; paginação por `pagina` desde 1 até a lista vazia; intervalo de 0,7 s das 06:00 às 23:59 e de 0,25 s das 00:00 às 05:59 em `America/Sao_Paulo`; retentativa em 429 com `Retry-After` e em 5xx com esperas exponenciais; `pessoa_juridica(cnpj)` devolvendo `("nao_encontrado", None)` para 404, corpo vazio, objeto sem `cnpj` ou com todos os campos nulos, e `("encontrado", objeto)` caso contrário

### Implementation for User Story 3

- [ ] T024 [US3] Criar o notebook `nb-util-010-bronze-transparencia-cliente` (Python puro), conforme `contracts/transparencia-api.md`: classe `ClienteTransparencia(caminho_chave, relogio=...)` com `paginar(caminho, params)`, `pessoa_juridica(cnpj)`, ritmo por faixa de horário, retentativas, contadores e sanitização de mensagens; commit pelo Fabric e rodar T023 até passar
- [ ] T025 [US3] Criar o notebook `nb-util-020-bronze-transparencia-gravacao` com o mesmo contrato do T013, mais as colunas `_cnpj STRING` e `_resultado STRING` na tabela `pessoa_juridica` (`payload` pode ser nulo quando `_resultado = 'nao_encontrado'`), conforme `contracts/bronze-tables.md`; commit pelo Fabric
- [ ] T026 [US3] Executar o §5.1 do `quickstart.md` em dev (sem imprimir a chave): tamanho da página de `/emendas`, resposta a CNPJ inexistente e ausência de 429 em 200 chamadas a 0,7 s; registrar os achados em `specs/003-gastos-bronze-ingestion/contracts/transparencia-api.md` e ajustar o cliente (T024) se algo divergir
- [ ] T027 [US3] Criar o notebook `nb-incr-030-bronze-transparencia-emendas` (parâmetro `anos`; vazio → ano corrente e o anterior): um lote por ano com `paginar('/emendas', {ano})`; registro sem `codigoEmenda` faz o lote falhar; `_origem='api'`, `_recorte={"ano":AAAA}`; chave lida de `/lakehouse/default/Files/_secrets/transparencia_api_key`; commit pelo Fabric
- [ ] T028 [US3] Validar os §5.2 e §5.3 do `quickstart.md` em dev; depois carregar `anos=2019,2020,2021,2022,2023,2025,2026` e conferir cada lote `succeeded` com `records_written = records_collected` (SC-002); anotar o volume por ano no fim do `quickstart.md`

**Checkpoint**: emendas na Bronze; chave validada fora do código

---

## Phase 6: User Story 4 - Cadastro dos fornecedores (Priority: P4)

**Goal**: cadastro de PJ de ≥ 95% dos ~68 mil CNPJs das despesas antes de 2026-11-30

**Independent Test**: `limite=1000` gera 2 lotes de 500 e a fila diminui 1.000; uma segunda execução não repete CNPJ (quickstart §6)

**Depende de**: US1 (despesas na `bronze_camara`) e US3 (cliente e gravação do Portal)

### Implementation for User Story 4

- [ ] T029 [US4] Criar o notebook `nb-incr-040-bronze-transparencia-fornecedores` (parâmetros `limite`=15000, `tamanho_bloco`=500): fila conforme research R10, com os dígitos de `get_json_object(payload,'$.txtCNPJCPF')` ou `'$.cnpjCpfFornecedor'` de `bronze_camara.despesas` com exatamente 14 dígitos, distintos, menos os `_cnpj` já presentes em `bronze_transparencia.pessoa_juridica`, em ordem crescente, até `limite`; um lote por bloco com `pessoa_juridica(cnpj)` para cada CNPJ, gravando `_cnpj`, `_resultado` e `payload`; `_source_endpoint='/pessoa-juridica'`, `_recorte={"cnpjs": n, "primeiro": "...", "ultimo": "..."}`; registrar no topo do notebook, em comentário, o desvio do Princípio I justificado no Complexity Tracking do `plan.md`; commit pelo Fabric
- [ ] T030 [US4] Criar o pipeline `pl-010-bronze-transparencia-gastos`: `nb-incr-030-bronze-transparencia-emendas` → `nb-incr-040-bronze-transparencia-fornecedores` (padrões) com dependência "Completed" e atividade Fail final como em T020; sem agenda em dev; commit pelo Fabric
- [ ] T031 [P] [US4] Acrescentar a `ci/schedules.json` a entrada `{"item": "pl-010-bronze-transparencia-gastos", "type": "DataPipeline", "job_type": "Pipeline", "enabled": true, "times": ["01:00"], "time_zone": "E. South America Standard Time"}`
- [ ] T032 [US4] Validar os §6.1 a §6.3 do `quickstart.md` em dev; em seguida, disparar a carga completa à mão depois da meia-noite (limite de madrugada) e repetir na noite seguinte até a fila ficar abaixo de 5% dos CNPJs distintos (SC-004, prazo 2026-11-30)

**Checkpoint**: fornecedores enriquecidos; todas as tabelas da Bronze do case preenchidas

---

## Phase 7: User Story 5 - Acompanhamento das execuções (Priority: P5)

**Goal**: toda execução auditável em `ctl_ingestion_runs`, com concorrência bloqueada

**Independent Test**: uma execução com sucesso e uma com chave inválida aparecem com status e motivo corretos (quickstart §7)

- [ ] T033 [US5] Ao final de cada notebook de carga (`nb-full-030-bronze-camara-cadastros`, `nb-incr-040-bronze-camara-despesas`, `nb-incr-030-bronze-transparencia-emendas`, `nb-incr-040-bronze-transparencia-fornecedores`), exibir com `display` as linhas de `ctl_ingestion_runs` do `run_id` atual (recurso, recorte, status, contagens, `message`), sem nenhum dado da chave; commit pelo Fabric
- [ ] T034 [US5] Validar o §7 do `quickstart.md` em dev: duas execuções seguidas de `nb-full-030-bronze-camara-cadastros` (a segunda com lotes `skipped`); uma linha `running` antiga forçada à mão (mais de 6 h) virando `failed` com `stale`; todas as execuções das fases anteriores presentes com status correto (SC-007)

**Checkpoint**: todas as histórias validadas em dev

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: documentação, segredos, publicação

- [ ] T035 [P] Reescrever `README.md`: fontes Câmara + Portal da Transparência e case `gastos` no lugar da balldontlie/NBA; tabela de camadas com `bronze_camara`, `bronze_transparencia`, os notebooks e pipelines desta feature, `silver_camara`, `silver_transparencia`, `gold_gastos`, `sm-gastos`, `rpt-gastos-parlamentares`; seção de nomes apontando para `docs/padrao-nomenclatura.md`
- [ ] T036 [P] Atualizar `docs/padrao-nomenclatura.md`: tabelas Bronze e Silver com o nome da entidade da fonte, sem prefixo de liga; exemplos `camara`, `transparencia` e `gastos` no lugar de `balldontlie` e `nba`; remover "como adicionar uma liga"
- [ ] T037 [P] Atualizar `docs/adr-002-cicd-fabric-cicd.md`: busca do valor de `TRANSPARENCIA_API_KEY` no lugar da chave da balldontlie e segredo em `bronze_transparencia/Files/_secrets/transparencia_api_key`, com link para a ADR-003
- [ ] T038 [P] Atualizar os exemplos de `specs/002-naming-standard-cicd/contracts/deploy-config.md` e `contracts/naming-rules.md` (tabelas sem `LIGA`, `bronze_camara`, `pl-010-bronze-camara-gastos`); nas tarefas abertas de `specs/002-naming-standard-cicd/tasks.md` que citam `bronze_balldontlie` ou a feature 001 (T010, T011, T023, T024, T028, T029 e a Phase 6), anotar que foram substituídas por esta feature
- [ ] T039 [P] Em `.claude/settings.json`, trocar as permissões `WebFetch` dos domínios `*.balldontlie.io` por `dadosabertos.camara.leg.br`, `www.camara.leg.br` e `api.portaldatransparencia.gov.br`
- [ ] T040 Rodar `pytest tests/unit -q` e `python ci/validate_names.py workspace` (zero violações) e a busca do §8 do `quickstart.md` (SC-008); conferir também a saída das células dos notebooks executados
- [ ] T041 Remover o comentário "Sync Impact Report" do topo de `.specify/memory/constitution.md` e fazer os commits da branch `003-gastos-bronze-ingestion` (constituição v3.0.0, specs, `ci/`, `docs/`, `tests/`, `.github/`); abrir o PR para `dev`
- [ ] T042 Quando o fluxo de publicação da feature 002 estiver ativo: enviar a chave para `bronze_transparencia/Files/_secrets/transparencia_api_key` do `ws-prd-dpacademy` à mão, abrir o PR de `dev` para `main` e conferir em produção as duas agendas de `ci/schedules.json` e a primeira execução de cada pipeline (FR-009, SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: depende das tarefas T001, T002 e T005 da feature 002
- **Foundational (Phase 2)**: depende do Setup; T006 depende de T005
- **US1 (Phase 3)**: depende de T002 e T009
- **US2 (Phase 4)**: depende de US1 (estende o cliente e o notebook de despesas)
- **US3 (Phase 5)**: depende de T002, T003 e T009; independente de US1 e US2
- **US4 (Phase 6)**: depende de US1 (despesas na Bronze) e de US3 (cliente e gravação do Portal)
- **US5 (Phase 7)**: depende dos notebooks de carga existirem (US1 a US4)
- **Polish (Phase 8)**: T035 a T039 podem começar a qualquer momento após a Phase 2; T040 a T042 no fim

### User Story Dependencies

```text
Setup ─► Foundational ─┬─► US1 (P1) ─► US2 (P2)
                       │      │
                       └─► US3 (P3) ─┴─► US4 (P4) ─► US5 (P5) ─► Polish
```

### Within Each User Story

- Teste do cliente antes do cliente (T011 → T012, T017 → T018, T023 → T024)
- Cliente e gravação antes dos notebooks de carga
- Notebook de carga antes do pipeline e da agenda
- Validação do quickstart fecha cada história

### Parallel Opportunities

- Phase 1: T003 e T004 em paralelo com T002
- Phase 2: T005, T007, T008, T009 e T010 em paralelo; T006 depois de T005
- Depois da Phase 2: US1 e US3 em paralelo (fontes independentes)
- T021 e T031 (agendas) em paralelo com os pipelines
- Phase 8: T035 a T039 em paralelo

---

## Parallel Example: User Story 1

```text
Task: "T011 Escrever tests/unit/test_camara_cliente.py"
Task: "T023 Escrever tests/unit/test_transparencia_cliente.py"   # US3, outra fonte
```

## Parallel Example: Foundational

```text
Task: "T005 Atualizar tests/unit/test_validate_names.py"
Task: "T007 Atualizar ci/parameter.yml"
Task: "T008 Atualizar .github/workflows/pr-validation.yml"
Task: "T009 Criar tests/unit/conftest.py"
Task: "T010 Escrever docs/adr-003-segredo-api-em-lakehouse-files.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 e Phase 2
2. Phase 3 (US1): cadastros e histórico de despesas pelo arquivo anual
3. **PARAR E VALIDAR**: quickstart §3, conferido contra a tabela de research R2
4. A Bronze da Câmara já sustenta a primeira Silver e a Gold do case `gastos`

### Incremental Delivery

1. US1 → 1,27 mi de despesas (MVP, sem chave)
2. US2 → Câmara se mantém atualizada sozinha
3. US3 → emendas (primeira carga com chave)
4. US4 → fornecedores (duas madrugadas, prazo 2026-11-30)
5. US5 → operação auditável
6. Polish → documentação e publicação em produção

### Prazo

O Trial termina por volta de 2026-12-05. US1 e US3 podem andar juntas para que a carga de
fornecedores (US4) comece até 2026-11-27, deixando duas madrugadas de folga antes de 2026-11-30.

---

## Notes

- [P] = arquivos diferentes, sem dependência de tarefa incompleta
- Nenhuma tarefa edita `workspace/` à mão; todo item do Fabric chega pelo commit da Git integration
- A chave do Portal nunca aparece em notebook, log, `ctl_ingestion_runs` ou repositório
- Commit ao fim de cada tarefa ou grupo lógico; parar em cada checkpoint para validar
