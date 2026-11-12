# Implementation Plan: Padrão de nomenclatura e CI/CD do dpacademy

**Branch**: `002-naming-standard-cicd` | **Date**: 2026-10-22 (revisado em 2026-10-23) | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-naming-standard-cicd/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Documentar o padrão datasource.expert adotado na constituição e montar o fluxo
`dev` → PR → `main` → produção no GitHub, com repositório público e GitHub Actions (research R0).

- **Desenvolvimento**: o `ws-dev-dpacademy` fica ligado à branch `dev` pela Git integration.
- **Validação**: todo PR para `main` passa pelo `pr-validation`, que confere os nomes dos itens
  (lidos dos `.platform`), roda os testes e procura segredos, tanto os valores conhecidos quanto o
  `gitleaks`, em todo o histórico.
- **Publicação**: concluído o PR, o `deploy-prd` publica no `ws-prd-dpacademy` com `fabric-cicd`.
  Ele troca os IDs de ambiente pelo `parameter.yml`, remove itens órfãos e aplica os agendamentos
  versionados. O `ws-prd-dpacademy` não é conectado ao Git.
- **Autenticação e registro**: a publicação usa uma service principal gratuita do Entra ID. O
  Environment `ws-prd-dpacademy` do GitHub guarda cada publicação.
- **Laboratório DP-600**: um workspace `ws-lab-dpacademy` e um deployment pipeline do Fabric
  `dpl-dpacademy-lab` (dev → lab) para praticar os temas de ciclo de vida da prova que o fluxo
  de produção não exercita. O laboratório não publica em produção (research R12).

## Technical Context

**Language/Version**: Python 3.11 (scripts de CI); YAML do GitHub Actions

**Primary Dependencies**: `fabric-cicd` e `azure-identity` (versões fixas em
`ci/requirements.txt`, ambas com pelo menos duas semanas de lançamento); `gitleaks` (binário com
versão fixa); localmente `pytest`

**Storage**: N/A (configuração versionada em `ci/`; registros no GitHub)

**Testing**: `pytest` para `ci/validate_names.py` (casos válidos e inválidos por tipo); roteiro
ponta a ponta em [quickstart.md](./quickstart.md)

**Target Platform**: GitHub (repositório público, Actions com `ubuntu-latest`, Issues) e
Microsoft Fabric (Trial), workspaces `ws-dev-dpacademy` e `ws-prd-dpacademy`

**Project Type**: automação de CI/CD para itens do Fabric

**Performance Goals**: mudança aprovada em produção em menos de 15 min (SC-005); validação de PR
em menos de 5 min

**Constraints**: custo zero (sem assinatura Azure); `workspace/` nunca é escrito à mão; nenhum
segredo no repositório nem nos logs; uma publicação por vez

**Scale/Scope**: um engenheiro, dois ambientes, cerca de 10 itens no primeiro case, crescendo por
case (NBA, depois NFL ou UCL)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Verificação | Resultado |
|---|---|---|
| I. Arquitetura Medalhão | Não cria dados; as regras de tabela refletem Bronze e Silver por fonte com prefixo de liga, e `dim_`/`fat_`/`agg_` na Gold | ✅ |
| II. Ingestão Idempotente | Fora do escopo; o deploy só publica definições, e Files e tabelas não são tocados | ✅ |
| III. Fabric Versionado no Git | Dev pela Git integration em `dev`; produção só a partir de `main` via PR, com publicação automática; `workspace/` não é editado (o deploy lê no lugar, com `parameter_file_path`); ruleset sem bypass, inclusive para administradores; agendamento só em produção | ✅ (ver nota 1) |
| IV. Padrão de Nomenclatura | Validador com as regras do [contrato](./contracts/naming-rules.md); "tipo sem regra" bloqueia; documento em `docs/` | ✅ |
| V. Qualidade Verificável | Sem tabelas Silver ou Gold nesta feature; o PR para `main` passa nas validações do Princípio III | ✅ (escopo) |
| VI. Segredos Fora do Código | Segredos só nos secrets do GitHub (repositório e Environment) e nos Files dos lakehouses; push protection, busca por valor exato e `gitleaks` em todo o histórico; repositório público tratado como tal | ✅ |
| VII. Custo Zero e Simplicidade | GitHub gratuito (repositório público), SP do Entra sem assinatura, `fabric-cicd` open source; um script por responsabilidade. O laboratório DP-600 é um componente a mais, sem necessidade de produção | ⚠️ justificado (Complexity Tracking) |

Nota 1: desde a constituição 2.1.1, o Princípio III diz explicitamente que `ws-prd-dpacademy` é
publicado a partir de `main`, sem Git integration conectada (research R1). Desde a 2.2.0, a
"aprovação" de PR é a conclusão com as validações verdes (research R6).

**Gate pré-pesquisa**: aprovado. **Gate pós-design** (contratos e modelo de dados): aprovado.
O laboratório DP-600, acrescentado depois, tem dois desvios justificados em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-naming-standard-cicd/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── naming-rules.md
│   ├── ci-pipelines.md
│   └── deploy-config.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks (ainda não criado)
```

### Source Code (repository root)

```text
workspace/                      # escrito só pela Git integration do ws-dev-dpacademy
.github/
├── workflows/
│   ├── pr-validation.yml       # nomes, testes, segredos
│   └── deploy-prd.yml          # fabric-cicd + agendamentos + relatório de tabelas
└── pull_request_template.md    # o que muda em cada camada
ci/
├── requirements.txt            # fabric-cicd, azure-identity (versões fixas)
├── validate_names.py           # regras de nomenclatura (contracts/naming-rules.md)
├── deploy.py                   # publicação em prd
├── environments.json           # IDs e nomes dos workspaces
├── parameter.yml               # troca de IDs dev → prd
└── schedules.json              # agendamentos de produção
tests/
└── unit/
    └── test_validate_names.py
docs/
├── padrao-nomenclatura.md      # FR-004
├── adr-002-cicd-fabric-cicd.md # decisão R1/R2, expiração do secret da SP
└── estudo-dp600.md             # anotações do laboratório e do setup, por tema da prova
README.md                       # atualizado: case NBA, nomes novos, fluxo CI/CD
```

**Structure Decision**: os itens do Fabric continuam em `workspace/`, escritos só pela Git
integration. Toda a automação fica fora de `workspace/`: os workflows e o template de PR em `.github/`, os
scripts e a configuração em `ci/`, e os testes em `tests/unit/`, que já é a pasta dos testes da
feature 001. Os IDs de workspace e de lakehouse não são segredos e ficam versionados; os
segredos ficam só nos secrets do GitHub.

## Ordem de entrega e dependência com a 001

1. Infraestrutura sem código: repositório público no GitHub, branches, secret scanning e os
   dois workspaces (research R0).
2. Laboratório DP-600, pela interface: papéis de workspace, Git integration e deployment
   pipeline dev → lab (research R12). Vem antes da SP e dos pipelines, para aprender o mecanismo
   nativo antes do automatizado.
3. SP, configurações de tenant, secrets e Environment do GitHub (research R2).
4. US1: `docs/padrao-nomenclatura.md`, `ci/validate_names.py` com testes e o `README.md`.
5. US2: `pr-validation`, ruleset de `main`, `deploy-prd` e a primeira publicação com
   `bronze_balldontlie` (quickstart §7).
6. Implementar a 001 em dev, a partir do plano e das tarefas regenerados na US1 (divisão em
   `nb-full-020`/`nb-incr-030`, liga como parâmetro, `environment` em `ctl_ingestion_runs`), e
   publicar.
7. US3: agendamento em produção e carga histórica em produção (quickstart §8). A carga
   histórica de produção precisa terminar antes de 2026-11-15 (SC-008 da 001).
8. Segunda parte do laboratório: auto-binding e regras de implantação com os notebooks da 001.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Terceiro workspace (`ws-lab-dpacademy`) e um deployment pipeline sem uso em produção (Princípio VII: "cada componente novo precisa de uma necessidade concreta"; Restrições: "mesmo par de workspaces") | Necessidade concreta de estudo: a DP-600 cobra deployment pipelines (estágios, regras, comparação, auto-binding) e Git integration, que o fluxo com `fabric-cicd` não exercita | Estudar só pela documentação não fixa o comportamento; usar deployment pipelines em produção trocaria "o que foi aprovado em `main`" por "o que estava em dev" (research R1) |
| `ws-lab-dpacademy` recebe mudanças fora de `ws-dev-dpacademy`, numa branch descartável `lab-git` editada pelo GitHub (Princípio III) | O exercício de conflito e de "Update" da Git integration exige uma mudança feita no repositório, fora do workspace | Fazer o exercício em `dev` violaria o Princípio III no ramo real; a branch `lab-git` é apagada e o Git do laboratório é desconectado ao fim do exercício |
