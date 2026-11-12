# Research: Padrão de nomenclatura e CI/CD do dpacademy

**Feature**: [spec.md](./spec.md) | **Date**: 2026-10-22 (revisado em 2026-10-23: Azure DevOps →
GitHub, ver R0)

## R0. Plataforma de repositório e CI/CD

- **Decision**: GitHub, com o repositório **público** `dpacademy`, GitHub Actions para validação e
  publicação, e GitHub Issues para o backlog.
- **Rationale**: em 2026-10-23, ao criar a organização, o Azure DevOps exigiu vincular uma
  assinatura Azure para cobrança, o que o Princípio VII não permite. No GitHub, um repositório
  público tem, no plano gratuito:
  - GitHub Actions sem limite de minutos;
  - rulesets de branch (FR-007);
  - secret scanning com push protection.
  A Git integration do Fabric suporta GitHub, e o `fabric-cicd` é indiferente à plataforma de CI.
- **Alternatives considered**:
  - *Azure DevOps com assinatura pay-as-you-go*: custo esperado zero, mas exige cartão e
    contraria o Princípio VII.
  - *Azure DevOps com a conta gratuita do Azure*: é desativada em 30 dias, antes do fim do Trial
    do Fabric.
  - *GitHub privado gratuito*: sem proteção de branch, então o FR-007 não seria garantido.

## R1. Mecanismo de publicação em produção

- **Decision**: publicação "build-based" com a biblioteca open source `fabric-cicd` (Microsoft),
  rodando num workflow do GitHub Actions disparado por push em `main`. O `ws-dev-dpacademy`
  fica conectado à branch `dev` pela Git integration; o `ws-prd-dpacademy` **não** é conectado ao
  Git: ele recebe tudo pelo `fabric-cicd`, a partir do conteúdo de `main`.
- **Rationale**:
  - O repositório continua sendo a fonte de verdade (Princípio III), e o que vai para produção é
    exatamente o que foi aprovado no PR.
  - `fabric-cicd` troca os IDs específicos de ambiente (lakehouse padrão dos notebooks, workspace
    das atividades de pipeline) por meio de `parameter.yml` e resolve sozinho as referências
    entre itens do repositório (FR-009).
  - `unpublish_all_orphan_items` remove de produção os itens que saíram do repositório, o que
    cobre o edge case do item renomeado (sem cópia órfã).
  - Cada publicação republica todos os itens no escopo, então uma alteração feita à mão em
    produção é sobrescrita na publicação seguinte (edge case de divergência).
  - Gratuito (Princípio VII): biblioteca Python e GitHub Actions em repositório público.
- **Alternatives considered**:
  - *Git integration nos dois workspaces* (`ws-prd` conectado a `main`): depois do merge, alguém
    ou algum script tem de chamar "Update from Git", e os notebooks continuam apontando para o
    lakehouse de dev, porque o ID do lakehouse padrão fica gravado no conteúdo. A Variable
    Library contorna parte disso, mas não troca o lakehouse padrão.
  - *Deployment pipelines do Fabric*: fazem a troca automática do lakehouse padrão (auto-binding)
    e têm regras de deploy, mas produção passa a ser "o que estava em dev", não "o que foi
    aprovado em `main`". Disparar após o PR exige a mesma chamada de API pelo GitHub Actions, e
    a configuração fica na interface, fora do Git.

## R2. Autenticação do GitHub Actions no Fabric

- **Decision**: uma *service principal* (registro de aplicativo no Entra ID do tenant),
  `sp-dpacademy-cicd`, com papel **Admin** só no `ws-prd-dpacademy`.
  - O client secret fica como **secret do Environment** `ws-prd-dpacademy` do GitHub, liberado só
    para `main`. O ID do tenant e o da SP ficam como variáveis do mesmo Environment.
  - O secret chega ao `fabric-cicd` por `ClientSecretCredential` (`azure-identity`).
  - Um secret de Environment só é entregue a jobs que declaram esse Environment, e só a partir
    das branches permitidas. O workflow de PR nunca vê a credencial da SP.
- **Rationale**: registrar aplicativo no Entra ID não exige assinatura Azure; o tenant roda sem
  assinatura (Princípio VII). As configurações de tenant do Fabric que liberam o uso das APIs
  por service principal precisam ser ativadas, restritas a um grupo de segurança que contém só
  essa SP.
- **Risco aceito**: o client secret expira (no máximo 24 meses); a data de expiração vai para o
  [docs/adr-002-cicd-fabric-cicd.md](../../docs/adr-002-cicd-fabric-cicd.md).
- **Alternatives considered**:
  - token do próprio usuário no workflow (expira em horas e mistura identidade pessoal com
    automação);
  - identidade gerenciada (exige recurso Azure pago);
  - login OIDC com credencial federada do GitHub na SP. Elimina o secret e não exige assinatura,
    mas acrescenta configuração. Fica como melhoria futura no ADR-002.

## R3. Executores do GitHub Actions

- **Decision**: executores hospedados pelo GitHub (`ubuntu-latest`).
- **Rationale**: em repositório público, os minutos são ilimitados e não há concessão de
  paralelismo a pedir.
- **Alternatives considered**: executor self-hosted (desnecessário e, em repositório público,
  arriscado, porque PRs de forks poderiam rodar código na máquina do engenheiro).

## R4. Validação dos nomes no PR

- **Decision**: um script Python `ci/validate_names.py` lê `workspace/**/.platform` (campos
  `metadata.type` e `metadata.displayName`), aplica a expressão regular do tipo descrita em
  [contracts/naming-rules.md](./contracts/naming-rules.md) e falha com a lista de violações
  (item, tipo, regra). Também confere que o sequencial é único por tipo, camada e fonte ou case.
  Um tipo de item sem regra **bloqueia** o PR com a mensagem "tipo sem regra" (Princípio IV:
  a regra precisa existir antes da publicação).
- **Rationale**: o `.platform` é o único lugar versionado com o nome de exibição e o tipo de cada
  item; o nome da pasta pode divergir do nome de exibição. Python puro, sem dependências, e
  testável localmente com `pytest`.
- **Limite conhecido**: nomes de **tabelas** e **colunas** não estão no Git (são criados em tempo
  de execução, às vezes com nome dinâmico, como `f"{liga}_{recurso}"`). Eles são verificados
  depois de cada publicação pelo relatório de tabelas (R7), sem bloquear o PR.
- **Alternatives considered**: varrer o código dos notebooks em busca de `saveAsTable` e
  `CREATE TABLE` (frágil com nomes dinâmicos); regras em YAML (dependência a mais para ~10
  expressões).

## R5. Validação de segredos no PR

- **Decision**: três camadas.
  1. **Push protection do GitHub**: bloqueia o push quando reconhece uma credencial de formato
     conhecido, antes de ela entrar no repositório.
  2. **Valor conhecido, no PR**: a chave da balldontlie fica como repository secret
     `BDL_NBA_API_KEY`. O workflow procura o valor, como texto exato, em todo o histórico
     (`git grep -F` sobre `git rev-list --all`). Qualquer ocorrência bloqueia o PR, sem imprimir o
     valor.
  3. **Padrões genéricos, no PR**: `gitleaks` (binário open source com versão fixa) sobre o
     histórico completo, com as regras padrão.
- **Rationale**:
  - A chave da balldontlie não tem formato distinguível, e os itens do Fabric estão cheios de
    GUIDs. Uma regra por formato daria falso positivo; a busca pelo valor exato tem zero falso
    positivo e cobre o histórico (edge case).
  - O client secret da SP **não** entra na busca por valor. Ele vive só no Environment de
    produção, e levá-lo ao workflow de PR aumentaria a exposição. Client secrets do Entra ID têm
    formato conhecido e são cobertos pelo push protection e pelo `gitleaks`.
- **Alternatives considered**: só `gitleaks` (não reconhece a chave da balldontlie);
  `detect-secrets` (exige manter um baseline).

## R6. Regras do ramo `main`

- **Decision**: um ruleset `main-protegida` em `main`, com enforcement ativo e bypass list vazia
  (vale também para administradores):
  - exigir pull request, com **0** aprovações obrigatórias;
  - exigir o status check `pr-validation`, com a branch atualizada antes do merge;
  - bloquear force push e exclusão da branch.
  Nas configurações do repositório, só o merge do tipo squash fica permitido, para cada PR virar
  um commit em `main` (a "versão publicada").
- **Rationale**: atende FR-007 e FR-008.
  - O GitHub não permite que o autor aprove o próprio PR. Com um engenheiro só, exigir uma
    aprovação travaria todo merge.
  - A "aprovação" passa a ser a conclusão do PR com o status check verde, registrada como quem
    mesclou (constituição 2.2.0, Princípio III).
  - "Branch atualizada" garante que cada PR seja validado contra o estado atual de `main` (edge
    case de dois PRs).
- **Alternatives considered**: exigir 1 aprovação com um segundo usuário só para aprovar (uma
  identidade a mais, sem revisão real); branch protection rules clássicas (rulesets são o
  mecanismo atual e deixam explícita a bypass list).

## R7. Workflow de publicação, concorrência e registro

- **Decision**: o workflow `deploy-prd` dispara a cada push em `main` com mudança em
  `workspace/`, `ci/` ou no próprio workflow. Ele usa o grupo de concorrência `deploy-prd`, sem
  cancelar o run em andamento, e roda no Environment `ws-prd-dpacademy` do GitHub. Etapas:
  1. aponta o `fabric-cicd` para `workspace/` e passa o `ci/parameter.yml` por
     `parameter_file_path` (suportado a partir da versão fixada, 1.4.0);
  2. roda `fabric-cicd` (`publish_all_items` e depois `unpublish_all_orphan_items`) para os tipos
     no escopo;
  3. aplica os agendamentos de `ci/schedules.json` em produção (R8);
  4. gera o relatório de tabelas: lista as tabelas dos lakehouses de produção pela API e as
     confere contra as regras de tabela; divergências viram aviso no resumo do run.
- **Rationale**:
  - Com `parameter_file_path`, o `parameter.yml` fica em `ci/` e nada é escrito em `workspace/`,
    que é exclusivo da Git integration (Princípio III). A ideia inicial, uma cópia temporária de
    `workspace/` com o arquivo na raiz, ficou desnecessária e foi descartada na implementação.
  - O grupo de concorrência garante uma publicação por vez. Se vários pushes chegarem durante um
    run, só o mais recente fica na fila, e a publicação seguinte sempre reflete o `main` mais
    recente (edge case de dois PRs).
  - A página do Environment registra cada publicação: commit (versão), horário e resultado. O
    commit leva ao PR, que guarda quem mesclou (FR-011).
- **Risco aceito (atomicidade)**: o `fabric-cicd` publica item por item, então uma falha no meio
  deixa produção parcialmente atualizada. Mitigações: o run fica vermelho, o GitHub envia e-mail,
  e a volta à última versão boa é usar "Re-run all jobs" no último run verde, que publica de novo
  aquele commit (ou um revert em `main`). O edge case da spec ("produção continua na última versão aprovada") é atendido por
  convergência, não por transação.
- **Alternatives considered**: deploy só dos itens alterados (mais rápido, mas não sobrescreve
  divergências feitas à mão em produção).

## R8. Agendamento só em produção (FR-012)

- **Decision**: agendamentos não fazem parte da definição dos itens no Git, então ficam em
  `ci/schedules.json` (item, tipo de job, horário, fuso `E. South America Standard Time`). O
  `deploy-prd` cria ou atualiza o agendamento em produção pela API de agendamento de jobs do
  Fabric, de forma idempotente. Em `ws-dev-dpacademy` não se cria agendamento, e o quickstart
  confere isso pela mesma API.
- **Rationale**: sem passo manual em produção, e o horário fica versionado e revisado no PR como
  qualquer outra mudança.
- **Verificado na implementação (fabric-cicd 1.4.0)**: a biblioteca não publica agendamentos, então
  a etapa própria do `deploy.py` continua necessária.
- **Alternatives considered**: agendar à mão em produção uma vez (fere "nenhuma alteração direta",
  SC-003); agendar dentro de uma orquestração que checa o ambiente (roda em dev também).

## R9. Ambiente no registro de execuções (FR-013)

- **Decision**: o notebook lê o nome do workspace atual no contexto de execução e extrai o
  ambiente do padrão `ws-<ambiente>-dpacademy` (`dev` ou `prd`). A feature 001 grava esse valor
  em `ctl_ingestion_runs.environment`.
- **Rationale**: nenhum parâmetro ou variável precisa ser trocado na publicação; o nome do
  workspace já obedece ao padrão.
- **Alternatives considered**: Variable Library com um conjunto de valores por ambiente (mais um
  item para manter, com o mesmo resultado).

## R10. Chave da fonte em produção

- **Decision**: mantém-se a decisão R5 da feature 001 (arquivo na área Files do lakehouse), com
  um arquivo por liga, `Files/_secrets/balldontlie_<liga>_api_key`, enviado uma vez ao
  `bronze_balldontlie` de cada ambiente.
- **Rationale**: Files e tabelas são dados, não itens; não passam pelo Git nem pelo
  `fabric-cicd`. O envio do segredo a produção é o único passo manual do ambiente, e não altera
  item nenhum.
- **Alternatives considered**: o workflow de deploy gravar o arquivo a partir de um secret do GitHub
  (mais um caminho por onde o segredo trafega, sem ganho para um único engenheiro).

## R12. Laboratório DP-600

- **Decision**: um workspace `ws-lab-dpacademy` e um deployment pipeline do Fabric
  `dpl-dpacademy-lab`, com os estágios "Desenvolvimento" (`ws-dev-dpacademy`) e "Laboratório"
  (`ws-lab-dpacademy`), feitos à mão pela interface e documentados em `docs/estudo-dp600.md`.
  O laboratório nunca publica em `ws-prd-dpacademy`. Os notebooks não rodam nele, porque não há
  chave da fonte. O exercício de Git integration usa uma branch descartável `lab-git`, e o
  workspace é desconectado do Git antes de virar estágio do deployment pipeline.
- **Rationale**: a DP-600 cobra o ciclo de vida pelos mecanismos nativos do Fabric (Git
  integration, deployment pipelines com regras e comparação), e não pelo `fabric-cicd`. Praticar
  os dois lado a lado dá ao engenheiro o cenário "quando usar cada um", típico da prova.
  - Um workspace só pode estar num deployment pipeline. Como produção não usa deployment
    pipeline, `ws-dev-dpacademy` fica livre para o laboratório.
  - Um workspace com Git integration pode ser estágio de deployment pipeline. Por isso, dev
    continua conectado a `dev`.
- **Alternatives considered**: deployment pipeline dev → prd (rejeitado em R1); estudar só pela
  documentação (não exercita regras nem auto-binding); um segundo tenant de estudo (mais
  identidades e capacidades a manter).

## R11. Documentação do padrão (FR-004) e limpeza dos nomes antigos (FR-005, SC-002)

- **Decision**: o padrão fica em `docs/padrao-nomenclatura.md`, com as três camadas, as regras
  gerais, um exemplo por tipo e a referência às expressões regulares de
  [contracts/naming-rules.md](./contracts/naming-rules.md). O `README.md` deixa de citar o case
  Olist e os nomes antigos. Os artefatos da 001 já foram renomeados na emenda 2.1.0; falta
  regenerar o plano e as tarefas dela, que é trabalho da própria 001.
- **Rationale**: um único documento de referência para pessoas e validador.
- **Alternatives considered**: deixar o padrão só na constituição (é longo demais para ela e muda
  com mais frequência).
