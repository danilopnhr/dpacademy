# Data Model: Padrão de nomenclatura e CI/CD do dpacademy

**Feature**: [spec.md](./spec.md) | **Date**: 2026-10-22

Esta feature não cria tabelas de dados. As entidades são configurações versionadas e registros
mantidos pelo GitHub.

## Regra de nomenclatura

Onde vive: `ci/validate_names.py` (constantes) e `docs/padrao-nomenclatura.md` (descrição).

| Campo | Descrição |
|---|---|
| `tipo` | `metadata.type` do Fabric (`Notebook`, `Lakehouse`...) ou `Tabela` |
| `expressao` | expressão regular do [contrato](./contracts/naming-rules.md) |
| `bloqueia` | `true` para itens do workspace; `false` para tabelas (só aviso) |
| `exemplo` | um nome válido, usado no documento e nos testes |

Validações:

- Todo `tipo` encontrado em `workspace/**/.platform` precisa de uma regra; senão, "tipo sem regra".
- (tipo, camada, fonte ou case, sequencial) é único entre notebooks, dataflows e pipelines.

## Ambiente

Onde vive: `ci/environments.json` e o Environment homônimo do GitHub (só `prd`).

| Campo | `dev` | `prd` |
|---|---|---|
| Workspace | `ws-dev-dpacademy` | `ws-prd-dpacademy` |
| Ramo | `dev` | `main` |
| Como recebe itens | Git integration (o engenheiro edita e faz commit pelo Fabric) | `deploy-prd` com `fabric-cicd` |
| Git integration | conectada, pasta `workspace/` | não conectada |
| Agendamentos | nenhum | os de `ci/schedules.json` |
| Papéis | engenheiro: Admin | engenheiro: Admin; `sp-dpacademy-cicd`: Admin |
| Segredo da fonte | `bronze_balldontlie/Files/_secrets/balldontlie_nba_api_key` | idem, no lakehouse de produção |

O laboratório DP-600 (`ws-lab-dpacademy`, research R12) não é um ambiente do fluxo: recebe itens
de dev pelo deployment pipeline `dpl-dpacademy-lab`, não tem agendamentos nem chave da fonte,
fica sem Git integration (exceto durante o exercício na branch `lab-git`) e não aparece em
`ci/environments.json`.

## Solicitação de mudança (PR)

Onde vive: pull requests do GitHub.

| Campo | Descrição |
|---|---|
| origem → destino | sempre `dev` → `main` |
| validações | resultado do `pr-validation` (nomes, testes, segredo conhecido, gitleaks) |
| aprovador | quem mesclou o PR (com um engenheiro só, o GitHub não permite aprovar o próprio PR; research R6) |
| situação | aberto → mesclado (squash) ou fechado sem merge |

Transições: `aberto` só passa a `mesclado` com o check `pr-validation` verde e a branch atualizada
com `main`; um push novo roda a validação de novo.

## Publicação

Onde vive: página do Environment `ws-prd-dpacademy` no GitHub (deployments).

| Campo | Origem |
|---|---|
| versão | commit squash em `main` |
| PR e quem mesclou | PR ligado ao commit |
| início, fim | run do `deploy-prd` |
| resultado | `succeeded` / `failed` / `canceled` do run |
| itens publicados e removidos | log da etapa 1 do `deploy.py` |
| avisos de tabela | resumo da etapa 3 |

Estados: `em fila` (aguardando o grupo de concorrência) → `em execução` → `succeeded` ou
`failed`. Se vários commits chegam durante uma publicação, só o mais recente fica na fila e é
publicado em seguida.

## Reflexo na feature 001

`ingestion_runs` passa a se chamar `ctl_ingestion_runs` (constituição 2.1.1) e ganha a coluna `environment` (`dev` ou `prd`), derivada do nome do workspace
(research R9). A alteração da tabela é feita no plano regenerado da 001.
