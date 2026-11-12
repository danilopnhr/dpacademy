# Estudo DP-600 no dpacademy

Diário de estudo para a certificação **Microsoft Certified: Fabric Analytics Engineer Associate
(DP-600)**, preenchido durante o setup e os laboratórios do projeto. Cada seção liga um passo
prático a um tema da prova.

Referências oficiais (confira sempre a versão mais recente do guia de estudo, que lista as
habilidades cobradas e muda com o tempo):

- Página da certificação: https://learn.microsoft.com/credentials/certifications/fabric-analytics-engineer-associate/
- Guia de estudo da DP-600: https://learn.microsoft.com/credentials/certifications/resources/study-guides/dp-600

## Como usar

1. Antes de cada passo, leia no guia de estudo a habilidade correspondente e faça o módulo do
   Microsoft Learn ligado a ela.
2. Faça o exercício no Fabric, pela interface.
3. Preencha a seção com o que fez, o que a prova cobra e o que surpreendeu.
4. Escreva **uma pergunta de prova** sua sobre o tema, com a resposta. Ao final, você terá um
   simulado feito por você.

Modelo de cada seção:

> **O que fiz**:
> **O que a prova cobra**:
> **O que me surpreendeu**:
> **Minha pergunta de prova** (com resposta):

---

## §1 Capacidade e configurações de tenant

Passos do projeto: conferir a capacidade Trial e ler o portal de administração (tarefa T004 e
research R2).

Para observar:

- onde fica a capacidade, como um workspace é atribuído a ela e o que acontece quando o Trial
  acaba;
- as configurações de tenant que habilitam Git integration, deployment pipelines e uso das APIs
  por service principals, e a restrição por grupo de segurança.

> **O que fiz** (2026-10-22): abri o Admin portal → Capacity settings → Trial. A capacidade fica em
> **Brazil South**, com **43 dias** restantes (fim em 2026-12-04). Em Tenant settings, conferi Git
> integration, uso das APIs por service principals e criação de itens do Fabric: as três estão
> habilitadas **para a organização inteira**. Não alterei nada.
>
> **O que a prova cobra**:
> - **Administrador do Fabric** (configurações de tenant) e **administrador de capacidade**
>   (capacidade e workspaces atribuídos a ela) são papéis diferentes.
> - Cada configuração de tenant pode valer para a organização inteira, só para grupos de
>   segurança ou para todos exceto alguns grupos. Algumas podem ser delegadas a administradores
>   de capacidade, domínio ou workspace.
> - Menor privilégio: uma configuração sensível, como o uso das APIs por service principals,
>   deve ficar restrita a um grupo. Aqui isso vira a restrição a `sg-dpacademy-cicd` na T014.
>
> **O que me surpreendeu**:
> **Minha pergunta de prova**:

> **Atualização (2026-10-23)**: a Git integration com **GitHub** tem uma configuração de tenant
> **própria**, separada da do Azure DevOps (algo como "usuários podem sincronizar itens do
> workspace com repositórios do GitHub"). Conferir se está habilitada antes da T005. Na prova,
> vale lembrar que o Fabric suporta os dois provedores e que cada um tem a sua chave no tenant.

## §2 Papéis de workspace e acesso a itens

Passos do projeto: tarefa T008 (usuário de teste `lab.dp600`).

Para observar:

| Ação | Admin | Member | Contributor | Viewer |
|---|---|---|---|---|
| Criar e editar itens | | | | |
| Compartilhar um item | | | | |
| Adicionar pessoas ao workspace | | | | |
| Ler dados pelo endpoint SQL | | | | |
| Conectar o workspace ao Git | | | | |
| Implantar num deployment pipeline | | | | |

Compare também o acesso pelo papel no workspace com o compartilhamento de um item só.

> **O que fiz**:
> **O que a prova cobra**:
> **O que me surpreendeu**:
> **Minha pergunta de prova**:

## §3 Workspaces do projeto

Passos do projeto: tarefas T004 e T005 (`ws-dev-dpacademy`, `ws-prd-dpacademy`).

Para observar: por que produção não tem Git integration neste projeto (ADR-002) e o que isso
muda em relação ao fluxo "um workspace por branch" que a documentação do Fabric apresenta.

> **O que fiz**:
> **O que a prova cobra**:
> **O que me surpreendeu**:
> **Minha pergunta de prova**:

## §4 Git integration (controle de versão do workspace)

Passos do projeto: tarefa T005 (`ws-dev-dpacademy` em `dev`) e laboratório T009 (branch
`lab-git`).

Para observar:

- commit, "Update" e o painel de controle de código;
- o que acontece num conflito e quais são as opções para resolvê-lo;
- o formato em que cada tipo de item é gravado no repositório (`.platform`, `notebook-content.py`,
  `pipeline-content.json`);
- o que **não** é versionado: dados das tabelas, Files, agendamentos, permissões;
- o que aparece quando um item é renomeado.

> **O que fiz**:
> **O que a prova cobra**:
> **O que me surpreendeu**:
> **Minha pergunta de prova**:

## §5 Deployment pipelines

Passos do projeto: laboratório T010 (`dpl-dpacademy-lab`, estágio "Laboratório") e T011
(auto-binding e regras com os notebooks da 001).

Para observar:

- criação do pipeline, número de estágios e atribuição de workspaces (um workspace só pode estar
  num pipeline);
- "Compare" entre estágios e implantação seletiva;
- **auto-binding**: o notebook implantado passa a apontar para o lakehouse do estágio de destino
  quando o lakehouse está no mesmo workspace;
- **regras de implantação**: quais tipos de item aceitam regra e o que cada regra troca;
- histórico de implantações e o que dá para fazer a partir dele.

> **O que fiz**:
> **O que a prova cobra**:
> **O que me surpreendeu**:
> **Minha pergunta de prova**:

## §6 Deployment pipelines × fabric-cicd

Passos do projeto: laboratório T012, depois do primeiro `deploy-prd` (T035).

| Aspecto | Deployment pipeline do Fabric | fabric-cicd (GitHub Actions) |
|---|---|---|
| De onde vem o que é implantado | | |
| Como troca IDs entre ambientes | | |
| Onde fica a configuração | | |
| Como se faz revisão antes de implantar | | |
| Como se volta atrás | | |
| Quando eu usaria | | |

> **O que me surpreendeu**:
> **Minha pergunta de prova**:

## §7 Próximos temas (features seguintes)

Temas da prova que aparecem nas próximas features do projeto, para preencher quando chegarem:

- **Silver e Gold**: lakehouse × warehouse, shortcuts, T-SQL no endpoint SQL, Delta (`OPTIMIZE`,
  V-Order), Dataflow Gen2.
- **Modelo semântico `sm-nba`**: Direct Lake (e quando cai para DirectQuery), star schema,
  relacionamentos, DAX (medidas, variáveis, grupos de cálculo, parâmetros de campo), RLS e OLS,
  desempenho (DAX Studio, Best Practice Analyzer).
- **Ciclo de vida do modelo**: projeto do Power BI Desktop (PBIP) no Git, endpoint XMLA, análise
  de impacto, ativos reutilizáveis (.pbit, .pbids, modelo semântico compartilhado).
- **Governança**: endosso (promovido, certificado), rótulos de confidencialidade.
