# Contrato: workflows do GitHub Actions

Dois workflows em `.github/workflows/`, no repositório público `dpacademy` (research R0).

## `pr-validation.yml`

| Campo | Valor |
|---|---|
| Gatilho | `on: pull_request` para `main` |
| Job | `pr-validation` (é o nome do status check obrigatório do ruleset) |
| Executor | `ubuntu-latest` |
| Permissões | `contents: read` |
| Secrets | repository secret `BDL_NBA_API_KEY` (só para a busca por valor) |
| Checkout | `fetch-depth: 0` (histórico completo, para a busca de segredos) |

Etapas, todas obrigatórias; qualquer falha deixa o check vermelho e bloqueia o merge:

1. `python ci/validate_names.py workspace/` (contrato em [naming-rules.md](./naming-rules.md)).
2. `python -m pytest tests/unit -q`.
3. Busca do valor de `BDL_NBA_API_KEY` em todo o histórico. Em caso de ocorrência, falha com
   `::error::segredo conhecido encontrado em <commit>:<arquivo>`, sem imprimir o valor. Se o
   secret não estiver definido (como em PRs vindos de forks), a etapa também falha.
4. `gitleaks detect` sobre o histórico completo, com versão fixa do binário.

## `deploy-prd.yml`

| Campo | Valor |
|---|---|
| Gatilho | `on: push` para `main`, com `paths`: `workspace/**`, `ci/**`, `.github/workflows/deploy-prd.yml` |
| Concorrência | `group: deploy-prd`, `cancel-in-progress: false` (um por vez; só o mais recente espera) |
| Job | `publicar-prd`, no Environment `ws-prd-dpacademy` |
| Executor | `ubuntu-latest` |
| Variáveis do Environment | `FABRIC_TENANT_ID`, `SP_CLIENT_ID` |
| Secret do Environment | `SP_CLIENT_SECRET` |
| Script | `python ci/deploy.py --environment prd` |

Entradas do `ci/deploy.py`:

| Entrada | Origem |
|---|---|
| ID do `ws-prd-dpacademy` | `ci/environments.json` (não é segredo) |
| Credencial | variáveis de ambiente vindas do Environment |
| Itens | `workspace/`, lido no lugar, com `ci/parameter.yml` passado por `parameter_file_path` (nada é escrito em `workspace/`) |
| Tipos publicados | `Lakehouse`, `Notebook`, `DataPipeline` (e `SemanticModel`, `Report` quando existirem) |
| Agendamentos | `ci/schedules.json` |

Etapas e saídas:

1. Publicar todos os itens dos tipos acima; remover os órfãos. Saída: log do `fabric-cicd`.
2. Para cada entrada de `ci/schedules.json`, criar ou atualizar o agendamento no item de produção.
   Saída: "agendamento <item> ok (<horário> <fuso>)".
3. Relatório de tabelas (avisos `::warning::`; ver [naming-rules.md](./naming-rules.md#tabelas-relatório-pós-publicação-não-bloqueia)).
4. Código de saída diferente de `0` em qualquer falha das etapas 1 e 2, o que deixa o run vermelho e
   dispara o e-mail padrão do GitHub. Em caso de sucesso, uma linha no resumo do run
   (`GITHUB_STEP_SUMMARY`) com o workspace e o commit publicado.

## Environment `ws-prd-dpacademy` (configuração, não YAML)

- **Deployment branches**: só `main`.
- Variáveis `FABRIC_TENANT_ID` e `SP_CLIENT_ID`; secret `SP_CLIENT_SECRET`.
- A página do Environment é o histórico de publicações (FR-011).

## Ruleset `main-protegida` (configuração, não YAML)

- Alvo: branch `main`; enforcement **Active**; bypass list **vazia**.
- Exigir pull request, com 0 aprovações obrigatórias (research R6).
- Exigir o status check `pr-validation`, com a branch atualizada antes do merge.
- Bloquear force push e exclusão.
- Nas configurações do repositório, só o merge do tipo squash é permitido.
- Template padrão de PR: `.github/pull_request_template.md`, com o que muda em cada camada
  (Fluxo de Desenvolvimento da constituição).
- Em Code security: secret scanning e push protection ativos (research R5).
