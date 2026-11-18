---

description: "Lista de tarefas da feature 005: camada Gold e modelo semântico do case gastos"
---

# Tasks: Camada Gold e modelo semântico do case gastos

**Input**: Design documents from `/specs/005-gastos-gold/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: `pytest` para as funções puras do `nb-util-010-gold-gastos-comum` e para a regra nova do
validador de nomes, como define o plano. Tabelas e modelo são validados pelo quickstart no Fabric
(T-SQL no SQL endpoint e DAX pela API `executeQueries`).

**Organization**: tarefas agrupadas por história de usuário (US1 a US6 da spec).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa incompleta)
- **[Story]**: história de usuário da tarefa (US1 a US6)

## Path Conventions

- Itens do Fabric são criados ou alterados no `ws-dev-dpacademy` a partir de rascunhos locais
  (`Publish-FabNotebook`; modelo pela API `createItem`/`updateDefinition` com TMDL) e chegam ao
  repositório pelo **commit da Git integration** em `dev`, em `workspace/<nome>.<Tipo>/`. A pasta
  `workspace/` MUST NOT ser editada à mão (Princípio III).
- Arquivos fora de `workspace/` (`specs/`, `tests/`, `ci/`, `docs/`, `README.md`) são editados na
  branch `005-gastos-gold`, que recebe `dev` antes do PR.
- O notebook da Gold é um só (`nb-full-020-gold-gastos-modelo`, research R1): as histórias
  acrescentam seções a ele em sequência, e cada uma é validada antes da seguinte.
- `az`, tokens do Fabric, do SQL endpoint e do Power BI sempre com
  `AZURE_CONFIG_DIR=~/.azure-dpacademy`. Os servidores MCP do Fabric não são usados (research R9).
- Uma sessão Spark por vez na capacidade: nunca rodar notebook e sessão de diagnóstico ao mesmo
  tempo; em produção, nada entre 04:00 e 06:30.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: lakehouse, configuração de publicação e validador

- [X] T001 Conferir que a Silver de dev está atualizada (última execução dos quatro notebooks da Silver; rodar de novo se for anterior a 2026-11-17) e registrar as contagens de referência de dev (despesas por ano, emendas por ano e tipo, fornecedores) para o quickstart
- [X] T002 Criar o lakehouse `gold_gastos` em `ws-dev-dpacademy` (sem schemas, como os demais) e fazer commit pela Git integration em `dev` (resulta em `workspace/gold_gastos.Lakehouse/`); anotar o GUID do lakehouse, o servidor SQL e o GUID do SQL endpoint de dev
- [X] T003 Acrescentar a `ci/parameter.yml` a entrada do GUID de dev do `gold_gastos` com `replace_value.prd` = `$items.Lakehouse.gold_gastos.$id` (contrato notebooks-e-orquestracao)
- [X] T004 [P] Acrescentar a `tests/unit/test_validate_names.py` casos para `gold_gastos.ctl_quality_checks` (aceito), `gold_gastos.dim_deputado` (aceito) e `gold_gastos.despesas` (recusado); depois ajustar `validate_table_name` em `ci/validate_names.py` para aceitar `ctl_<assunto>` em lakehouses `gold_` (research R7); `pytest tests/unit -q` verde

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: biblioteca comum da Gold, usada por todas as histórias

- [ ] T005 [P] Escrever `tests/unit/test_gold_comum.py` com os casos do contrato para `normalizar_nome`, `mascarar_cpf`, `formatar_cnpj`, `grupo_emenda`, `ler_localidade` e `UFS` (27 siglas únicas, 5 regiões), carregando o rascunho por `DPACADEMY_NOTEBOOKS_DIR` pelo `conftest.py` existente; confirmar que falham antes da biblioteca existir
- [ ] T006 Criar o rascunho de `nb-util-010-gold-gastos-comum` com as funções puras do contrato (T005 verde) e as funções Spark: `sk()` (`xxhash64` da chave natural), `membros_reservados()`, `garantir_ctl()` (mesmo esquema da Silver), `verificar_unicidade`, `verificar_obrigatorias`, `verificar_integridade(fato, coluna, dim, coluna_dim)`, `verificar_conciliacao(...)`, `verificar_privacidade(df, colunas)`, `gravar(df, tabela)` (`overwrite`, `overwriteSchema`, `delta.parquet.vorder.enabled = true`), `registrar(resultados)` e `encerrar(run_id, resultados)` (exit JSON e exceção se houver `failed`); publicar com `Publish-FabNotebook` e commit pela Git integration
- [ ] T007 Criar o rascunho de `nb-full-020-gold-gastos-modelo` com o esqueleto: parâmetro `injetar_orfao_para_teste`, `%run nb-util-010-gold-gastos-comum`, leitura das cinco tabelas da Silver pelo nome qualificado, `run_id`, `_carregado_em`, lista de resultados e a seção final que só grava se tudo passou; e a `dim_data` (research R3, contrato gold-tables) com as verificações dela

**Checkpoint**: biblioteca e esqueleto prontos; `dim_data` gravada em dev com 2019-01-01 a 2026-12-31.

---

## Phase 3: User Story 1 - Gasto da cota por deputado, partido, UF, tipo e mês (Priority: P1) 🎯 MVP

**Goal**: `fat_despesas` e as dimensões de deputado, partido, UF e tipo de despesa, com totais iguais aos da Silver.

**Independent Test**: quickstart §1.

- [ ] T008 [US1] Acrescentar ao `nb-full-020-gold-gastos-modelo` a `dim_deputado` (cadastro ∪ despesas, lideranças, atributos do cadastro ou da linha mais recente, `tipo_membro`, `no_cadastro`, reservados `-1`/`-2`; research R4), a `dim_partido` (siglas de despesas, deputados e partidos; nome do cadastro ou a sigla), a `dim_uf` (de `UFS`) e a `dim_tipo_despesa` (descrição mais recente por subcota e especificação), com unicidade e obrigatórias de cada uma
- [ ] T009 [US1] Acrescentar a `fat_despesas` (contrato gold-tables), com `sk_fornecedor` provisório `-1` até o T011, as verificações de unicidade, obrigatórias, integridade com cada dimensão e conciliação por ano (linhas e valor líquido) contra `silver_camara.despesas`; publicar e commit pela Git integration
- [ ] T010 [US1] Rodar o notebook em dev e executar o quickstart §1 (totais por ano, lideranças, 234-equivalente de dev fora do cadastro, partido da linha, despesas sem data de emissão); registrar no quickstart

**Checkpoint**: MVP: cota parlamentar analisável por deputado, partido, UF, tipo e mês.

---

## Phase 4: User Story 2 - Fornecedores da cota com o perfil do Portal (Priority: P2)

**Goal**: `dim_fornecedor` com situação de consulta ao Portal e CPF mascarado.

**Independent Test**: quickstart §2.

- [ ] T011 [US2] Acrescentar a `dim_fornecedor` (chaves `J:`/`F:`/`S:`, nome mais frequente com desempate pelo mais recente, `documento_exibicao`, `situacao_portal`, indicadores e `possui_sancao` de `pessoa_juridica`; research R5) e trocar o `sk_fornecedor` provisório da `fat_despesas` pelo real; acrescentar a integridade `fat_despesas.sk_fornecedor` e a verificação `privacidade`; publicar e commit pela Git integration
- [ ] T012 [US2] Rodar em dev e executar o quickstart §2 (soma por situação, formato do CPF, CNPJ com várias grafias uma vez, `privacidade` `passed`); registrar no quickstart

**Checkpoint**: primeiro cruzamento Câmara × Portal pronto.

---

## Phase 5: User Story 3 - Emendas parlamentares ligadas ao deputado (Priority: P3)

**Goal**: `fat_emendas` com as dimensões de emenda e o deputado conformado.

**Independent Test**: quickstart §3.

- [ ] T013 [US3] Acrescentar `dim_tipo_emenda` (com `grupo_emenda`), `dim_funcao`, `dim_localidade` (`ler_localidade`) e `dim_autor_emenda` (ligação por nome normalizado com candidato único entre os membros `Deputado`, `ambíguo` sem ligação, `tipo_autor`, `motivo_sem_ligacao`; research R6), com unicidade e obrigatórias
- [ ] T014 [US3] Acrescentar a `fat_emendas` (contrato gold-tables, `sk_deputado = -2` sem ligação), integridade com cada dimensão, conciliação por ano e tipo (linhas, empenhado, liquidado, pago) contra `silver_transparencia.emendas` e a verificação informativa `ligacao_autor` com o percentual do valor pago individual ligado; publicar e commit pela Git integration
- [ ] T015 [US3] Rodar em dev e executar o quickstart §3 (totais por ano e tipo, relator/bancada/comissão com `-2`, percentual ligado ≥ 60%, ambíguos contados); registrar no quickstart

**Checkpoint**: Gold completa em dev.

---

## Phase 6: User Story 5 - Qualidade da Gold verificável e registrada (Priority: P5)

**Goal**: falha de qualidade impede a gravação; reexecução é determinística.

**Independent Test**: quickstart §4.

> Antes da US4 porque o orquestrador só deve chamar a Gold depois de o comportamento de falha estar provado.

- [ ] T016 [US5] Implementar `injetar_orfao_para_teste` no `nb-full-020-gold-gastos-modelo` (uma linha com `sk_fornecedor` inexistente no fato de despesas preparado); publicar e commit pela Git integration
- [ ] T017 [US5] Executar o quickstart §4: execução normal com todas as verificações `passed`; execução com `injetar_orfao_para_teste=true` falhando em `integridade` e sem versão Delta nova em nenhuma tabela (`DESCRIBE HISTORY`); reexecução normal com as mesmas contagens e os mesmos `sk`; registrar no quickstart

**Checkpoint**: Princípio V comprovado na Gold.

---

## Phase 7: User Story 4 - Atualização diária encadeada após a Silver (Priority: P4)

**Goal**: a rotina diária roda a Gold depois da Silver das duas fontes.

**Independent Test**: quickstart §5 (dev) e §7.4 (prd).

- [ ] T018 [US4] Acrescentar ao `pl-010-orq-gastos-diario` no ws-dev a atividade `gold_gastos` (notebook `nb-full-020-gold-gastos-modelo`, depende de `silver_camara_despesas` e `silver_transparencia_fornecedores` com `Succeeded`, timeout 1 h, 2 retentativas de 180 s) e `falha_gold_gastos` (Fail); commit pela Git integration
- [ ] T019 [US4] Disparar o orquestrador à mão em dev (com `limite` pequeno nos fornecedores, se necessário) e executar o quickstart §5, inclusive o teste de dependência com uma Silver forçada a falhar; registrar no quickstart. Marco: Gold validada em dev até 2026-11-22

**Checkpoint**: Gold pronta para o PR.

---

## Phase 8: User Story 6 - Modelo semântico `sm-gastos` (Priority: P6)

**Goal**: modelo Direct Lake sobre a Gold, com medidas que batem com as tabelas.

**Independent Test**: quickstart §6 (dev) e §7.3 (prd).

- [ ] T020 [US6] Escrever o TMDL de rascunho de `sm-gastos` conforme `contracts/sm-gastos.md`: `database.tmdl`, `model.tmdl` (cultura pt-BR), `expressions.tmdl` com `DatabaseQuery` = `Sql.Database("<servidor SQL de dev>", "<SQL endpoint de dev>")`, uma `tables/<tabela>.tmdl` por dimensão e fato com partição Direct Lake (`mode: directLake`, `entityName`, `schemaName: dbo`, `expressionSource: DatabaseQuery`), colunas com tipo, nome de exibição e `isHidden`, `dim_data` com `dataCategory: Time` e hierarquia Período, medidas nos fatos e `relationships.tmdl` com os 12 relacionamentos
- [ ] T021 [US6] Criar o `sm-gastos` no ws-dev pela API (`POST /workspaces/{ws}/semanticModels` com a definição TMDL em base64, token do contexto dpacademy), conferir que o enquadramento funciona (refresh pela API) e fazer commit pela Git integration (resulta em `workspace/sm-gastos.SemanticModel/`)
- [ ] T022 [US6] Acrescentar a `ci/parameter.yml` as duas entradas do `sm-gastos` (servidor SQL → `$items.Lakehouse.gold_gastos.$sqlendpoint` e SQL endpoint → `$items.Lakehouse.gold_gastos.$sqlendpointid`, `item_type: SemanticModel`, `file_path: **/expressions.tmdl`) com os valores reais de dev; conferir com uma execução local do parâmetro do `fabric-cicd` (sem publicar) que a troca acontece só no `expressions.tmdl`
- [ ] T023 [US6] Executar o quickstart §6 pela API `executeQueries`: totais por ano iguais aos da Gold em T-SQL, `% pago ligado a deputado` igual ao `ligacao_autor`, filtro por partido da despesa, e atualização automática depois de uma nova execução da Gold; registrar no quickstart

**Checkpoint**: modelo pronto para o PR.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T024 [P] Escrever `docs/adr-005-gold-reconstruida-e-direct-lake.md` (reconstrução total com verificação antes de gravar, chaves por hash, CPF mascarado sem hash, ligação de autor por nome exato, Direct Lake sobre SQL endpoint e reapontamento pelo `fabric-cicd`)
- [ ] T025 [P] Atualizar `README.md`: camada Gold (tabelas e grãos) e consumo (`sm-gastos`), estado do case
- [ ] T026 Rodar `pytest tests/unit -q` e `python ci/validate_names.py workspace` (zero violações); trazer `dev` para `005-gastos-gold`; abrir o PR para `dev`, concluir e abrir o PR `dev` → `main` descrevendo o que muda em cada camada (constituição, Fluxo de Desenvolvimento)
- [ ] T027 Depois do `deploy-prd` verde, executar o quickstart §7.1 e §7.2 em produção: itens publicados, `expressions.tmdl` de prd apontando para o SQL endpoint do `gold_gastos` de prd, carga inicial manual da Gold fora da rotina e conferência dos §1 a §4 com os números de prd (SC-006, até 2026-11-26)
- [ ] T028 Executar o quickstart §7.3 em produção: refresh manual único do `sm-gastos` pela API (plano B: assumir o modelo com a conta do engenheiro) e conferência do §6.2 (SC-009, SC-010, até 2026-11-30)
- [ ] T029 Na manhã seguinte à publicação, executar o quickstart §7.4 (Gold depois da Silver, fim antes das 07:00, `ctl_quality_checks` com `environment = 'prd'`, modelo atualizado sem refresh manual; SC-005); registrar no quickstart por um PR pequeno de docs

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T002 antes de T003; T001 e T004 independentes
- **Foundational (Phase 2)**: T005 antes de T006; T006 antes de T007; depende de T002
- **US1 → US2 → US3**: em sequência, porque editam o mesmo notebook e a US2 completa uma chave do fato da US1
- **US5**: depende de US3 (verificações completas)
- **US4**: depende de US5
- **US6**: depende de US3 (tabelas da Gold existentes em dev); T020 pode começar logo depois de T009
- **Polish**: T024 e T025 a qualquer momento; T026 depois de US4 e US6 (ou, se o modelo atrasar, depois de US4, com o modelo num segundo PR); T027 a T029 no fim

### User Story Dependencies

```text
Setup ─► Foundational ─► US1 (P1) ─► US2 (P2) ─► US3 (P3) ─► US5 (P5) ─► US4 (P4) ─┐
                                                     │                               ├─► Polish (PR, prd)
                                                     └──────────► US6 (P6) ──────────┘
```

### Within Each User Story

- Teste antes das funções puras (T005 → T006)
- Dimensões antes do fato que as usa; notebook antes do quickstart que o valida
- Gold validada antes do orquestrador e do modelo

### Parallel Opportunities

- T004 e T005 (arquivos de teste e CI fora do Fabric)
- T020 (TMDL de rascunho, local) em paralelo com T011 a T019
- T024 e T025 (documentos diferentes)
- As execuções no Fabric (T010, T012, T015, T017, T019, T021, T023) nunca em paralelo: uma sessão Spark por vez

## Implementation Strategy

### MVP First

1. Phase 1 e 2.
2. US1 (despesas) e quickstart §1: já sustenta um modelo semântico demonstrável.

### Incremental Delivery

1. US1 → US2 → US3, cada uma validada antes da seguinte.
2. US5 e US4: Gold pronta para produção (marco 2026-11-22 em dev, 2026-11-26 em prd).
3. US6 em paralelo a partir do fim da US3; vai no mesmo PR se estiver pronta, senão num segundo
   PR (modelo em prd até 2026-11-30).
4. Folga para a feature do relatório até o fim do Trial (~2026-12-04).
