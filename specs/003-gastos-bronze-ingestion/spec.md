# Feature Specification: Ingestão Bronze do case gastos (Câmara + Portal da Transparência)

**Feature Branch**: `003-gastos-bronze-ingestion`

**Created**: 2026-11-12

**Status**: Draft

**Input**: User description: "Ingestão Bronze das fontes do case gastos: API de Dados Abertos da
Câmara dos Deputados (deputados, partidos, legislaturas e despesas da cota parlamentar) e API do
Portal da Transparência (emendas parlamentares e cadastro de pessoa jurídica dos fornecedores),
com histórico desde 2019 e carga incremental idempotente, conforme a constituição v3.0.0."

## User Scenarios & Testing *(mandatory)*

O ator principal é o engenheiro de dados do dpacademy (o dono do case), que opera a ingestão.
O consumidor indireto é quem constrói as camadas Silver e Gold do case `gastos`, que precisa
encontrar na Bronze uma cópia fiel e completa do que cada fonte publicou.

### User Story 1 - Histórico da cota parlamentar (Priority: P1)

O engenheiro escolhe um ou mais anos e dispara a carga histórica da Câmara. Ao final, a Bronze
da Câmara contém os cadastros de deputados, partidos e legislaturas e todas as despesas da cota
parlamentar desses anos, exatamente como a fonte as publicou, cada registro marcado com quando
foi coletado, de qual recurso veio e a qual execução pertence.

**Why this priority**: as despesas da cota são o fato central do case; sem elas não existe
modelo dimensional nem relatório. É o mínimo demonstrável, e não depende de chave de acesso.

**Independent Test**: carregar o ano de 2024 e comparar a soma do valor líquido e a quantidade
de despesas na Bronze com os totais do arquivo anual publicado pela Câmara para 2024.

**Acceptance Scenarios**:

1. **Given** uma Bronze vazia, **When** o engenheiro carrega o ano de 2024, **Then** a Bronze
   contém os deputados das legislaturas 56 e 57, os partidos, as legislaturas e todas as
   despesas de 2024, cada registro com momento da coleta, recurso de origem e identificador da
   execução.
2. **Given** o ano de 2024 já carregado, **When** o engenheiro carrega o mesmo ano de novo,
   **Then** a execução termina com sucesso, fica registrada como nova execução e os dados da
   execução anterior continuam disponíveis e identificáveis.
3. **Given** a lista de anos 2019 a 2026, **When** o engenheiro dispara a carga, **Then** cada
   ano é processado e registrado como lote próprio, e a falha de um não apaga o que os outros já
   gravaram.

---

### User Story 2 - Atualização recorrente da cota parlamentar (Priority: P2)

Todos os dias, sem intervenção manual, a ingestão recoleta as despesas da janela recente e os
cadastros da Câmara. O engenheiro também pode disparar a carga para um mês específico, para
recuperar uma execução perdida.

**Why this priority**: mantém o case vivo com o mês corrente, mas depende do histórico (P1) para
ter valor.

**Independent Test**: disparar a carga para o mês anterior e conferir que a quantidade de
despesas na Bronze para aquele mês é igual à que a fonte informa.

**Acceptance Scenarios**:

1. **Given** despesas lançadas ou corrigidas pela fonte nos últimos três meses, **When** a carga
   diária agendada roda, **Then** a Bronze recebe o estado atual dessas despesas como a fonte
   informava no momento da coleta.
2. **Given** um mês sem nenhuma despesa nova, **When** a carga diária roda, **Then** a execução
   termina com sucesso e registra a quantidade coletada, sem ser tratada como erro.
3. **Given** que a carga de um mês falhou, **When** o engenheiro dispara a carga para aquele
   mês, **Then** as despesas do mês passam a constar na Bronze.

---

### User Story 3 - Emendas parlamentares (Priority: P3)

O engenheiro dispara a carga das emendas parlamentares de um ou mais anos. Ao final, a Bronze do
Portal da Transparência contém todas as emendas desses anos como a fonte as publicou, com autor,
valores e destino, para serem ligadas aos deputados nas camadas seguintes.

**Why this priority**: amplia o case de "quanto o deputado gasta" para "quanto o deputado
destina", mas o case já é demonstrável sem isso. É a primeira carga que exige chave de acesso.

**Independent Test**: carregar as emendas de 2024 e comparar a quantidade de emendas na Bronze
com o total que a fonte informa para 2024.

**Acceptance Scenarios**:

1. **Given** uma chave de acesso válida guardada em local protegido, **When** o engenheiro
   carrega as emendas de 2024, **Then** a Bronze do Portal contém todas as emendas de 2024, com as
   marcas de coleta, recurso e execução.
2. **Given** a chave ausente ou inválida, **When** o engenheiro dispara a carga, **Then** a
   execução falha logo no início com mensagem clara, sem coletar nada e sem exibir a chave.

---

### User Story 4 - Cadastro dos fornecedores (Priority: P4)

A ingestão identifica os fornecedores pessoa jurídica que aparecem nas despesas já coletadas e
ainda não têm cadastro na Bronze, e busca o cadastro de cada um no Portal da Transparência. O
engenheiro pode limitar quantos fornecedores cada execução processa.

**Why this priority**: enriquece a dimensão de fornecedor (razão social e se ele tem sanção,
contrato ou convênio com o governo federal), mas depende das despesas (P1) e da chave (P3).

**Independent Test**: com as despesas de um mês carregadas, rodar a carga de fornecedores e
conferir que todo CNPJ distinto daquele mês tem cadastro na Bronze ou um registro de "não
encontrado".

**Acceptance Scenarios**:

1. **Given** despesas com 500 CNPJs distintos sem cadastro, **When** a carga de fornecedores
   roda, **Then** cada um dos 500 tem cadastro gravado ou está registrado como não encontrado na
   fonte.
2. **Given** um limite de 200 fornecedores por execução, **When** a carga roda, **Then** ela
   processa no máximo 200, e a próxima execução continua de onde a anterior parou.
3. **Given** um fornecedor já cadastrado, **When** a carga roda de novo, **Then** ele não é
   buscado outra vez.

---

### User Story 5 - Acompanhamento das execuções (Priority: P5)

O engenheiro consulta um registro de execuções e sabe, para cada uma, a fonte, o recurso, o
recorte pedido (anos, meses, legislaturas), quando começou e terminou, quantos registros foram
coletados, quantas requisições foram feitas e se terminou com sucesso ou falha, com o motivo.

**Why this priority**: torna a operação auditável e é exigido pelos princípios da constituição,
mas não bloqueia a coleta em si.

**Independent Test**: rodar uma carga com sucesso e uma forçada a falhar (chave inválida) e
verificar que as duas aparecem no registro com status e motivo corretos.

**Acceptance Scenarios**:

1. **Given** uma carga concluída, **When** o engenheiro consulta o registro, **Then** encontra a
   execução com fonte, recurso, recorte, horários, contagens e status de sucesso.
2. **Given** uma carga que falhou no meio da paginação, **When** o engenheiro consulta o
   registro, **Then** a execução aparece como falha, com o motivo, e nenhum dado parcial dela é
   tratado como lote completo.

### Edge Cases

- A fonte recusa requisições por excesso de chamadas: a ingestão espera e tenta de novo, sem
  perder páginas e sem ultrapassar o limite da fonte. O Portal da Transparência tem limite menor
  durante o dia; cargas longas dele são agendadas de madrugada.
- A fonte fica indisponível ou devolve erro de servidor: novas tentativas com espera crescente;
  esgotadas as tentativas, a execução termina como falha com o motivo registrado.
- Uma página intermediária falha: o lote inteiro é marcado como falho, mesmo que páginas
  anteriores tenham sido coletadas.
- Despesa lançada ou corrigida meses depois (o deputado tem prazo para apresentar o documento):
  a janela recorrente recoleta os últimos três meses; correções mais antigas entram por recarga
  manual do ano.
- Despesa com valor negativo (estorno ou compensação): gravada como a fonte informar.
- Despesa sem CNPJ, com CPF de pessoa física ou com fornecedor estrangeiro: gravada como veio; só
  CNPJs válidos entram na busca de cadastro de fornecedor.
- CNPJ que o Portal não encontra: registrado como "não encontrado" para não ser buscado de novo a
  cada execução.
- Deputado que trocou de partido ou saiu do mandato: cada coleta grava o que a fonte informa
  naquele momento; o histórico é tratado nas camadas seguintes.
- Ano pedido que a fonte não tem (futuro ou anterior a 2019 no escopo): a execução registra zero
  registros e um aviso, sem erro.
- O arquivo anual e a consulta mês a mês da mesma fonte trazem as despesas com nomes de campo
  diferentes: cada registro guarda de qual dos dois veio, e a Bronze não unifica os nomes.
- Duas execuções disparadas ao mesmo tempo para o mesmo recurso: a segunda não começa enquanto a
  primeira não terminar.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A ingestão MUST coletar da Câmara os recursos deputados (legislaturas 56 e 57),
  partidos, legislaturas e despesas da cota parlamentar.
- **FR-002**: A ingestão MUST coletar do Portal da Transparência as emendas parlamentares por ano
  e o cadastro de pessoa jurídica dos fornecedores que aparecem nas despesas.
- **FR-003**: A ingestão MUST aceitar como parâmetros a fonte, o recurso, a janela (lista de
  anos ou de meses) e o recorte que o recurso exigir (legislatura, deputado, CNPJ).
- **FR-004**: Cadastros (deputados, partidos, legislaturas) MUST ser recoletados inteiros a cada
  execução; despesas e emendas MUST ser coletadas por janela.
- **FR-005**: Na ausência de parâmetros, a carga recorrente de despesas MUST coletar o mês
  corrente e os dois meses anteriores.
- **FR-006**: A carga histórica de despesas MAY usar os arquivos anuais publicados pela Câmara
  em vez da consulta por deputado; em ambos os casos, os registros vão para a mesma tabela da
  Bronze e indicam de qual dos dois caminhos vieram.
- **FR-007**: A carga histórica inicial MUST cobrir as despesas de 2019 até o mês corrente e as
  emendas de 2019 até o ano corrente.
- **FR-008**: A carga histórica MUST poder ser retomada: o engenheiro consegue reexecutar apenas
  os anos cujo lote falhou, sem recoletar os que já terminaram com sucesso.
- **FR-009**: A carga recorrente MUST rodar automaticamente uma vez por dia apenas no ambiente de
  produção; no ambiente de desenvolvimento, as cargas são disparadas manualmente.
- **FR-010**: A ingestão MUST percorrer todas as páginas de resultado da fonte até o fim.
- **FR-011**: A ingestão MUST respeitar o limite de chamadas de cada fonte e MUST tratar recusas
  por excesso de chamadas e erros temporários com novas tentativas e espera crescente.
- **FR-012**: Se qualquer página de um lote falhar após esgotar as tentativas, o lote inteiro
  MUST ser marcado como falho no registro de execuções.
- **FR-013**: Cada registro gravado MUST preservar o conteúdo devolvido pela fonte sem
  transformação e MUST carregar o momento da coleta, o recurso de origem e o identificador da
  execução.
- **FR-014**: A Bronze MUST apenas receber novos registros; nenhuma execução altera ou apaga
  registros de execuções anteriores.
- **FR-015**: Cada fonte MUST gravar no seu próprio lakehouse Bronze (`bronze_camara`,
  `bronze_transparencia`), em tabelas com o nome da entidade da fonte, sem prefixo (ex.:
  `despesas`, `deputados`, `emendas`).
- **FR-016**: Toda execução MUST ser registrada em `ctl_ingestion_runs` do lakehouse da fonte,
  com fonte, recurso, recorte, início, fim, quantidade de registros coletados, quantidade de
  requisições, status e motivo da falha quando houver.
- **FR-017**: A carga de fornecedores MUST buscar apenas CNPJs que aparecem nas despesas e ainda
  não têm cadastro nem registro de "não encontrado", e MUST aceitar um limite de fornecedores por
  execução.
- **FR-018**: A chave de acesso do Portal da Transparência MUST ser obtida de um local protegido,
  fora do código e do repositório, e MUST NOT aparecer em logs nem no registro de execuções. As
  cargas da Câmara MUST funcionar sem nenhuma chave.
- **FR-019**: Execuções simultâneas para o mesmo recurso MUST ser impedidas.
- **FR-020**: A carga histórica e a recorrente MUST usar a mesma lógica de coleta, diferindo
  apenas nos parâmetros; um recurso novo de uma fonte já existente MUST entrar por configuração,
  sem nova lógica de coleta.

### Key Entities *(include if feature involves data)*

- **Deputado** (Câmara): parlamentar; nome, partido, UF, legislatura, situação e foto. Cerca de
  500 por legislatura, mais suplentes que assumiram.
- **Partido** (Câmara): sigla, nome e número.
- **Legislatura** (Câmara): período de quatro anos; número, data de início e de fim.
- **Despesa da cota parlamentar** (Câmara): gasto ressarcido a um deputado; ano, mês, tipo de
  despesa, data e número do documento, valor do documento, glosa e valor líquido, fornecedor
  (nome e CNPJ ou CPF) e link da nota fiscal. Cerca de 200 mil por ano. Relaciona-se com um
  Deputado e, quando tem CNPJ, com um Fornecedor.
- **Emenda parlamentar** (Portal): recurso do orçamento indicado por um parlamentar ou bancada;
  ano, autor, tipo, função, localidade, valores empenhado, liquidado e pago. Relaciona-se com um
  Deputado pelo nome do autor nas camadas seguintes.
- **Fornecedor** (Portal): pessoa jurídica; CNPJ, razão social, nome fantasia e indicadores de
  relação com o governo federal (sanções CEIS, CNEP, CEPIM e CEAF, contratação, licitação,
  convênios, renúncia fiscal), ou a marca de "não encontrado". O Portal não informa atividade,
  porte nem município (confirmado em 2026-11-13).
- **Execução**: uma rodada da ingestão; fonte, recurso, recorte, horários, contagens, status e
  motivo de falha. Todo registro da Bronze aponta para uma Execução.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Para cada ano de despesas carregado, a quantidade de despesas e a soma do valor
  líquido na Bronze são iguais às do arquivo anual publicado pela Câmara (100% de completude).
- **SC-002**: Para cada ano de emendas carregado, a quantidade de emendas na Bronze é igual ao
  total que o Portal informa para o ano.
- **SC-003**: O histórico de despesas (2019 até o mês corrente) e os cadastros da Câmara estão na
  Bronze em até 2 horas de execução somadas.
- **SC-004**: O histórico de emendas (2019 até o ano corrente) e o cadastro de pelo menos 95% dos
  CNPJs distintos das despesas estão na Bronze antes de 2026-11-30, com folga para o fim do Trial
  (cerca de 2026-12-05).
- **SC-005**: Em 30 dias de operação diária, 100% das execuções recorrentes terminam com sucesso
  ou têm a falha recuperada por recarga manual em até 1 dia.
- **SC-006**: Zero execuções recusadas por excesso de chamadas terminam com perda de dados.
- **SC-007**: 100% das execuções aparecem no registro de execuções, com status correto.
- **SC-008**: A chave do Portal da Transparência não aparece em nenhum arquivo do repositório nem
  em nenhum log (verificado por busca textual).
- **SC-009**: Recarregar uma janela já coletada não exige nenhuma limpeza manual antes nem
  depois.

## Assumptions

- Fontes consultadas em 2026-11-12. A API da Câmara não exige chave, pagina por número de página
  com até 100 itens e informa o total de registros; a Câmara também publica arquivos anuais das
  despesas da cota (CSV e JSON, de 6 a 9 MB compactados por ano). A API do Portal da
  Transparência exige chave gratuita obtida com conta gov.br, tem limite de cerca de 90 chamadas
  por minuto durante o dia (maior de madrugada) e exige filtros em vários recursos.
- O engenheiro já possui (ou criará) a chave gratuita do Portal da Transparência antes da User
  Story 3.
- A capacidade Trial do Fabric está ativa até cerca de 2026-12-05; as cargas históricas precisam
  terminar antes disso.
- O desenvolvimento e as cargas manuais acontecem no workspace `ws-dev-dpacademy`; a carga
  recorrente agendada roda no `ws-prd-dpacademy`, depois que o fluxo de publicação da feature 002
  estiver ativo (constituição v3.0.0, Princípio III).
- Os nomes de itens e tabelas seguem o padrão datasource.expert da constituição v3.0.0
  (Princípio IV).
- A janela recorrente de três meses cobre o prazo que o deputado tem para apresentar documentos
  da cota; correções mais antigas são raras e entram por recarga manual do ano.
- As emendas são coletadas por ano para todos os autores (deputados, senadores, bancadas e
  comissões); o recorte para deputados acontece nas camadas seguintes.
- Recargas criam novas versões na Bronze; a deduplicação para a versão mais recente de cada
  registro é responsabilidade da Silver (Princípios I e II).
- Fora do escopo: votações, proposições, eventos e presenças da Câmara; outros recursos do Portal
  (contratos, licitações, servidores, viagens); transformações de Silver e Gold; qualquer
  relatório.
- As verificações de qualidade do Princípio V se aplicam a partir da Silver; nesta feature, a
  verificação é a completude por contagem (SC-001, SC-002) e o registro de execuções.
