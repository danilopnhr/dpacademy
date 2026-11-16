# ADR-002: Publicação em produção com fabric-cicd pelo GitHub Actions

- **Status**: aceita (revisada em 2026-10-23: Azure DevOps → GitHub)
- **Data**: 2026-10-22
- **Feature**: [002-naming-standard-cicd](../specs/002-naming-standard-cicd/plan.md)

## Contexto

O dpacademy precisa levar mudanças de `ws-dev-dpacademy` para `ws-prd-dpacademy` sempre por pull
request validado, de forma automática e sem custo (constituição, Princípios III e VII). Os
notebooks guardam no próprio conteúdo o ID do lakehouse padrão e do workspace. Por isso, copiar
um item de dev para prd deixaria a produção gravando no lakehouse de dev.

A primeira versão desta decisão usava Azure DevOps. Ao criar a organização, em 2026-10-23, o
Azure DevOps exigiu vincular uma assinatura Azure para cobrança, o que o Princípio VII não
permite. A plataforma passou a ser o GitHub, com repositório público.

## Decisão

- **Repositório:** `dpacademy` no GitHub, **público**.
  - Num repositório público, o GitHub Actions não tem limite de minutos e os rulesets de branch
    funcionam no plano gratuito.
  - Em repositório público, o secret scanning com push protection também é gratuito.
- **Desenvolvimento:** `ws-dev-dpacademy` fica conectado à branch `dev` pela Git integration,
  pasta `workspace/`, autenticada por um token de acesso pessoal *fine-grained* do GitHub,
  restrito a este repositório.
- **Produção:** `ws-prd-dpacademy` **não** é conectado ao Git. Ele é publicado a partir de `main`
  pelo workflow `deploy-prd`, que roda `ci/deploy.py` com o `fabric-cicd` (versão fixa em
  `ci/requirements.txt`). O script:
  - troca os IDs de dev pelos de produção com `ci/parameter.yml`, passado por
    `parameter_file_path`, sem escrever em `workspace/`;
  - publica todos os itens no escopo e remove os órfãos;
  - aplica os agendamentos de `ci/schedules.json`, porque o `fabric-cicd` não publica
    agendamentos;
  - gera um relatório dos nomes de tabela.
- **Autenticação:** o workflow usa a service principal `sp-dpacademy-cicd`, registrada no Entra ID
  (gratuito, sem assinatura Azure).
  - Ela tem papel Admin só em `ws-prd-dpacademy`.
  - O client secret fica como secret do **Environment** `ws-prd-dpacademy` do GitHub, liberado
    apenas para a branch `main`. O ID do tenant e o da SP ficam como variáveis desse Environment.
- **Validação:** todo PR para `main` passa pelo workflow `pr-validation`, status check obrigatório
  do ruleset de `main`. Ele roda:
  - o validador de nomes;
  - os testes;
  - a busca pelo valor exato da chave da balldontlie em todo o histórico;
  - o `gitleaks`.
- **Aprovação:** o GitHub não deixa o autor aprovar o próprio PR. Num projeto de um engenheiro só,
  o ruleset exige PR e status check verde, com zero aprovações. A "aprovação" é a conclusão do
  PR, registrada como quem mesclou (constituição, Princípio III).

## Alternativas rejeitadas

- **Azure DevOps.** Exige assinatura Azure vinculada para criar a organização desde 2026-10. Uma
  assinatura pay-as-you-go teria custo esperado zero, mas exige cartão de crédito e contraria o
  Princípio VII. A conta gratuita do Azure é desativada em 30 dias, antes do fim do Trial do
  Fabric.
- **GitHub com repositório privado gratuito.** Não tem proteção de branch, então o push direto em
  `main` não seria bloqueado (FR-007). O GitHub Pro resolveria, mas é pago.
- **Git integration nos dois workspaces**, com `ws-prd-dpacademy` conectado a `main`. Depois do
  merge, alguém teria de rodar "Update from Git", e os notebooks continuariam apontando para o
  lakehouse de dev.
- **Deployment pipelines do Fabric em produção.** Fazem a troca automática do lakehouse
  (auto-binding), mas produção passa a ser "o que estava em dev", e não "o que foi aprovado em
  `main`". Eles são praticados no laboratório DP-600 (`dpl-dpacademy-lab`, research R12).
- **Login OIDC (workload identity federation) entre GitHub e Entra ID.** Eliminaria o client
  secret, mas acrescenta configuração de credencial federada. Fica como melhoria futura,
  registrada abaixo.

## Consequências

- O que vai para produção é exatamente o conteúdo de `main`. Uma alteração feita à mão em
  produção é sobrescrita na publicação seguinte, porque o deploy republica todos os itens.
- Renomear um item não deixa cópia órfã, porque `unpublish_all_orphan_items` remove de produção o
  que saiu do repositório.
- O repositório é público. Nada de segredo vai para ele (Princípio VI), e os IDs de workspace e
  lakehouse que aparecem em `ci/` não são segredos.
- **Risco aceito: a publicação não é atômica.** O `fabric-cicd` publica item por item, então uma
  falha no meio pode deixar produção parcialmente atualizada. O run fica vermelho e o GitHub avisa
  por e-mail. Para voltar à última versão boa, há dois caminhos:
  1. abrir o último run verde do `deploy-prd` e usar **"Re-run all jobs"**, que publica de novo
     aquele mesmo commit;
  2. ou reverter o commit em `main` por PR, o que dispara uma nova publicação.
- O segredo da fonte em produção (`Files/_secrets/balldontlie_nba_api_key`) é enviado uma vez, à
  mão. Arquivos e tabelas são dados, não itens, e não passam pelo Git nem pelo `fabric-cicd`.
- **Melhoria futura:** trocar o client secret por login OIDC com credencial federada no
  `sp-dpacademy-cicd`. Assim, não há secret a renovar.

## Configuração do ambiente

Preencher conforme as tarefas de setup forem concluídas. Nada aqui é segredo.

| Item | Valor |
|---|---|
| Repositório GitHub | https://github.com/danilopnhr/dpacademy (público, só squash merge, branch apagada após merge; criado em 2026-11-12) |
| Secret scanning e push protection | ativos desde 2026-11-12 |
| Token fine-grained do Fabric (só a **expiração**) | 2027-02-10 (90 dias, criado em 2026-11-12; conta `github-dpacademy` no Fabric) |
| App ID da `sp-dpacademy-cicd` | _a preencher (T013)_ |
| Grupo `sg-dpacademy-cicd` | _a preencher (T013)_ |
| **Expiração do client secret** | _a preencher (T013)_ |
| Configurações de tenant do Fabric ativadas | _a preencher (T014)_ |
| Ruleset de `main` | _a preencher (T027)_ |

## Renovar credenciais

**Client secret da SP:**
1. No Entra ID, em `sp-dpacademy-cicd` → Certificates & secrets, crie um secret novo antes da
   expiração.
2. Atualize `SP_CLIENT_SECRET` no Environment `ws-prd-dpacademy` (GitHub → Settings →
   Environments).
3. Rode o `deploy-prd` uma vez para confirmar e apague o secret antigo.
4. Atualize a data de expiração na tabela acima.

**Token fine-grained da Git integration:** gere um novo no GitHub com as mesmas permissões e
atualize a conexão Git do `ws-dev-dpacademy` no Fabric (Workspace settings → Git integration).
