# Feature Specification: Camada Silver do case gastos (Câmara + Portal da Transparência)

**Feature Branch**: `004-gastos-silver`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Camada Silver do case gastos: uma tabela por entidade da Bronze,
tipada, em português e deduplicada, com despesas somente pelo arquivo anual da Câmara (pesquisa
de 2026-11-17), verificações de qualidade do Princípio V, recarga diária só dos arquivos anuais
que mudaram e um orquestrador diário único para Bronze e Silver, conforme a constituição v3.0.0."

## User Scenarios & Testing *(mandatory)*

O ator principal é o engenheiro de dados do dpacademy (o dono do case), que opera as cargas. O
consumidor indireto é quem constrói a Gold e o modelo semântico do case `gastos`, que precisa
encontrar na Silver uma versão única, tipada e confiável de cada registro das fontes, sem ter de
conhecer o formato bruto de cada uma.

### User Story 1 - Despesas da cota parlamentar confiáveis (Priority: P1)

O engenheiro roda a carga da Silver da Câmara. Ao final, existe uma tabela de despesas com uma
linha por despesa publicada na versão mais recente do arquivo anual de cada ano, com datas,
valores e códigos tipados, nomes de coluna em português e o sinal correto dos valores. As
despesas de liderança estão presentes, sem deputado associado. Se a Câmara republicou um ano, a
Silver reflete exatamente a nova versão: despesas incluídas aparecem e despesas retiradas somem.

**Why this priority**: as despesas são o fato central do case; a Gold e o relatório dependem de
uma versão única e correta delas. A pesquisa de 2026-11-17 mostrou que o arquivo anual é a única
origem completa e com o sinal correto.

**Independent Test**: carregar a Silver a partir da Bronze e comparar, para cada ano de 2019 a
2026, a quantidade de despesas e a soma do valor líquido da Silver com as do último arquivo
anual carregado na Bronze.

**Acceptance Scenarios**:

1. **Given** a Bronze com os arquivos anuais de 2019 a 2026, **When** o engenheiro roda a carga
   da Silver, **Then** cada ano tem na Silver a mesma quantidade de despesas e a mesma soma de
   valor líquido do último arquivo carregado daquele ano.
2. **Given** um ano republicado pela Câmara com linhas a mais e linhas a menos, **When** a nova
   versão chega à Bronze e a Silver roda, **Then** a Silver passa a refletir só a nova versão
   daquele ano, e os outros anos não mudam.
3. **Given** a Silver já atualizada, **When** o engenheiro roda a carga de novo sem nada novo na
   Bronze, **Then** nenhuma linha muda e a execução termina com sucesso.
4. **Given** despesas carregadas pela consulta mês a mês na Bronze, **When** a Silver roda,
   **Then** essas despesas não entram na Silver.

---

### User Story 2 - Cadastros da Câmara (Priority: P2)

O engenheiro roda a carga da Silver da Câmara e encontra deputados, partidos e legislaturas na
versão mais recente coletada, tipados e em português, prontos para virar dimensões. O CPF dos
deputados não é levado para a Silver.

**Why this priority**: as despesas precisam dos deputados, partidos e legislaturas para serem
analisadas por parlamentar, partido e UF, mas os cadastros sozinhos não formam o case.

**Independent Test**: conferir que a Silver tem 929 deputados, 38 partidos e 57 legislaturas
(as contagens do último lote da Bronze), um registro por código, e nenhuma coluna de CPF.

**Acceptance Scenarios**:

1. **Given** vários lotes de cadastros na Bronze, **When** a Silver roda, **Then** cada
   deputado, partido e legislatura aparece uma única vez, com os dados do lote mais recente.
2. **Given** um deputado que trocou de partido entre dois lotes, **When** a Silver roda,
   **Then** a Silver mostra o partido do lote mais recente.
3. **Given** o detalhe do deputado com CPF na fonte, **When** a Silver roda, **Then** nenhuma
   tabela da Silver contém o CPF.

---

### User Story 3 - Emendas e fornecedores do Portal da Transparência (Priority: P3)

O engenheiro roda a carga da Silver do Portal e encontra as emendas parlamentares na versão mais
recente de cada ano e o cadastro dos fornecedores na versão mais recente de cada CNPJ, tipados e
em português. Os fornecedores que o Portal não encontrou continuam na Silver, marcados como não
encontrados, para que a Gold saiba que foram consultados.

**Why this priority**: amplia o case para emendas e para o perfil dos fornecedores, mas o case de
despesas já é demonstrável sem isso.

**Independent Test**: conferir que a quantidade de emendas por ano na Silver é igual à do último
lote de cada ano na Bronze, e que cada CNPJ consultado aparece uma única vez na Silver, como
encontrado ou não encontrado.

**Acceptance Scenarios**:

1. **Given** as emendas de 2019 a 2026 na Bronze, com dois lotes para alguns anos, **When** a
   Silver roda, **Then** cada ano tem na Silver as emendas do lote mais recente daquele ano, com
   os valores numéricos corretos.
2. **Given** um CNPJ consultado mais de uma vez, **When** a Silver roda, **Then** ele aparece uma
   única vez, com o resultado mais recente.
3. **Given** a carga noturna de fornecedores ainda em andamento em produção, **When** a Silver
   roda a cada noite, **Then** os CNPJs consultados naquela noite entram na Silver sem
   reprocessar os anteriores.

---

### User Story 4 - Atualização diária encadeada (Priority: P4)

Todas as noites, sem intervenção manual, uma única rotina atualiza a Bronze das duas fontes e, em
seguida, a Silver das duas fontes. A Bronze de despesas passa a recarregar só os arquivos anuais
que a Câmara alterou desde a última carga, e deixa de coletar despesas pela consulta mês a mês. A
Silver só roda depois que a Bronze terminou.

**Why this priority**: mantém a Silver em dia e absorve as republicações da Câmara, mas depende
das cargas das histórias anteriores.

**Independent Test**: depois da publicação em produção, conferir na manhã seguinte que a rotina
rodou uma vez, na ordem Bronze do Portal, Bronze da Câmara e Silver, que só os arquivos anuais
alterados foram recarregados e que a Silver reflete a Bronze daquela noite.

**Acceptance Scenarios**:

1. **Given** nenhum arquivo anual alterado pela Câmara desde a última carga, **When** a rotina
   noturna roda, **Then** nenhum arquivo é recarregado e a execução registra que os arquivos
   foram verificados sem mudança.
2. **Given** a Câmara republicou os arquivos de dois anos, **When** a rotina noturna roda,
   **Then** só esses dois anos são recarregados na Bronze e atualizados na Silver.
3. **Given** uma falha na Bronze de uma fonte, **When** a rotina noturna roda, **Then** a Silver
   daquela fonte não roda e a falha fica registrada.
4. **Given** a rotina noturna configurada, **When** o engenheiro olha as agendas de produção,
   **Then** existe uma única agenda diária, e nenhuma agenda em desenvolvimento.

---

### User Story 5 - Qualidade verificável e registrada (Priority: P5)

A cada execução, a Silver verifica a unicidade da chave e o preenchimento das colunas
obrigatórias de cada tabela e registra a contagem de linhas. O engenheiro consulta um registro de
verificações e sabe, para cada execução e tabela, quais verificações passaram ou falharam e
quantas linhas havia. Uma verificação que falha interrompe a rotina antes da camada seguinte.

**Why this priority**: é exigida pelo Princípio V e protege a Gold de números errados, mas só faz
sentido sobre as tabelas das histórias anteriores.

**Independent Test**: rodar a Silver com sucesso e conferir o registro; depois provocar em
desenvolvimento uma chave duplicada e conferir que a execução falha, a verificação aparece como
falha no registro e a tabela não é publicada com a duplicidade.

**Acceptance Scenarios**:

1. **Given** uma execução da Silver concluída, **When** o engenheiro consulta o registro de
   verificações, **Then** encontra, para cada tabela, o resultado de unicidade, de obrigatórias e
   a contagem de linhas daquela execução.
2. **Given** dados que violam a unicidade da chave, **When** a Silver roda, **Then** a execução
   falha, o registro mostra qual verificação e qual tabela falharam, e a rotina não segue para a
   camada seguinte.

### Edge Cases

- O identificador de documento do arquivo não é único: `0` marca as despesas de telefonia
  (107.503 linhas de 2019 a 2026) e as passagens aéreas repetem o mesmo identificador em até 9
  linhas (trechos e passageiros). A chave da despesa precisa distinguir essas linhas.
- Linhas idênticas em todos os campos dentro do mesmo arquivo: tratadas como uma linha só ou
  mantidas, conforme decidido no plano a partir da contagem real; a regra fica documentada e a
  conferência do SC-001 a considera.
- Despesas de liderança (sem deputado): entram na Silver com o deputado vazio; o deputado não é
  coluna obrigatória.
- Despesas com valor negativo no arquivo (compensações): entram com o sinal do arquivo.
- Fornecedor com CPF, sem documento ou estrangeiro: o documento do fornecedor entra como veio,
  normalizado só em dígitos quando for CNPJ.
- Valores em formatos diferentes por fonte (vírgula decimal no arquivo, `1.234,56` no Portal):
  convertidos para número com duas casas decimais; um valor que não converte faz a verificação de
  obrigatórias falhar em vez de virar zero.
- Um ano de despesas que ainda não tem arquivo carregado na Bronze: não aparece na Silver; nenhum
  ano é apagado da Silver só porque não veio lote novo.
- Lotes da Bronze com status de falha: nunca entram na Silver (a Bronze só grava no sucesso, mas
  a Silver também ignora lotes que não estão como sucesso no registro de execuções).
- A Câmara fora do ar na hora da verificação dos arquivos: a Bronze da Câmara falha, a Silver da
  Câmara não roda naquela noite, e a da noite seguinte pega o que mudou.
- Bronze de desenvolvimento desatualizada (arquivos de 2021 a 2026 de antes da republicação de
  2026-11-16): recarregada antes de qualquer comparação entre ambientes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Cada fonte MUST ter seu lakehouse Silver (`silver_camara`, `silver_transparencia`),
  com uma tabela por entidade, no nome da entidade da fonte e sem prefixo: `legislaturas`,
  `partidos`, `deputados` e `despesas` na Câmara; `emendas` e `pessoa_juridica` no Portal.
- **FR-002**: As colunas da Silver MUST ser tipadas (datas como data, valores monetários como
  número com duas casas, códigos e contagens como inteiro quando a fonte for numérica) e nomeadas
  em `snake_case` em português, com o id da fonte como `codigo_<entidade>` (Princípio IV).
- **FR-003**: Cada linha da Silver MUST indicar o lote da Bronze de onde veio e o momento da
  coleta desse lote.
- **FR-004**: As despesas da Silver MUST vir somente dos arquivos anuais da Câmara; despesas
  coletadas pela consulta mês a mês MUST NOT entrar na Silver.
- **FR-005**: Para cada ano, a Silver de despesas MUST refletir exatamente o lote mais recente do
  arquivo daquele ano: despesas que deixaram de existir numa republicação MUST sair da Silver.
- **FR-006**: A despesa MUST ter uma chave que identifique cada linha publicada, inclusive as de
  identificador de documento `0` e as passagens aéreas com identificador repetido.
- **FR-007**: Deputados, partidos e legislaturas MUST refletir o lote completo mais recente da
  Bronze, uma linha por código.
- **FR-008**: O CPF dos deputados MUST NOT ser levado para a Silver.
- **FR-009**: As emendas MUST refletir o lote mais recente de cada ano, uma linha por emenda,
  tipo de transferência e localidade.
- **FR-010**: O cadastro de fornecedores MUST refletir o resultado mais recente de cada CNPJ,
  incluindo os não encontrados, com uma indicação de encontrado ou não.
- **FR-011**: A carga da Silver MUST ser incremental: processa só os lotes da Bronze que ainda
  não processou, e uma reexecução sem lotes novos MUST NOT alterar nenhuma linha (Princípio II).
- **FR-012**: A Silver MUST considerar apenas lotes registrados como sucesso no registro de
  execuções da Bronze.
- **FR-013**: Cada execução da Silver MUST verificar, para cada tabela, a unicidade da chave e o
  preenchimento das colunas obrigatórias, e MUST registrar o resultado e a contagem de linhas num
  registro de verificações `ctl_quality_checks` no lakehouse Silver da fonte (Princípio V).
- **FR-014**: Uma verificação que falha MUST interromper a rotina antes da camada seguinte, e a
  tabela MUST NOT ficar publicada com os dados que violaram a verificação.
- **FR-015**: A Bronze de despesas MUST verificar diariamente os arquivos anuais de 2019 até o
  ano corrente e recarregar apenas os que mudaram desde a última carga bem-sucedida, registrando
  a verificação mesmo quando nenhum arquivo mudou.
- **FR-016**: A rotina diária MUST deixar de coletar despesas pela consulta mês a mês; essa
  coleta MUST continuar disponível para disparo manual.
- **FR-017**: Uma única rotina diária MUST rodar, apenas em produção, a Bronze do Portal, a Bronze
  da Câmara e a Silver das duas fontes, em sequência, cada etapa só depois do sucesso da etapa
  de que depende; as agendas atuais por fonte MUST ser removidas.
- **FR-018**: Os itens novos MUST seguir o padrão de nomes da constituição v3.0.0 e passar no
  validador de nomes do pull request (Princípios III e IV).
- **FR-019**: Antes de validar a Silver em desenvolvimento, a Bronze de desenvolvimento MUST ser
  recarregada com os arquivos anuais de 2021 a 2026 republicados em 2026-11-16.
- **FR-020**: O backlog do repositório MUST trocar os épicos da NBA pelos épicos do case
  `gastos` (Bronze, Silver, Gold e Consumo).

### Key Entities *(include if feature involves data)*

- **Despesa** (Silver da Câmara): uma linha por despesa do arquivo anual; ano, mês, deputado
  (vazio nas lideranças), legislatura, tipo de despesa e especificação, fornecedor (nome e
  documento), número, tipo e data do documento, valor do documento, glosa, valor líquido,
  restituição, parcela, passageiro e trecho (passagens), link do documento e o lote de origem.
- **Deputado**: código, nome civil e eleitoral, partido, UF, legislatura, situação, sexo, data de
  nascimento, escolaridade e foto, sem CPF.
- **Partido**: código, sigla e nome.
- **Legislatura**: código, data de início e de fim.
- **Emenda**: código, ano, tipo, autor, função e subfunção, localidade do gasto, valores
  empenhado, liquidado, pago e de restos a pagar.
- **Fornecedor** (pessoa jurídica): CNPJ em dígitos, encontrado ou não, razão social, nome
  fantasia e indicadores de relação com o governo federal (sanções, contratos, convênios,
  licitações, renúncia fiscal).
- **Verificação de qualidade**: execução, tabela, verificação, resultado, quantidade de linhas
  com problema e contagem de linhas da tabela.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Para cada ano de 2019 a 2026, a quantidade de despesas e a soma do valor líquido na
  Silver são iguais às do último arquivo daquele ano na Bronze (considerando a regra de linhas
  idênticas definida no plano).
- **SC-002**: A quantidade de emendas por ano e de fornecedores na Silver é igual à do lote mais
  recente correspondente na Bronze, com zero chaves duplicadas.
- **SC-003**: 100% das execuções da Silver registram, para cada tabela, unicidade, obrigatórias e
  contagem de linhas; uma duplicidade provocada em desenvolvimento interrompe a rotina.
- **SC-004**: Reexecutar a Silver sem lotes novos na Bronze não altera nenhuma linha.
- **SC-005**: A rotina noturna termina, Bronze e Silver das duas fontes, antes das 06:00 de
  Brasília, e numa noite sem arquivo alterado a Bronze da Câmara leva menos tempo do que hoje
  (cerca de 30 minutos).
- **SC-006**: A Silver está publicada e carregada em produção até 2026-11-24, com a primeira
  rotina noturna conferida, deixando cerca de 10 dias de Trial para a Gold e o consumo.
- **SC-007**: Nenhuma tabela da Silver contém CPF de deputado.

## Assumptions

- Pesquisa de 2026-11-17 em produção (registro em `research.md`): nos documentos presentes nas
  duas origens, a consulta mês a mês inverte o sinal do valor líquido; parte dos documentos dela
  tem identificador sem correspondência no arquivo; as despesas de liderança só existem no
  arquivo. Por isso o arquivo é a origem oficial da Silver de despesas.
- O arquivo anual de um ano é sempre a publicação completa daquele ano; a Câmara o atualiza todos
  os dias no ano corrente e republica anos anteriores sem aviso (2019 e 2020 em 2026-11-13; 2021 a
  2026 em 2026-11-16).
- A forma de detectar que um arquivo anual mudou (data de modificação, tamanho ou conteúdo) é
  decidida no plano.
- A Silver guarda só o estado mais recente de cada registro; o histórico de versões continua na
  Bronze, que é append-only.
- A integridade referencial entre tabelas (despesa → deputado, despesa → fornecedor, emenda →
  deputado) é verificada na Gold, onde as fontes se cruzam (Princípios I e V).
- A capacidade Trial permite uma sessão Spark por vez, então as etapas da rotina rodam em
  sequência; o Trial termina por volta de 2026-12-04.
- Em produção, a fila de fornecedores ainda está sendo consultada (15 mil CNPJs por noite, de
  cerca de 68 mil, até por volta de 2026-11-21); a Silver acompanha incrementalmente.
- O desenvolvimento acontece em `ws-dev-dpacademy`; a rotina agendada roda em `ws-prd-dpacademy`
  depois da publicação por pull request para `main` (feature 002).
- Fora do escopo: modelo dimensional, cruzamento entre fontes, casamento de emendas com
  deputados pelo nome, modelo semântico e relatórios (features seguintes de Gold e Consumo).
