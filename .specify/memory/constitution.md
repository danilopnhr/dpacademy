# dpacademy Constitution

## Core Principles

### I. Arquitetura Medalhão

Todo dado percorre Bronze → Silver → Gold, sem pular camadas.

- **Bronze** (`bronze_camara`, `bronze_transparencia`): resposta da API gravada em Delta sem
  transformação de conteúdo, com os nomes de coluna da fonte (as-is) mais as colunas de
  auditoria `_ingested_at`, `_source_endpoint` e `_batch_id`. Bronze é append-only.
- **Silver** (`silver_camara`, `silver_transparencia`): uma tabela por entidade da fonte, com
  tipagem explícita, colunas renomeadas em `snake_case` em português, deduplicação por chave
  natural e carga incremental por `MERGE`. A Silver não usa `dim_` nem `fat_`.
- **Gold** (`gold_<case>`, no primeiro case `gold_gastos`): modelo dimensional (star schema)
  com dimensões `dim_`, fatos `fat_` e grão documentado em cada fato; tabelas agregadas usam
  `agg_`. A Gold é o único lugar onde as fontes se cruzam.
- Bronze e Silver são organizadas por **fonte** e compartilhadas entre os cases; a Gold é
  organizada por **case**, um lakehouse para cada.
- Consumo (modelo semântico e relatórios) lê exclusivamente da Gold.

Justificativa: separar dado bruto de dado tratado permite reprocessar qualquer camada sem
chamar a API de novo, e o star schema é o formato que o Direct Lake e a DP-600 esperam.

### II. Ingestão Idempotente

A ingestão de qualquer fonte MUST poder ser reexecutada para a mesma janela sem gerar
duplicidade nas camadas Silver e Gold.

- Toda carga é parametrizada por endpoint, por janela (data, mês ou ano) e pelo recorte que a
  fonte exigir (ex.: legislatura, deputado, órgão, município).
- A paginação é percorrida até o fim, por página ou por cursor conforme a fonte; uma página
  falha interrompe o lote inteiro.
- Respostas HTTP 429 e 5xx são tratadas com retry e backoff exponencial; o limite de
  requisições de cada fonte MUST ser respeitado.
- Cargas históricas (backfill) e diárias usam o mesmo código, mudando só os parâmetros. Quando a
  fonte publica arquivos em lote, o backfill MAY usá-los, desde que grave na mesma tabela
  Bronze com as mesmas colunas de auditoria.
- A ingestão é genérica por fonte: um endpoint ou recorte novo entra por configuração, sem
  notebook novo.

Justificativa: APIs públicas têm limite de requisições e instabilidade, e falhas parciais são
esperadas; reprocessar com segurança é mais barato do que corrigir duplicidade.

### III. Fabric Versionado no Git

O repositório é a fonte de verdade dos itens do Fabric.

- A pasta `workspace/` é escrita apenas pela Git integration do Fabric e MUST NOT ser editada à
  mão.
- Mudanças, inclusive as feitas por agentes via MCP, acontecem somente no workspace
  `ws-dev-dpacademy` (branch `dev`).
- O workspace `ws-prd-dpacademy` é publicado a partir da branch `main`, sem Git integration
  conectada, e recebe mudanças apenas por pull request de `dev` para `main`; gravação direta em
  `main` MUST ser bloqueada, inclusive para administradores do repositório.
- Com um engenheiro só, a aprovação de um pull request é a sua conclusão pelo engenheiro com
  todas as validações verdes, registrada como quem mesclou.
- Todo pull request MUST passar por validações automáticas de nomenclatura (Princípio IV) e de
  ausência de segredos (Princípio VI) antes de poder ser concluído.
- Concluído o pull request, a publicação em `ws-prd-dpacademy` MUST ser automática, sem cópia
  manual de itens, com as referências de ambiente apontando para produção.
- Cargas agendadas rodam apenas em produção; em desenvolvimento as cargas são manuais.

Justificativa: reproduz o fluxo de CI/CD de um time real e impede alterações sem revisão em
produção.

### IV. Padrão de Nomenclatura datasource.expert

Todo item MUST seguir o padrão datasource.expert (lado Microsoft):

- Workspace: `ws-ambiente-bi` (`ws-dev-dpacademy`, `ws-prd-dpacademy`).
- Lakehouse: `bronze_<fonte>`, `silver_<fonte>`, `gold_<case>`.
- Notebook: `nb-<mode>-<999>-<camada>-<fonte|case>-<assunto>`
  (ex.: `nb-full-020-bronze-camara-deputados`, `nb-incr-030-bronze-camara-despesas`,
  `nb-full-010-gold-gastos-dimensoes`). `mode` descreve como a tabela é carregada: `full` para
  cadastros recoletados inteiros, `incr` para dados coletados por janela, `util` para notebooks
  de biblioteca que não gravam tabelas e só são chamados por outros
  (`nb-util-010-bronze-transparencia-cliente`).
- Dataflow Gen2: `df-<mode>-<999>-<camada>-<fonte|case>-<assunto>`.
- Pipeline: `pl-<999>-<camada>-<fonte|case>-<assunto>` (ex.: `pl-010-bronze-camara-gastos`);
  a orquestração de todas as camadas de um case usa a camada `orq` (`pl-010-orq-gastos-diario`).
- Modelo semântico: `sm-<case>` (`sm-gastos`). Relatório: `rpt-<case>-<assunto>`
  (`rpt-gastos-parlamentares`). Sem sequencial.
- `999` é sequencial de três dígitos, de 10 em 10 (`010`, `020`...), único por tipo, camada e
  fonte ou case; recomeça em cada fonte ou case.
- Tabelas em `snake_case`. Na Bronze e na Silver, o nome é a entidade da fonte, sem prefixo,
  porque o lakehouse já identifica a fonte (`bronze_camara.despesas`,
  `silver_camara.despesas`); tabelas de controle usam `ctl_` e registram o endpoint e o recorte
  em colunas (`ctl_ingestion_runs`). Na Gold, `dim_`, `fat_` e `agg_`.
- Colunas: na Bronze, como a fonte devolve, mais as de auditoria iniciadas por `_`; na Silver e
  na Gold, `snake_case` em português (`data_documento`), chave substituta `sk_<entidade>` e id
  da fonte `codigo_<entidade>`.
- Itens do workspace em minúsculas com hífen; lakehouses, tabelas e colunas em `snake_case`;
  nomes sem acentos nem espaços.
- Um tipo de item sem regra acima tem a regra definida na feature que o cria e registrada em
  `docs/` antes de ser publicado.

Justificativa: nomes previsíveis tornam o workspace navegável, permitem a validação automática
no pull request e seguem um padrão de mercado reconhecível no portfólio.

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

A chave da API do Portal da Transparência e quaisquer outras credenciais MUST NOT aparecer no
repositório, em notebooks, em definições de pipeline ou em logs. A API da Câmara dos Deputados
não exige chave. O mecanismo de armazenamento do segredo é decidido no plano técnico da
primeira feature de ingestão que usar a chave, respeitando o Princípio VII.

Justificativa: o repositório é público, como portfólio, e o histórico do Git guarda tudo; um
segredo commitado precisa ser trocado, não só apagado.

### VII. Custo Zero e Simplicidade

O case MUST rodar apenas na capacidade Trial do Fabric e em planos gratuitos. Recursos pagos
(capacidade F, assinatura Azure paga) estão fora de escopo. Cada componente novo precisa de
uma necessidade concreta; a solução mais simples que atende à spec vence.

Justificativa: é um projeto pessoal de estudo para a DP-600, sem orçamento.

## Restrições de Plataforma e Stack

- Plataforma: Microsoft Fabric em tenant próprio, capacidade Trial (válida até cerca de
  2026-12-05).
- Fontes de dados: API de Dados Abertos da Câmara dos Deputados
  (`dadosabertos.camara.leg.br/api/v2`, sem chave) e API do Portal da Transparência do Governo
  Federal (`api.portaldatransparencia.gov.br/api-de-dados`, chave gratuita via gov.br), ambas
  públicas e gratuitas.
- Processamento: notebooks PySpark gravando em Delta; orquestração por Data Pipeline do
  Fabric.
- Consumo: modelo semântico em modo Direct Lake e relatório Power BI.
- Versionamento e CI/CD: Git integration do Fabric com GitHub (repositório público `dpacademy`),
  GitHub Actions para validação e publicação, e GitHub Issues para o backlog.
- Organização dos cases: todos os cases vivem no mesmo par de workspaces. O primeiro é
  `gastos` (cota parlamentar, emendas e contratos com fornecedores). Cases futuros MAY
  reaproveitar as fontes existentes ou trazer outras, cada fonte nova com seu par
  `bronze_<fonte>`/`silver_<fonte>`. Cada case tem seu lakehouse Gold, sua orquestração diária,
  seu modelo semântico, seus relatórios, um épico nas Issues do GitHub e as próprias features do
  Spec Kit. Separar um case em workspace próprio exige justificativa (acesso, capacidade ou
  cadência de deploy próprios) no plano da feature.
- Documentação, specs e textos do portfólio em português do Brasil. Páginas e relatórios do
  portfólio seguem o design system dpacademy
  (https://claude.ai/artifact/RLhQvxQPtgoSPTMonjbGcP).

## Fluxo de Desenvolvimento

- Toda feature segue o fluxo do Spec Kit: `/speckit-specify` → `/speckit-plan` →
  `/speckit-tasks` → `/speckit-implement`.
- Cada feature nasce de uma issue do backlog no GitHub e é entregue em branch própria a partir
  de `dev`.
- O pull request para `main` MUST descrever o que muda em cada camada e passar nas
  verificações de qualidade do Princípio V e nas validações do Princípio III.
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

**Version**: 3.0.0 | **Ratified**: 2026-10-22 | **Last Amended**: 2026-11-12
