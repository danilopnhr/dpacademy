# Feature Specification: Camada Gold e modelo semântico do case gastos

**Feature Branch**: `005-gastos-gold`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Camada Gold do case gastos: lakehouse `gold_gastos` com o modelo
dimensional (star schema) que cruza as despesas da cota parlamentar, os fornecedores e as emendas
parlamentares, com grão documentado em cada fato, verificações de qualidade do Princípio V
(inclusive integridade referencial) e atualização diária no orquestrador existente, depois da
Silver, mais o modelo semântico `sm-gastos` em Direct Lake sobre a Gold, conforme a constituição
v3.0.0. Esclarecimentos de 2026-11-18: escopo Gold + `sm-gastos` (relatório fica para a feature
seguinte); CPF de fornecedor pessoa física mascarado."

## User Scenarios & Testing *(mandatory)*

O ator principal é o analista que vai construir o relatório `rpt-gastos-parlamentares` (feature
seguinte) sobre o modelo semântico `sm-gastos` desta feature, e que precisa encontrar na Gold
tabelas prontas para análise e no modelo as medidas já definidas: fatos com grão claro, dimensões com descrição legível e nenhum valor perdido
no cruzamento entre as fontes. O engenheiro de dados (dono do case) opera as cargas e responde
pela qualidade.

Perguntas que a Gold precisa responder sem transformação adicional no consumo:

- Quanto cada deputado, partido e UF gastou da cota, por mês, por tipo de despesa?
- Quais fornecedores mais receberam da cota, e quais deles têm sanção ou relação com o governo
  federal segundo o Portal da Transparência?
- Quanto cada deputado destinou em emendas individuais, para quais funções e localidades, e como
  isso se compara ao seu gasto da cota?

### User Story 1 - Gasto da cota por deputado, partido, UF, tipo e mês (Priority: P1)

O analista consulta um fato de despesas com uma linha por despesa publicada e o associa a
dimensões de deputado, partido, UF, tipo de despesa, fornecedor e calendário. Somando o valor
líquido por qualquer combinação dessas dimensões, chega exatamente aos mesmos totais da Silver.
As despesas de liderança aparecem num membro próprio da dimensão de deputado, e o partido e a UF
de cada despesa são os que a Câmara publicou na linha da despesa, não os atuais do deputado.

**Why this priority**: a cota parlamentar é o centro do case e a pergunta principal do relatório.
Sozinha, já forma um modelo semântico demonstrável.

**Independent Test**: carregar a Gold de despesas e conferir, para cada ano de 2019 a 2026, a
quantidade de linhas e a soma do valor líquido contra a Silver; conferir que toda linha do fato
encontra seu membro em cada dimensão.

**Acceptance Scenarios**:

1. **Given** a Silver de despesas carregada, **When** a Gold roda, **Then** o fato tem, por ano,
   a mesma quantidade de linhas e a mesma soma de valor líquido da Silver.
2. **Given** despesas de liderança (sem deputado), **When** a Gold roda, **Then** elas ficam
   associadas a um membro identificado como liderança, com o nome da liderança publicado.
3. **Given** um deputado que trocou de partido no período, **When** o analista soma o gasto por
   partido, **Then** cada despesa conta para o partido publicado na linha daquela despesa.
4. **Given** um deputado presente nas despesas mas ausente do cadastro de deputados (suplente ou
   legislatura anterior), **When** a Gold roda, **Then** ele existe na dimensão de deputado com o
   nome publicado nas despesas e as demais informações de cadastro vazias.
5. **Given** despesas sem data de emissão (cerca de 3%), **When** a Gold roda, **Then** a despesa
   continua associada ao calendário pelo mês de competência.

---

### User Story 2 - Fornecedores da cota com o perfil do Portal da Transparência (Priority: P2)

O analista vê, para cada fornecedor da cota, o nome, o documento e, quando é empresa consultada no
Portal, a razão social e os indicadores de relação com o governo federal (sanções, contratos,
convênios, licitações, renúncia fiscal). Fornecedores ainda não consultados ou não encontrados no
Portal aparecem com essa situação explícita, para que o relatório não confunda "sem sanção" com
"não consultado".

**Why this priority**: é o primeiro cruzamento entre as duas fontes e o diferencial do case, mas
depende do fato de despesas.

**Independent Test**: conferir que todo fornecedor do fato de despesas existe na dimensão de
fornecedor, com uma situação de consulta ao Portal (encontrado, não encontrado ou não consultado),
e que a soma por situação bate com a Silver.

**Acceptance Scenarios**:

1. **Given** um CNPJ encontrado no Portal, **When** a Gold roda, **Then** o fornecedor tem a razão
   social e os indicadores do Portal, e a situação "encontrado".
2. **Given** um CNPJ ainda na fila de consulta, **When** a Gold roda, **Then** o fornecedor aparece
   com a situação "não consultado" e os indicadores vazios, e passa a "encontrado" ou "não
   encontrado" na noite em que for consultado, sem intervenção manual.
3. **Given** um fornecedor pessoa física, **When** a Gold roda, **Then** ele aparece com o nome
   publicado e o CPF mascarado (só os seis dígitos centrais visíveis), e nenhuma tabela da Gold
   contém o CPF completo.
4. **Given** o mesmo CNPJ publicado com nomes diferentes em despesas diferentes, **When** a Gold
   roda, **Then** ele é um único membro da dimensão, com um nome escolhido por regra documentada.

---

### User Story 3 - Emendas parlamentares ligadas ao deputado (Priority: P3)

O analista consulta um fato de emendas com uma linha por emenda, tipo e localidade, com os valores
empenhado, liquidado e pago, associado a dimensões de autor, tipo de emenda, função e subfunção e
ano. Nas emendas individuais de deputados, o autor está ligado ao mesmo membro da dimensão de
deputado usada nas despesas, de modo que o relatório compara cota e emendas do mesmo parlamentar.
Emendas de relator, bancada e comissão, e emendas de senadores, aparecem com o autor publicado, sem
ligação a deputado.

**Why this priority**: amplia o case para emendas e permite a comparação cota × emendas, mas o
case de despesas já se sustenta sem isso.

**Independent Test**: conferir que o fato de emendas tem, por ano e tipo, a mesma quantidade e os
mesmos valores da Silver, e medir a parcela das emendas individuais cujo autor foi ligado a um
deputado.

**Acceptance Scenarios**:

1. **Given** a Silver de emendas carregada, **When** a Gold roda, **Then** o fato tem, por ano e
   tipo de emenda, a mesma quantidade de linhas e os mesmos valores empenhado, liquidado e pago.
2. **Given** uma emenda individual cujo autor tem o mesmo nome parlamentar de um deputado,
   **When** a Gold roda, **Then** a emenda fica ligada a esse deputado.
3. **Given** uma emenda de relator geral, bancada ou comissão, **When** a Gold roda, **Then** ela
   fica associada a um autor do tipo correspondente, sem deputado.
4. **Given** um nome de autor que corresponde a mais de um deputado, **When** a Gold roda,
   **Then** a emenda não é ligada a nenhum deles e o caso fica contado como ambíguo.

---

### User Story 4 - Atualização diária encadeada após a Silver (Priority: P4)

Todas as madrugadas, a mesma rotina diária que hoje atualiza Bronze e Silver passa a atualizar a
Gold em seguida, só depois do sucesso da Silver das duas fontes, e termina antes do horário de
consumo.

**Why this priority**: mantém o relatório em dia, mas depende das histórias anteriores.

**Independent Test**: depois da publicação em produção, conferir na manhã seguinte que a rotina
rodou a Gold depois da Silver, terminou antes das 07:00 e que a Gold reflete a Silver daquela
noite.

**Acceptance Scenarios**:

1. **Given** a rotina diária em produção, **When** a Silver das duas fontes termina com sucesso,
   **Then** a Gold roda em seguida e reflete a Silver daquela noite.
2. **Given** uma falha na Silver de qualquer fonte, **When** a rotina roda, **Then** a Gold não
   roda naquela noite e continua com os dados da noite anterior.
3. **Given** a rotina configurada, **When** o engenheiro olha as agendas, **Then** continua
   existindo uma única agenda diária, só em produção.

---

### User Story 5 - Qualidade da Gold verificável e registrada (Priority: P5)

A cada execução, a Gold verifica a unicidade das chaves de cada tabela, o preenchimento das
colunas obrigatórias, a integridade referencial de cada fato com cada dimensão e a conciliação dos
totais com a Silver, e registra o resultado e a contagem de linhas. Uma verificação que falha
impede que a Gold seja publicada com o problema.

**Why this priority**: exigida pelo Princípio V; protege o relatório de números errados.

**Independent Test**: rodar a Gold com sucesso e conferir o registro; provocar em desenvolvimento
uma linha de fato sem membro de dimensão e conferir que a execução falha e a Gold anterior
continua publicada.

**Acceptance Scenarios**:

1. **Given** uma execução da Gold concluída, **When** o engenheiro consulta o registro de
   verificações, **Then** encontra, para cada tabela, unicidade, obrigatórias e contagem, e, para
   cada fato, integridade com cada dimensão e conciliação com a Silver.
2. **Given** uma linha de fato sem membro na dimensão, **When** a Gold roda, **Then** a execução
   falha, o registro mostra qual verificação falhou, e as tabelas publicadas não mudam.

---

### User Story 6 - Modelo semântico `sm-gastos` pronto para o relatório (Priority: P6)

O analista abre o modelo semântico `sm-gastos` e encontra os fatos e dimensões da Gold
relacionados em estrela, com nomes legíveis, colunas técnicas ocultas, hierarquia de calendário e
medidas prontas (gasto da cota, gasto por deputado, emendas empenhadas, liquidadas e pagas,
parcela de emendas ligadas a deputado). O modelo lê a Gold diretamente, sem cópia agendada dos
dados, e em produção aponta para a Gold de produção. Os números das medidas batem com a Gold.

**Why this priority**: é o que o relatório consome e o artefato central da DP-600, mas depende de
a Gold estar estável.

**Independent Test**: consultar o modelo em produção e conferir que o gasto da cota por ano e o
valor pago de emendas por ano são iguais aos totais da Gold, e que o modelo reflete a Gold da noite
sem atualização manual.

**Acceptance Scenarios**:

1. **Given** a Gold carregada, **When** o analista consulta o gasto da cota por ano no modelo,
   **Then** o resultado é igual à soma do valor líquido da Gold em cada ano.
2. **Given** a rotina noturna atualizou a Gold, **When** o analista abre o modelo de manhã,
   **Then** vê os dados da noite sem ter disparado nenhuma atualização.
3. **Given** o modelo publicado em produção pelo pull request para `main`, **When** o engenheiro
   confere a origem dos dados, **Then** o modelo de produção lê o `gold_gastos` de produção, e o de
   desenvolvimento, o de desenvolvimento.
4. **Given** um analista filtrando por partido, **When** soma o gasto da cota, **Then** o filtro
   respeita o partido publicado na despesa (FR-006).

### Edge Cases

- Despesas de liderança: 6.074 linhas sem deputado; entram num membro por liderança (nome
  publicado), marcado como liderança.
- Deputados das despesas ausentes do cadastro: 234 de 1.161 (5.157 linhas); entram na dimensão com
  o que as despesas publicam (nome, partido e UF da linha mais recente).
- Partido publicado na despesa que não existe no cadastro de partidos (partido extinto ou
  incorporado no período): entra na dimensão de partido só com a sigla.
- Fornecedor sem documento ou com documento inválido (nem 11 nem 14 dígitos): agrupado num membro
  por nome publicado, marcado como sem documento.
- Fila de fornecedores ainda em andamento em produção (cerca de 38 mil CNPJs pendentes em
  2026-11-18, previsão de término por volta de 2026-11-21): a situação "não consultado" é
  esperada e diminui a cada noite.
- CNPJ encontrado no Portal com razão social vazia (89 casos): o nome publicado na despesa é usado.
- Emendas de senadores: o Portal traz emendas de todo o Congresso; autores que não casam com
  nenhum deputado ficam como autores não ligados, e o relatório os distingue.
- Diferenças de grafia entre o nome do autor da emenda e o nome parlamentar (acentos, maiúsculas,
  espaços): normalizadas antes da comparação; diferenças de nome em si (nome civil × nome
  parlamentar) ficam sem ligação.
- Emenda com código `S/I` ou sem número: entra no fato pela chave da Silver; o código publicado
  vira atributo, não chave.
- Valores negativos (compensações na cota, cancelamentos nas emendas): entram com o sinal da
  fonte.
- Silver com um ano a menos (ano ainda sem arquivo): a Gold reflete a Silver; nenhum ano é
  inventado.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O case MUST ter o lakehouse `gold_gastos`, o único lugar onde Câmara e Portal se
  cruzam (Princípio I), com dimensões `dim_`, fatos `fat_` e, se necessário, agregados `agg_`.
- **FR-002**: Cada fato MUST ter o grão documentado: `fat_despesas`, uma linha por despesa da
  Silver; `fat_emendas`, uma linha por emenda, tipo de transferência e localidade da Silver.
- **FR-003**: Cada dimensão MUST ter chave substituta `sk_<entidade>` e, quando houver, o id da
  fonte como `codigo_<entidade>`; colunas em `snake_case` em português (Princípio IV).
- **FR-004**: Toda dimensão referenciada por um fato MUST ter um membro para "não informado", de
  modo que nenhuma linha de fato fique sem membro e nenhum valor seja perdido na soma.
- **FR-005**: A dimensão de deputado MUST reunir os deputados do cadastro e os que só aparecem nas
  despesas, e as lideranças como membros próprios marcados como liderança.
- **FR-006**: O partido e a UF associados a cada despesa MUST ser os publicados na linha da
  despesa.
- **FR-007**: O calendário MUST cobrir de 2019-01-01 até o fim do ano corrente; cada despesa MUST
  se associar ao calendário pelo mês de competência (ano e mês publicados) e, quando houver, pela
  data de emissão.
- **FR-008**: A dimensão de fornecedor MUST ter um membro por documento de fornecedor, com a
  situação de consulta ao Portal (encontrado, não encontrado, não consultado) e, quando
  encontrado, a razão social e os indicadores do Portal.
- **FR-009**: Fornecedores pessoa física MUST aparecer com o nome publicado e o CPF mascarado,
  com só os seis dígitos centrais visíveis (`***.456.789-**`), um membro por CPF; o CPF completo
  MUST NOT ser gravado na Gold nem chegar ao modelo semântico.
- **FR-010**: O fato de emendas MUST se associar à dimensão de deputado nas emendas individuais
  cujo autor case, por nome normalizado, com exatamente um deputado; os demais autores MUST ficar
  numa dimensão de autor com o tipo (deputado, senador ou não identificado, relator, bancada,
  comissão, sem informação), sem ligação a deputado.
- **FR-011**: A Gold MUST ser reexecutável: rodar de novo sobre a mesma Silver MUST produzir as
  mesmas tabelas, sem duplicidade (Princípio II).
- **FR-012**: Cada execução da Gold MUST verificar unicidade da chave e obrigatórias de cada
  tabela, integridade referencial de cada fato com cada dimensão e conciliação dos totais dos
  fatos com a Silver (quantidade e valores por ano), e MUST registrar o resultado e a contagem de
  linhas num registro `ctl_quality_checks` no `gold_gastos` (Princípio V).
- **FR-013**: Uma verificação que falha MUST interromper a rotina, e as tabelas da Gold MUST NOT
  ficar publicadas com os dados que violaram a verificação.
- **FR-014**: A rotina diária existente MUST rodar a Gold depois do sucesso da Silver das duas
  fontes, só em produção, sem agenda nova.
- **FR-015**: Nenhuma tabela da Gold MUST conter CPF de deputado.
- **FR-016**: Os itens novos MUST seguir o padrão de nomes da constituição v3.0.0 e passar no
  validador de nomes do pull request (Princípios III e IV).
- **FR-017**: O modelo semântico `sm-gastos` MUST ler as tabelas do `gold_gastos` diretamente,
  sem importação agendada (Direct Lake), com os fatos e dimensões relacionados em estrela e
  filtro de uma direção, das dimensões para os fatos.
- **FR-018**: O modelo MUST expor medidas para, no mínimo: gasto líquido da cota, quantidade de
  despesas, gasto médio por deputado, valores empenhado, liquidado e pago de emendas e parcela do
  valor pago de emendas individuais ligada a deputado; colunas de chave e linhagem MUST ficar
  ocultas; o calendário MUST ter hierarquia ano, trimestre, mês.
- **FR-019**: O modelo MUST ser versionado no Git e publicado em produção pelo mesmo fluxo de pull
  request das demais camadas, apontando para o `gold_gastos` do ambiente onde está (Princípio III).
- **FR-020**: O relatório `rpt-gastos-parlamentares` está fora do escopo desta feature.

### Key Entities *(include if feature involves data)*

- **Fato de despesa** (`fat_despesas`): uma linha por despesa da cota; valores do documento, glosa,
  líquido e restituição; referências a deputado, partido, UF, tipo de despesa, fornecedor, mês de
  competência e data de emissão; número e link do documento como atributos.
- **Fato de emenda** (`fat_emendas`): uma linha por emenda, tipo e localidade; valores empenhado,
  liquidado, pago e de restos a pagar; referências a autor (e deputado, quando ligado), tipo de
  emenda, função e subfunção, localidade e ano.
- **Deputado**: um membro por deputado ou liderança; nome parlamentar e civil, sexo, UF e partido
  atuais (do cadastro, quando houver), foto, situação, indicação de liderança e de presença no
  cadastro.
- **Partido**: sigla e nome.
- **UF**: sigla e nome da unidade da federação.
- **Tipo de despesa**: subcota e especificação publicadas.
- **Fornecedor**: documento, tipo de documento, nome, situação de consulta ao Portal, razão social e
  indicadores do Portal.
- **Autor de emenda**: nome publicado, tipo de autor e deputado ligado, quando houver.
- **Tipo de emenda, função e subfunção, localidade**: descrições publicadas pelo Portal.
- **Calendário**: data, mês, trimestre, ano, nomes em português.
- **Modelo semântico** (`sm-gastos`): fatos e dimensões da Gold em estrela, medidas, hierarquia de
  calendário; lê a Gold do próprio ambiente.
- **Verificação de qualidade**: execução, tabela, verificação, resultado, linhas com problema,
  contagem e ambiente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Para cada ano de 2019 a 2026, a quantidade de linhas e a soma do valor líquido do
  fato de despesas são iguais às da Silver.
- **SC-002**: Para cada ano e tipo de emenda, a quantidade de linhas e as somas de empenhado,
  liquidado e pago do fato de emendas são iguais às da Silver.
- **SC-003**: 100% das linhas de cada fato encontram membro em cada dimensão referenciada; zero
  chaves duplicadas em qualquer tabela.
- **SC-004**: Pelo menos 60% do valor pago em emendas individuais fica ligado a um deputado (a
  comparação exata de nomes casou cerca de 63% em 2026-11-18), e a parcela ligada é registrada a
  cada execução.
- **SC-005**: A rotina noturna completa, Bronze, Silver e Gold, termina antes das 07:00 de
  Brasília.
- **SC-006**: A Gold está publicada e carregada em produção até 2026-11-26, com a primeira rotina
  noturna conferida, deixando cerca de uma semana de Trial para o modelo semântico e o relatório.
- **SC-007**: Nenhuma tabela da Gold nem coluna do modelo contém CPF de deputado ou CPF completo de
  fornecedor.
- **SC-008**: Uma linha de fato sem membro de dimensão provocada em desenvolvimento interrompe a
  rotina sem alterar as tabelas publicadas.
- **SC-009**: Em produção, o gasto da cota e o valor pago de emendas por ano no `sm-gastos` são
  iguais aos totais da Gold, e o modelo mostra os dados da rotina noturna sem atualização manual.
- **SC-010**: O `sm-gastos` está publicado em produção até 2026-11-30, deixando alguns dias de Trial
  para o relatório.

## Assumptions

- Perfil de produção em 2026-11-18: 1.687.037 despesas (1.672.509 com CNPJ, 14.528 com CPF,
  6.074 de liderança); 68.121 CNPJs distintos nas despesas, dos quais 18.355 encontrados, 11.645
  não encontrados e 38.121 ainda na fila do Portal; 55.057 emendas, das quais 51.662 individuais;
  1.216 autores distintos de emendas individuais, 785 casando por nome exato com deputados.
- A Silver guarda só o estado mais recente de cada registro; a Gold também. Histórico de
  mudanças de atributos (SCD tipo 2) está fora do escopo: o partido histórico já vem na linha da
  despesa (FR-006).
- O volume (cerca de 1,7 milhão de despesas) permite reconstruir a Gold inteira a cada noite; a
  escolha entre reconstrução e carga incremental é do plano, desde que SC-005 seja atendido
  (Princípio VII).
- O modelo é Direct Lake sobre o `gold_gastos`, então as tabelas precisam ser Delta, com tipos
  compatíveis e sem colunas calculadas no modelo; os limites de Direct Lake da capacidade Trial e a
  forma de reapontar o modelo para produção na publicação são decididos no plano.
- O mascaramento do CPF de fornecedor é uma escolha de portfólio (o dado é público na fonte); o
  documento completo continua só na Silver e na Bronze, que não são consumidas.
- A capacidade Trial permite uma sessão Spark por vez, e o Trial termina por volta de 2026-12-04.
- O desenvolvimento acontece em `ws-dev-dpacademy`; a publicação em produção é por pull request
  para `main` (feature 002), e a rotina agendada só roda em `ws-prd-dpacademy`.
- Fora do escopo: casamento aproximado de nomes (fuzzy) entre autor de emenda e deputado,
  emendas de senadores ligadas a uma dimensão de senador, contratos do Portal, o relatório
  `rpt-gastos-parlamentares` e segurança em nível de linha no modelo.
