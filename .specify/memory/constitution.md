# dpacademy Constitution

## Core Principles

### I. Arquitetura Medalhão

Todo dado percorre Bronze → Silver → Gold, sem pular camadas.

- **Bronze** (`lh_bronze`): resposta da API gravada em Delta sem transformação de conteúdo, com
  colunas de auditoria `_ingested_at`, `_source_endpoint` e `_batch_id`. Bronze é append-only.
- **Silver** (`lh_silver`): tipagem explícita, nomes de coluna em `snake_case`, deduplicação por
  chave natural e carga incremental por `MERGE`.
- **Gold** (`lh_gold`): modelo dimensional (star schema) com grão documentado em cada fato.
- Consumo (modelo semântico e relatórios) lê exclusivamente da Gold.

Justificativa: separar dado bruto de dado tratado permite reprocessar qualquer camada sem
chamar a API de novo, e o star schema é o formato que o Direct Lake e a DP-600 esperam.

### II. Ingestão Idempotente

A ingestão da API balldontlie MUST poder ser reexecutada para a mesma janela sem gerar
duplicidade nas camadas Silver e Gold.

- Toda carga é parametrizada por janela (data ou temporada) e por endpoint.
- Paginação por cursor é percorrida até o fim; uma página falha interrompe o lote inteiro.
- Respostas HTTP 429 e 5xx são tratadas com retry e backoff exponencial; o limite de requisições
  do plano gratuito MUST ser respeitado.
- Cargas históricas (backfill) e diárias usam o mesmo código, mudando só os parâmetros.

Justificativa: o plano gratuito da API tem limite de requisições, e falhas parciais são
esperadas; reprocessar com segurança é mais barato do que corrigir duplicidade.

### III. Fabric Versionado no Git

O repositório é a fonte de verdade dos itens do Fabric.

- A pasta `workspace/` é escrita apenas pela Git integration do Fabric e MUST NOT ser editada à
  mão.
- Mudanças, inclusive as feitas por agentes via MCP, acontecem somente no workspace
  `dpacademy-dev` (branch `dev`).
- O workspace `dpacademy-prod` (branch `main`) recebe mudanças apenas por pull request de `dev`
  para `main`.

Justificativa: reproduz o fluxo de CI/CD de um time real e impede alterações sem revisão em
produção.

### IV. Convenção de Nomes

Todo item do Fabric MUST usar o prefixo do seu tipo: `lh_` (lakehouse), `nb_` (notebook),
`pl_` (pipeline), `sm_` (modelo semântico), `rpt_` (relatório). Tabelas usam `snake_case`;
dimensões começam com `dim_` e fatos com `fato_`. Nomes não usam acentos nem espaços.

Justificativa: nomes previsíveis tornam o workspace navegável e permitem automação por padrão
de nome.

### V. Qualidade de Dados Verificável

Toda tabela Silver e Gold MUST ter verificações automáticas executadas no pipeline:

- unicidade da chave primária ou da chave natural;
- colunas obrigatórias sem nulos;
- integridade referencial entre fatos e dimensões na Gold;
- contagem de linhas registrada por execução.

Uma verificação que falha MUST interromper o pipeline antes da camada seguinte ser
atualizada.

Justificativa: num portfólio, um número errado no relatório invalida o case inteiro.

### VI. Segredos Fora do Código

A chave da API balldontlie e quaisquer credenciais MUST NOT aparecer no repositório, em
notebooks, em definições de pipeline ou em logs. O mecanismo de armazenamento do segredo é
decidido no plano técnico da primeira feature de ingestão, respeitando o Princípio VII.

Justificativa: o repositório é privado, mas o código pode ser mostrado como portfólio e o
histórico do Git guarda tudo; um segredo commitado precisa ser trocado, não só apagado.

### VII. Custo Zero e Simplicidade

O case MUST rodar apenas na capacidade Trial do Fabric e em planos gratuitos. Recursos pagos
(capacidade F, assinatura Azure paga) estão fora de escopo. Cada componente novo precisa de
uma necessidade concreta; a solução mais simples que atende à spec vence.

Justificativa: é um projeto pessoal de estudo para a DP-600, sem orçamento.

## Restrições de Plataforma e Stack

- Plataforma: Microsoft Fabric em tenant próprio, capacidade Trial (válida até cerca de
  2026-12-05).
- Fonte de dados: API balldontlie (NBA), plano gratuito.
- Processamento: notebooks PySpark gravando em Delta; orquestração por Data Pipeline do
  Fabric.
- Consumo: modelo semântico em modo Direct Lake e relatório Power BI.
- Versionamento e CI/CD: Git integration do Fabric com Azure DevOps (Repos e Boards).
- Documentação, specs e textos do portfólio em português do Brasil. Páginas e relatórios do
  portfólio seguem o design system dpacademy
  (https://claude.ai/artifact/RLhQvxQPtgoSPTMonjbGcP).

## Fluxo de Desenvolvimento

- Toda feature segue o fluxo do Spec Kit: `/speckit-specify` → `/speckit-plan` →
  `/speckit-tasks` → `/speckit-implement`.
- Cada feature nasce de um item do backlog no Azure Boards e é entregue em branch própria a
  partir de `dev`.
- O pull request para `main` MUST descrever o que muda em cada camada e passar nas
  verificações de qualidade do Princípio V.
- Decisões de arquitetura relevantes são registradas em `docs/`.

## Governance

Esta constituição prevalece sobre outras práticas do projeto. Specs, planos e tarefas MUST
estar de acordo com ela; qualquer desvio precisa ser justificado no plano da feature, na seção
de verificação da constituição.

- Emendas são feitas via `/speckit-constitution`, com o Sync Impact Report revisado antes do
  commit.
- Versionamento semântico: MAJOR para remover ou redefinir um princípio; MINOR para adicionar
  princípio ou seção; PATCH para esclarecimentos de texto.
- Todo pull request para `main` verifica conformidade com os princípios.

**Version**: 1.0.1 | **Ratified**: 2026-10-22 | **Last Amended**: 2026-10-22
