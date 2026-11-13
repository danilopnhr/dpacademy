---

description: "Task list for feature 002-naming-standard-cicd"
---

# Tasks: Padrão de nomenclatura e CI/CD do dpacademy

**Input**: Design documents from `/specs/002-naming-standard-cicd/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: incluídos apenas para `ci/validate_names.py`, conforme o plano (`pytest`, seção
Testing). O restante é validado pelo roteiro de [quickstart.md](./quickstart.md).

**Organization**: tarefas agrupadas por user story, para cada uma ser implementada e testada de
forma independente.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1, US2, US3)

## Path Conventions

- Itens do Fabric: `workspace/<item>.<Tipo>/`, escritos **só** pela Git integration do
  `ws-dev-dpacademy`; nunca editar à mão (Princípio III).
- Automação: `.github/` (workflows e template de PR), `ci/` (scripts e configuração), `tests/unit/` (pytest),
  `docs/` (documentação).
- Tarefas de portal (GitHub, Entra ID, Fabric) registram o resultado no arquivo indicado.
- Nenhum segredo é escrito em arquivo do repositório; segredos vão só para os secrets do GitHub
  (repositório e Environment `ws-prd-dpacademy`) e para os Files dos lakehouses.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: repositório remoto, branches, workspaces e estrutura de pastas.

- [X] T001 Criar (se não existir) a conta no GitHub e o repositório **público** `dpacademy`, **sem** README, `.gitignore` nem licença (para o primeiro push não conflitar); adicionar como `origin` no repositório local e enviar `main` (`git remote add origin <url>` e `git push -u origin main`); em Settings → General, deixar só **Allow squash merging** — URL registrada em `docs/adr-002-cicd-fabric-cicd.md`
- [X] T002 Criar a branch `dev` a partir de `main` e enviá-la ao `origin`; criar a branch da feature `002-naming-standard-cicd` a partir de `dev` para os arquivos de `ci/`, `.github/`, `docs/` e `tests/` (o Fabric continua fazendo commit direto em `dev`, só em `workspace/`)
- [X] T003 [P] Em Settings → Code security do repositório, ativar **Secret scanning** e **Push protection** (gratuitos em repositório público; camada extra do Princípio VI, antes mesmo do PR); registrar em `docs/adr-002-cicd-fabric-cicd.md`
- [X] T004 Criar (ou renomear, se já existirem com o nome antigo) os workspaces `ws-dev-dpacademy` e `ws-prd-dpacademy` na capacidade Trial; o engenheiro fica Admin nos dois
- [X] T005 Conectar `ws-dev-dpacademy` ao GitHub: conferir no Admin portal do Fabric a configuração de tenant de sincronização com **GitHub** (separada da do Azure DevOps); gerar um token *fine-grained* do GitHub restrito ao repositório `dpacademy`, com permissão **Contents: Read and write** e expiração definida; em Workspace settings → Git integration, escolher GitHub, criar a conexão com o token, branch `dev`, pasta `workspace/`; **não** conectar `ws-prd-dpacademy` ao Git (research R1); registrar a expiração do token (nunca o valor) em `docs/adr-002-cicd-fabric-cicd.md`
- [X] T006 [P] Criar as pastas `.github/`, `ci/`, `tests/unit/` e `docs/`, e o arquivo `ci/requirements.txt` com `fabric-cicd` e `azure-identity` em versões exatas (`==`), cada uma lançada há pelo menos duas semanas, mais `pytest` para os testes

---

## Phase 2: Laboratório DP-600 (Git integration e deployment pipelines)

**Purpose**: praticar, pela interface, os temas de ciclo de vida e acesso da DP-600 que o fluxo de
produção (com `fabric-cicd`) não exercita. Nada aqui publica em `ws-prd-dpacademy`. Cada tarefa
registra o aprendizado na seção correspondente de `docs/estudo-dp600.md`. Justificativa da
exceção ao Princípio VII: Complexity Tracking do [plan.md](./plan.md).

- [ ] T007 Antes de cada tarefa deste laboratório, ler a parte correspondente do guia de estudo da DP-600 no Microsoft Learn (links em `docs/estudo-dp600.md`) e só então fazer o exercício
- [ ] T008 Testar os quatro papéis de workspace (Admin, Member, Contributor, Viewer) no `ws-dev-dpacademy`: criar no Entra ID o usuário de teste `lab.dp600` (sem licença paga), atribuir um papel por vez e anotar o que ele consegue e não consegue fazer (criar item, editar notebook, compartilhar, gerenciar acesso, ler dados pelo endpoint SQL); remover o usuário do workspace ao final; registrar em `docs/estudo-dp600.md` §2
- [ ] T009 Criar o workspace `ws-lab-dpacademy` na capacidade Trial, com o engenheiro como Admin, e conectá-lo temporariamente a uma branch descartável `lab-git` (a partir de `dev`), pasta `workspace/`; exercitar commit, alteração do mesmo item pelo editor web do GitHub na branch `lab-git`, "Update" e resolução de conflito; anotar o que **não** é versionado (dados, Files, agendamentos); depois **desconectar** o Git de `ws-lab-dpacademy` e apagar a branch `lab-git`; registrar em `docs/estudo-dp600.md` §4
- [ ] T010 Criar o deployment pipeline `dpl-dpacademy-lab` com dois estágios, "Desenvolvimento" (`ws-dev-dpacademy`) e "Laboratório" (`ws-lab-dpacademy`); implantar o `bronze_balldontlie` (depende de T028); usar "Compare" antes e depois de uma alteração em dev, a implantação seletiva e o histórico de implantações; registrar em `docs/estudo-dp600.md` §5 — **substituída pela feature 003** (`specs/003-gastos-bronze-ingestion`): a fonte deixou de ser a balldontlie
- [ ] T011 Depois que a 001 estiver em dev (T041): implantar os notebooks pelo `dpl-dpacademy-lab`, confirmar que o lakehouse padrão foi religado automaticamente ao `bronze_balldontlie` do laboratório (auto-binding), criar uma **regra de implantação** de lakehouse padrão para um notebook no estágio "Laboratório", implantar de novo e comparar com o que o `ci/parameter.yml` faz no `fabric-cicd`; **não** rodar os notebooks no laboratório (não há chave da fonte lá); registrar em `docs/estudo-dp600.md` §5 — **substituída pela feature 003** (`specs/003-gastos-bronze-ingestion`): a fonte deixou de ser a balldontlie
- [ ] T012 Preencher a comparação "deployment pipelines × fabric-cicd" em `docs/estudo-dp600.md` §6 (quando usar cada um, o que cada um troca entre ambientes, onde fica a configuração, como volta atrás) e conferir os nomes `ws-lab-dpacademy` e `dpl-dpacademy-lab` contra `docs/padrao-nomenclatura.md`

**Checkpoint**: temas de acesso, Git integration e deployment pipelines praticados e anotados.

---

## Phase 3: Foundational (Blocking Prerequisites)

**Purpose**: identidade de automação, segredos e configuração de ambientes, necessários para US2 e US3.

**⚠️ CRITICAL**: o `deploy-prd` (US2) não funciona sem esta fase. US1 pode começar em paralelo.

- [ ] T013 Registrar o aplicativo `sp-dpacademy-cicd` no Entra ID, criar um client secret (anotar só a **data de expiração**, nunca o valor) e criar o grupo de segurança `sg-dpacademy-cicd` contendo a SP; registrar IDs não secretos e expiração em `docs/adr-002-cicd-fabric-cicd.md`
- [ ] T014 No portal de administração do Fabric, ativar as configurações de tenant que permitem a service principals usar as APIs públicas do Fabric, restritas ao grupo `sg-dpacademy-cicd` (research R2); registrar as configurações ativadas em `docs/adr-002-cicd-fabric-cicd.md`
- [ ] T015 Adicionar `sp-dpacademy-cicd` como **Admin** apenas no `ws-prd-dpacademy` (nenhum papel em `ws-dev-dpacademy`), conforme a tabela "Ambiente" de [data-model.md](./data-model.md)
- [ ] T016 Criar no repositório (Settings → Secrets and variables → Actions) o **repository secret** `BDL_NBA_API_KEY`, usado só pela busca de segredos do `pr-validation` (research R5)
- [ ] T017 Criar o **Environment** `ws-prd-dpacademy` no GitHub (Settings → Environments) com **Deployment branches** restrito a `main`, as **variáveis** `FABRIC_TENANT_ID` e `SP_CLIENT_ID` e o **secret** `SP_CLIENT_SECRET` ([contracts/ci-pipelines.md](./contracts/ci-pipelines.md))
- [X] T018 [P] Criar `ci/environments.json` exatamente no formato de [contracts/deploy-config.md](./contracts/deploy-config.md), com `workspace_name` e `workspace_id` de `dev` e `prd` (IDs obtidos na URL do workspace)

**Checkpoint**: identidade, segredos e ambientes prontos.

---

## Phase 4: User Story 1 - Padrão de nomenclatura aplicado ao projeto (Priority: P1) 🎯 MVP

**Goal**: o padrão documentado no repositório e um validador que o aplica a todo item versionado.

**Independent Test**: `python ci/validate_names.py workspace/` sai com `0`, os testes passam e a
busca por nomes antigos (quickstart §3) não acha nada.

### Tests for User Story 1

> Escrever primeiro e confirmar que falham antes de T020.

- [X] T019 [P] [US1] Escrever `tests/unit/test_validate_names.py` com `pytest` e `.platform` falsos em `tmp_path`, cobrindo: (a) um válido por tipo do contrato (`bronze_balldontlie`, `gold_nba`, `nb-incr-030-bronze-balldontlie-jogos`, `nb-util-010-bronze-balldontlie-cliente`, `df-full-010-silver-balldontlie-cadastros`, `pl-010-orq-nba-diario`, `sm-nba`, `rpt-nba-temporadas`); (b) inválidos `nb_teste`, `lh_bronze`, `pl-inc-010-bronze-balldontlie-nba`, `nb-full-000-bronze-balldontlie-x`, `nb-full-015-bronze-balldontlie-x`, nome com maiúscula, nome com acento; (c) `nb-full-010-gold-nba-dimensoes` + `nb-incr-010-gold-nba-fatos` → violação de sequencial único; (d) tipo `VariableLibrary` → "tipo sem regra"; (e) formato da linha `ERRO <caminho do .platform>: <tipo> "<displayName>" viola <regra>: <motivo>`, linha de anotação `::error file=<caminho>::` e código de saída `1`, e `0` sem violações; (f) tabelas: `nba_games` e `ctl_ingestion_runs` válidas em `bronze_balldontlie`, `games` e `ingestion_runs` inválidas em `bronze_balldontlie`, `dim_time` válida e `jogos` inválida em `gold_nba`

### Implementation for User Story 1

- [X] T020 [US1] Implementar `ci/validate_names.py` (Python puro, sem dependências) conforme [contracts/naming-rules.md](./contracts/naming-rules.md): blocos `SEQ` = `(?!000)\d{2}0`, `CAMADA` = `(bronze|silver|gold)`, `NOME` = `[a-z0-9]+`; ler `metadata.type` e `metadata.displayName` de cada `workspace/**/.platform`; aplicar a expressão do tipo; sequencial único por (tipo, camada, primeiro `NOME`, `SEQ`) para `Notebook`, `Dataflow` e `DataPipeline`; tipo sem regra bloqueia; constante `LIGAS = {"nba"}` e prefixo `ctl_` para tabelas de controle da fonte; função pública `validate_table_name(lakehouse, table)` que devolve `None` ou o motivo (usada por `ci/deploy.py`); uso `python ci/validate_names.py <pasta>`; saída e códigos exatamente como no contrato; até T019 passar
- [X] T021 [P] [US1] Escrever `docs/padrao-nomenclatura.md` (FR-004): origem (datasource.expert, lado Microsoft) e extensões do dpacademy; Bronze e Silver por fonte, Gold por case; tabela com padrão e exemplo para workspace, lakehouse, tabela (Bronze `<liga>_<endpoint>`, Silver `<liga>_<entidade>`, controle `ctl_<assunto>`, Gold `dim_`/`fat_`/`agg_`), notebook (`full`/`incr`/`util`), Dataflow Gen2, pipeline de camada, pipeline `orq`, modelo semântico e relatório; regras gerais (FR-002), colunas (FR-003: Bronze as-is + auditoria `_`, Silver e Gold `snake_case` em português, `sk_<entidade>`, `codigo_<entidade>`); como adicionar uma liga (`LIGAS`) ou um tipo novo; link para [contracts/naming-rules.md](./contracts/naming-rules.md)
- [X] T022 [P] [US1] Reescrever `README.md`: case NBA via API balldontlie no lugar do Olist; tabela de arquitetura com `bronze_balldontlie`, `silver_balldontlie`, `gold_nba`, `nb-util-010-bronze-balldontlie-cliente`, `nb-full-020-bronze-balldontlie-cadastros`, `nb-incr-030-bronze-balldontlie-jogos`, `pl-010-bronze-balldontlie-nba`, `sm-nba`, `rpt-nba-temporadas`; tabela de ambientes (`dev` → `ws-dev-dpacademy`, `main` → `ws-prd-dpacademy`, publicado pelo `deploy-prd`); fluxo de CI/CD em 4 passos; estrutura do repositório com `.github/`, `ci/`, `tests/`; seção de nomes apontando para `docs/padrao-nomenclatura.md` (sem duplicar a tabela)
- [ ] T023 [US1] Regenerar o plano e as tarefas da 001 (FR-005): apontar `.specify/feature.json` para `specs/001-balldontlie-bronze-ingestion`, trocar `ingestion_runs` por `ctl_ingestion_runs` em todos os artefatos da 001 e rodar `/speckit-plan` e `/speckit-tasks` com estas entradas: notebooks `nb-util-010-bronze-balldontlie-cliente`, `nb-full-020-bronze-balldontlie-cadastros` (teams, players) e `nb-incr-030-bronze-balldontlie-jogos` (games, histórico e diário pelos mesmos parâmetros); liga como parâmetro e recursos por liga em configuração (FR-016 da 001); `ctl_ingestion_runs` com colunas `league` e `environment`, este derivado do nome do workspace `ws-<ambiente>-dpacademy` (research R9); chave em `Files/_secrets/balldontlie_nba_api_key` (research R10); nenhum agendamento em `ws-dev-dpacademy` (a antiga tarefa de agendamento em dev da 001 sai; o agendamento vem de `ci/schedules.json`); remover os avisos "Desatualizado" de `specs/001-balldontlie-bronze-ingestion/plan.md` e `tasks.md`; ao final, apontar `.specify/feature.json` de volta para a 002 — **substituída pela feature 003** (`specs/003-gastos-bronze-ingestion`): a fonte deixou de ser a balldontlie
- [ ] T024 [US1] Rodar a busca do quickstart §3 e corrigir qualquer nome antigo restante em `README.md`, `docs/` e `specs/001-balldontlie-bronze-ingestion/`; o resultado MUST ser zero ocorrências, sem exceções — **substituída pela feature 003** (`specs/003-gastos-bronze-ingestion`): a fonte deixou de ser a balldontlie

**Checkpoint**: US1 completa e testável sem GitHub nem Fabric.

---

## Phase 5: User Story 2 - Fluxo de CI/CD de desenvolvimento para produção (Priority: P2)

**Goal**: PR para `main` validado automaticamente e publicação automática em `ws-prd-dpacademy`.

**Independent Test**: quickstart §4 a §7 e §9: PR com nome ruim ou segredo é bloqueado, push
direto em `main` é recusado, e um PR aprovado aparece em produção em menos de 15 min.

### Implementation for User Story 2

- [X] T025 [P] [US2] Criar `.github/workflows/pr-validation.yml` conforme [contracts/ci-pipelines.md](./contracts/ci-pipelines.md): `on: pull_request` para `main`; job `pr-validation` em `ubuntu-latest`; `permissions: contents: read`; `actions/checkout` com `fetch-depth: 0`; Python 3.11; `pip install -r ci/requirements.txt`; etapa 1 `python ci/validate_names.py workspace/`; etapa 2 `python -m pytest tests/unit -q`; etapa 3 com o repository secret `BDL_NBA_API_KEY` mapeado via `env:`, `git grep -F -l -e "$VALOR" $(git rev-list --all)` e, se houver resultado, `::error::segredo conhecido encontrado em <commit>:<arquivo>` e `exit 1`, sem nunca ecoar o valor; etapa 4 baixar `gitleaks` numa versão exata e rodar `gitleaks detect --source . --log-opts="--all" --redact`
- [ ] T026 [US2] Abrir um PR de teste de `dev` para `main` para o workflow `pr-validation` rodar pela primeira vez (o GitHub só lista um status check como obrigatório depois que ele roda uma vez); conferir as anotações no PR e fechar o PR de teste sem mesclar
- [ ] T027 [US2] Criar o **ruleset** `main-protegida` para `main` conforme research R6 e [contracts/ci-pipelines.md](./contracts/ci-pipelines.md): enforcement **Active**; bypass list **vazia** (vale também para administradores); exigir pull request com **0** aprovações obrigatórias (o GitHub não deixa o autor aprovar o próprio PR); exigir o status check `pr-validation` com a branch atualizada; bloquear force push e exclusão da branch; registrar em `docs/adr-002-cicd-fabric-cicd.md`
- [ ] T028 [US2] Criar o lakehouse `bronze_balldontlie` no `ws-dev-dpacademy` (se a 001 ainda não criou) e fazer commit pelo controle de código do Fabric em `dev` (resulta em `workspace/bronze_balldontlie.Lakehouse/`); anotar o GUID do lakehouse de dev para T029 — **substituída pela feature 003** (`specs/003-gastos-bronze-ingestion`): a fonte deixou de ser a balldontlie
- [ ] T029 [US2] Criar `ci/parameter.yml` no formato `find_replace` do `fabric-cicd`, conforme [contracts/deploy-config.md](./contracts/deploy-config.md): GUID do `ws-dev-dpacademy` → `$workspace.$id`; GUID do `bronze_balldontlie` de dev → `$items.Lakehouse.bronze_balldontlie.$id`; nenhum GUID de produção escrito à mão — **substituída pela feature 003** (`specs/003-gastos-bronze-ingestion`): a fonte deixou de ser a balldontlie
- [X] T030 [US2] Implementar `ci/deploy.py` conforme [contracts/ci-pipelines.md](./contracts/ci-pipelines.md) e [contracts/deploy-config.md](./contracts/deploy-config.md): aceitar só `--environment prd`; ler `ci/environments.json`; credencial `ClientSecretCredential` com `FABRIC_TENANT_ID`, `SP_CLIENT_ID` e `SP_CLIENT_SECRET` das variáveis de ambiente; conferir pela API que o nome do workspace é `ws-prd-dpacademy` antes de publicar; ler `workspace/` no lugar e passar `ci/parameter.yml` por `parameter_file_path` (nunca escrever em `workspace/`); `FabricWorkspace` com `environment="prd"` e tipos `Lakehouse`, `Notebook`, `DataPipeline` (mais `SemanticModel` e `Report` quando existirem no repositório); `publish_all_items` e depois `unpublish_all_orphan_items`; logar itens publicados e removidos; relatório de tabelas listando as tabelas de cada lakehouse de produção pela API e chamando `validate_table_name`, com anotação `::warning::` por divergência; código de saída `1` em falha de publicação; nunca logar a credencial
- [X] T031 [P] [US2] Criar `.github/workflows/deploy-prd.yml` conforme [contracts/ci-pipelines.md](./contracts/ci-pipelines.md): `on: push` para `main` com `paths` `workspace/**`, `ci/**` e o próprio workflow; `concurrency: { group: deploy-prd, cancel-in-progress: false }`; job no Environment `ws-prd-dpacademy`; Python 3.11; `pip install -r ci/requirements.txt`; `python ci/deploy.py --environment prd` com `FABRIC_TENANT_ID` e `SP_CLIENT_ID` (variáveis) e `SP_CLIENT_SECRET` (secret) do Environment mapeados via `env:`
- [X] T032 [P] [US2] Escrever `docs/adr-002-cicd-fabric-cicd.md`: contexto; decisão (research R1 e R2); alternativas rejeitadas (Git integration nos dois workspaces, Deployment pipelines do Fabric); consequências, incluindo o risco aceito de publicação não atômica (R7) e o procedimento de volta (rodar de novo o último `deploy-prd` verde ou reverter o commit em `main`); data de expiração do secret da SP e como renová-lo
- [ ] T033 [US2] Conferir em Actions que o workflow `deploy-prd` foi reconhecido e, em Settings → Environments, que `ws-prd-dpacademy` só aceita deploy a partir de `main`
- [X] T034 [P] [US2] Criar `.github/pull_request_template.md` (template padrão de PR do GitHub) com as seções "Bronze", "Silver", "Gold", "Consumo" e "CI/CD e configuração", cada uma com "o que muda" ou "sem mudança"; "Validações" como checklist (`pr-validation` verde; verificações do Princípio V quando houver Silver ou Gold); e "Feature e issue"
- [ ] T035 [US2] Abrir PR da branch `002-naming-standard-cicd` para `dev`, concluir, e então abrir o primeiro PR `dev` → `main`; com `pr-validation` verde, concluir (squash); validar quickstart §7 (deploy automático, verde, em menos de 15 min, `bronze_balldontlie` em `ws-prd-dpacademy`, deployment registrado no Environment `ws-prd-dpacademy`) — SC-005
- [ ] T036 [US2] Executar quickstart §4, §5 e §6 (PR com `nb_teste` bloqueado; PR com segredo conhecido bloqueado, usando um valor de teste no secret e **nunca** a chave real, porque o repositório é público; push direto em `main` recusado pelo ruleset) e registrar o resultado em `specs/002-naming-standard-cicd/checklists/requirements.md` — SC-003, SC-004
- [ ] T037 [US2] Executar quickstart §9 (renomear item sem deixar órfão; alteração direta em produção revertida na publicação seguinte) e registrar o resultado em `specs/002-naming-standard-cicd/checklists/requirements.md`

**Checkpoint**: US1 e US2 funcionando; produção só muda por PR.

---

## Phase 6: User Story 3 - Ingestão NBA operando em produção (Priority: P3)

> **Substituída pela feature 003** (`specs/003-gastos-bronze-ingestion`, T042): a ingestão em
> produção passa a ser a da Câmara e do Portal da Transparência.

**Goal**: a carga diária da 001 agendada e rodando só em produção, gravando `environment = 'prd'`.

**Independent Test**: quickstart §8: agendamento só em `ws-prd-dpacademy`, notebook de produção
apontando para o lakehouse de produção, execução diária registrada como `prd`.

**Depende de**: US2 e da feature 001 implementada em dev (T041 abaixo).

### Implementation for User Story 3

- [ ] T038 [P] [US3] Criar `ci/schedules.json` exatamente como em [contracts/deploy-config.md](./contracts/deploy-config.md): `pl-010-bronze-balldontlie-nba`, `type` `DataPipeline`, `job_type` `Pipeline`, `enabled: true`, `times: ["06:00"]`, `time_zone` `E. South America Standard Time`
- [X] T039 [US3] Adicionar a `ci/deploy.py` a etapa de agendamentos, entre a publicação e o relatório de tabelas: para cada entrada de `ci/schedules.json`, localizar o item em produção (item ausente falha o deploy), listar os agendamentos pela API de agendamento de jobs do Fabric e criar ou atualizar o agendamento de forma idempotente, com log `agendamento <item> ok (<horário> <fuso>)`; desativar agendamentos ativos de itens de produção que não estão no arquivo; antes, conferir se a versão fixada do `fabric-cicd` já publica agendamentos a partir do Git e, se publicar, usar o recurso nativo (research R8)
- [ ] T040 [US3] Enviar a chave da NBA, sozinha numa linha, para `bronze_balldontlie` de **produção** → `Files/_secrets/balldontlie_nba_api_key` pelo explorador do lakehouse (único passo manual em produção; não altera item); nunca para o repositório
- [ ] T041 [US3] Implementar a 001 em `ws-dev-dpacademy` a partir do plano e das tarefas regenerados em T023 (via `/speckit-implement` da 001) e publicá-la por PR `dev` → `main`; se algum notebook novo usar lakehouse padrão diferente de `bronze_balldontlie`, acrescentar a entrada em `ci/parameter.yml` no mesmo PR
- [ ] T042 [US3] Executar quickstart §8 (lakehouse padrão de produção no notebook; agendamento só em `ws-prd-dpacademy`; execução do dia seguinte com `environment = 'prd'` e nenhuma nova em dev) e registrar em `specs/002-naming-standard-cicd/checklists/requirements.md` — SC-006

**Checkpoint**: todas as user stories funcionando.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T043 [P] Reescrever `backlog/backlog.csv` para o case NBA com os nomes novos: um epic por case (NBA agora; NFL e UCL como epics vazios para o futuro), epics de Fundação e CI/CD com os itens desta feature, e Bronze/Silver/Gold/Consumo da NBA
- [ ] T044 Remover o comentário Sync Impact Report do topo de `.specify/memory/constitution.md` antes do commit da emenda 2.1.1 (já aplicada: Princípio III explícito, exemplos de sequencial corrigidos, prefixo `ctl_`)
- [ ] T045 Rodar o quickstart completo (§1 a §11) e marcar SC-001 a SC-006 em `specs/002-naming-standard-cicd/checklists/requirements.md`
- [ ] T046 [P] Importar `backlog/backlog.csv` como Issues do GitHub: criar o rótulo `epic`; para cada linha `Epic`, uma issue com esse rótulo; para cada `Issue`, uma issue ligada como **sub-issue** do épico acima dela; uma forma prática é um script com `gh issue create` lendo o CSV, salvo em `backlog/importar_issues.ps1`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências. T001 → T002 → T005; T004 antes de T005; T003 depois de T001; T006 a qualquer momento.
- **Laboratório DP-600 (Phase 2)**: T008 depende de T004; T009 de T001, T002 e T004; T010 de T009 e T028; T011 de T010 e T041; T012 por último. Não bloqueia nenhuma user story; fazer T008 a T010 **antes** da Phase 3, para aprender o mecanismo nativo antes do automatizado.
- **Foundational (Phase 3)**: depende de T001 e T004. Bloqueia US2 e US3; **não** bloqueia US1.
- **US1 (Phase 4)**: depende só de T006. T019 → T020; T021, T022 e T023 em paralelo; T024 depois de T021, T022 e T023.
- **US2 (Phase 5)**: depende da Phase 3 e de T020 (o PR roda o validador). T028 depende de T023 (FR-005: plano da 001 corrigido antes de criar itens) e vem antes de T029; T030 depende de T020 (`validate_table_name`) e T029; T026 depois de T025; T033 depois de T031; T035 depois de T026, T027, T030, T033 e T034; T036 e T037 depois de T035.
- **US3 (Phase 6)**: depende de US2 e de T041 (001 implementada). T038 → T039; T040 antes da primeira carga em produção; T042 por último.
- **Polish (Phase 7)**: T043 a qualquer momento; T044 junto do commit da emenda; T045 por último.

### User Story Dependencies

- **US1 (P1)**: independente; testável só localmente.
- **US2 (P2)**: usa o validador de US1 no PR.
- **US3 (P3)**: usa a publicação de US2 e a ingestão da feature 001.

### Prazo

A carga histórica da NBA em produção precisa terminar antes de 2026-11-15 (SC-008 da 001).
Com repositório público, o GitHub Actions não tem fila de concessão de paralelismo; o caminho crítico é T001 → T005 → T028 → T035.

---

## Parallel Example: User Story 1

```text
Task: "T019 Escrever tests/unit/test_validate_names.py"
Task: "T021 Escrever docs/padrao-nomenclatura.md"
Task: "T022 Reescrever README.md"
Task: "T023 Regenerar o plano e as tarefas da 001"
```

## Parallel Example: User Story 2

```text
Task: "T025 Criar .github/workflows/pr-validation.yml"
Task: "T031 Criar .github/workflows/deploy-prd.yml"
Task: "T032 Escrever docs/adr-002-cicd-fabric-cicd.md"
Task: "T034 Criar .github/pull_request_template.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (T006 basta para começar US1) e Phase 4.
2. **Validar**: testes verdes, validador sai com `0`, documento do padrão publicado.
3. Em paralelo, seguir com Phase 1 completa, o laboratório (Phase 2) e a Phase 3 (portal), que dependem de esperas externas.

### Incremental Delivery

1. US1 → padrão documentado e validável.
2. US2 → primeiro PR `dev` → `main` publicando `bronze_balldontlie` em produção.
3. Feature 001 regenerada e implementada em dev.
4. US3 → agendamento em produção e carga histórica antes de 2026-11-15.

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente.
- Tarefas de portal não geram código, mas registram o resultado no arquivo indicado.
- Nunca editar `workspace/` à mão; nunca escrever segredo em arquivo do repositório.
- Commit ao fim de cada tarefa ou grupo lógico, na branch da feature; `main` só por PR.