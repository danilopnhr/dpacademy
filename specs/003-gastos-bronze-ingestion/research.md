# Research: Ingestão Bronze do case gastos (Câmara + Portal da Transparência)

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-12

As decisões R5 a R7 e R9 reaproveitam a pesquisa da antiga feature 001 (balldontlie, nunca
implementada), ajustada para duas fontes.

## R1. Recursos da Câmara e como coletá-los

- **Decision**:
  - Cadastros pela API v2:
    - `GET /legislaturas`;
    - `GET /partidos`;
    - `GET /deputados?idLegislatura=56` e `=57`, que servem como fila. O que vai para a Bronze é o
      detalhe de cada um, `GET /deputados/{id}`.
  - Despesas da cota pela API, em `GET /deputados/{id}/despesas?ano=&mes=`, para a carga
    recorrente.
  - Despesas pelo arquivo anual `https://www.camara.leg.br/cotas/Ano-<AAAA>.csv.zip`, para o
    histórico.
- **Rationale**:
  - Testado em 2026-11-12, a API responde sem chave. Ela pagina por `pagina` e `itens` (até 100) e
    devolve o link `next` em `links` e o total no cabeçalho `X-Total-Count`.
  - O detalhe do deputado traz CPF, sexo, nascimento, escolaridade e município, que a lista não
    tem e que enriquecem a dimensão.
  - O arquivo anual é atualizado todo dia (o de 2026 tinha data de 2026-11-12 03:16) e traz numa
    só requisição o que a API levaria cerca de 6 mil chamadas para cobrir por ano.
- **Alternatives considered**:
  - Histórico só pela API: cerca de 1.200 deputados × 12 meses × 8 anos, ou ~115 mil chamadas.
    Inviável no prazo do Trial.
  - Recorrente pelo arquivo do ano corrente: uma chamada, mas grava ~170 mil linhas repetidas por
    dia na Bronze append-only e não exercita a ingestão por API, que é parte do portfólio.

## R2. Volume da Câmara (medido nos arquivos anuais em 2026-11-12)

| Ano | Despesas | Valor líquido (R$) | CNPJs distintos |
|---|---|---|---|
| 2019 | 199.383 | 158,1 mi | 21.179 |
| 2020 | 128.178 | 149,7 mi | 16.862 |
| 2021 | 155.274 | 165,1 mi | 20.124 |
| 2022 | 148.193 | 161,8 mi | 21.003 |
| 2023 | 173.515 | 201,2 mi | 21.563 |
| 2024 | 173.961 | 211,4 mi | 22.207 |
| 2025 | 170.589 | 214,5 mi | 22.036 |
| 2026 (até nov) | 123.968 | 154,6 mi | 21.404 |
| **Total** | **1.273.061** | | **68.042 distintos no período** |

**Republicação em 2026-11-13**: a Câmara republicou os arquivos de 2019 (199.383 → 289.832
despesas, R$ 158,1 → 210,9 mi) e de 2020 (128.178 → 167.144, R$ 149,7 → 173,3 mi) entre
2026-11-12 e 2026-11-13 (arquivos com data de 2026-11-13 03:32). Os demais anos não mudaram. Com
isso, o histórico passa a 1.402.476 despesas e 68.043 CNPJs distintos. A Bronze, carregada em
2026-11-13, bate exatamente com os arquivos republicados. Os totais de SC-001 são conferidos
contra o arquivo do dia da carga, nunca contra esta tabela.

- Os CSVs descompactados somam ~460 MB (de 46 a 72 MB por ano); separador `;`, UTF-8 com BOM,
  32 colunas (`txNomeParlamentar`, `ideCadastro`, `sgPartido`, `txtDescricao`, `txtFornecedor`,
  `txtCNPJCPF`, `datEmissao`, `vlrDocumento`, `vlrGlosa`, `vlrLiquido`, `numMes`, `numAno`,
  `ideDocumento`, `urlDocumento` e outras).
- Cerca de 0,5% das linhas não têm `ideCadastro`. São despesas de lideranças partidárias, não
  de deputados, e ficam na Bronze como vieram.
- A API usa outros nomes para os mesmos campos (`tipoDespesa`, `codDocumento`, `valorLiquido`,
  `cnpjCpfFornecedor`). A Bronze não unifica os nomes (R4); a Silver faz o mapeamento.

## R3. Recursos e limites do Portal da Transparência

- **Decision**:
  - `GET /api-de-dados/emendas?ano=<AAAA>&pagina=<n>`, para todos os autores.
  - `GET /api-de-dados/pessoa-juridica?cnpj=<cnpj>`, para cada fornecedor.
  - Chave no header `chave-api-dados`.
  - Paginação: `pagina` de 1 em diante até a resposta vir como lista vazia.
- **Rationale**: o OpenAPI público (`/v3/api-docs`, lido em 2026-11-12) confirma os dois
  endpoints. Em `/emendas`, `pagina` é obrigatório e `ano`, `nomeAutor`, `tipoEmenda` e outros
  filtros são opcionais. Em `/pessoa-juridica`, `cnpj` é obrigatório.
- **Limite de chamadas**: a página de cadastro da API informa cerca de 90 requisições por minuto
  das 06:00 às 23:59 e um limite maior de madrugada (00:00 às 05:59), que não aparece no
  OpenAPI. O ritmo é configurável por faixa de horário, com padrão de 0,7 s entre chamadas de dia
  (~85/min) e 0,25 s de madrugada (~240/min). Os valores serão confirmados no quickstart §5.
- **Pendências a verificar com a chave** (quickstart §5):
  - o tamanho da página de `/emendas` (o Portal costuma devolver 15 registros);
  - como `/pessoa-juridica` responde a um CNPJ inexistente (404, corpo vazio ou campos nulos).
  O cliente trata as três formas como "não encontrado".
- **Alternatives considered**: os arquivos em lote do Portal (download de CSV de emendas). Ficam
  como plano B se o volume de `/emendas` passar do orçamento de chamadas.

## R4. Formato das tabelas Bronze com duas origens

- **Decision**: toda tabela Bronze guarda o registro da fonte em `payload` (STRING com o JSON,
  nomes de campo como a fonte devolve), mais as colunas de auditoria:
  - `_ingested_at`, `_source_endpoint` e `_batch_id`, exigidas pela constituição;
  - `_origem` (`api` ou `arquivo`);
  - `_recorte`, um JSON com os parâmetros do lote.
  Linhas de CSV viram JSON com os nomes do cabeçalho e os valores como texto.
- **Rationale**: a despesa chega com dois esquemas, o do arquivo e o da API. Uma coluna JSON
  preserva os dois sem transformação (Princípio I) na mesma tabela (FR-006). O mesmo padrão
  passou na verificação da constituição na feature 001.
- **Alternatives considered**:
  - Colunas tipadas com os nomes da fonte: são dois esquemas incompatíveis na mesma tabela.
  - Uma tabela por origem (`despesas` e `despesas_arquivo`): contraria o FR-006 e duplica a lógica
    da Silver.

## R5. Onde guardar a chave do Portal (Princípio VI)

- **Decision**: arquivo texto em `bronze_transparencia/Files/_secrets/transparencia_api_key`,
  lido em tempo de execução. O valor nunca é impresso, nunca vai para `ctl_ingestion_runs`, e as
  mensagens de erro são sanitizadas. O arquivo é enviado à mão em dev e em produção, como a
  ADR-002 já prevê para o segredo da fonte.
- **Rationale**: o Key Vault exige assinatura Azure (Princípio VII). A área Files do lakehouse
  não passa pela Git integration nem pelo `fabric-cicd`.
- **Risco aceito**: qualquer membro do workspace lê o arquivo. É aceitável num tenant pessoal.
- **Alternatives considered**: Key Vault (pago); Variable Library (é sincronizada com o Git);
  header na Copy activity (fica em texto na definição do pipeline).

## R6. Motor de execução

- **Decision**: notebooks PySpark (Runtime padrão do workspace) orquestrados por Data Pipeline.
- **Rationale**: é a stack da constituição. O gargalo é a API, não o processamento. O maior lote
  (um arquivo anual, ~200 mil linhas, ~72 MB) cabe no driver e é lido com `spark.read.csv`.
- **Alternatives considered**: Python notebook sem Spark (mais leve, mas desvia da stack);
  Copy activity com conector REST (não resolve a chave com segurança nem o ritmo por horário).
- **Achado na implementação (2026-11-12)**: o runtime padrão do workspace roda Spark 4.1, e nele
  os parâmetros nomeados de `spark.sql(..., args=...)` não chegam ao SQL
  (`UNBOUND_SQL_PARAMETER`). A gravação usa a API do Delta (`DeltaTable.update`) e filtros de
  DataFrame no lugar de SQL parametrizado.

## R7. Organização do código e testes

- **Decision**: cada fonte tem os próprios notebooks, sem dependência entre fontes:
  - `nb-util-010-bronze-<fonte>-cliente`: Python puro. Faz HTTP, ritmo, retentativas e paginação.
    No caso da Câmara, também baixa e lê o arquivo anual.
  - `nb-util-020-bronze-<fonte>-gravacao`: PySpark. Cuida do append Delta atômico, de
    `ctl_ingestion_runs` e da trava de concorrência.
  - Notebooks de carga, que fazem `%run` dos dois.
  Testes locais com `pytest` carregam o `notebook-content.py` de cada cliente e simulam as APIs.
- **Rationale**: testa a lógica sem gastar Trial nem chamadas. Manter cada fonte autocontida
  segue o Princípio IV (`<fonte>` no nome) ao custo de ~60 linhas parecidas entre os dois
  clientes. A paginação e a autenticação são diferentes de qualquer forma.
- **Alternatives considered**: um motor comum às duas fontes. Exigiria um nome fora do padrão
  `<fonte|case>` ou uma emenda à constituição. Fica para quando houver uma terceira fonte.

## R8. Ritmo, retentativas e atomicidade

- **Decision**:
  - **Câmara**: uma requisição por vez, com no mínimo 0,25 s entre elas (o limite não é
    documentado).
  - **Portal**: ritmo por faixa de horário (R3).
  - **Retentativas**: em 429, 5xx e erro de conexão, até 5 tentativas com espera exponencial (15,
    30, 60, 120 e 240 s), respeitando `Retry-After`. Um 401 ou 403 falha na hora com "chave da
    API ausente ou inválida". Os outros 4xx falham na hora, com o corpo truncado em 300
    caracteres.
  - **Lotes**: cada lote é coletado inteiro em memória e gravado com um único append Delta, ou
    nada é gravado. Definição dos lotes:
    - despesas pelo arquivo: um ano;
    - despesas pela API: um mês, com todos os deputados;
    - cadastros: um recurso;
    - emendas: um ano;
    - fornecedores: um bloco de até 500 CNPJs.
- **Rationale**: atende ao FR-011 e ao FR-012. Não existe lote parcial na Bronze, e retomar
  (FR-008) é rodar o lote de novo. A carga de fornecedores é longa (até ~4 h), então os blocos
  evitam perder horas de coleta por uma falha no fim. Um bloco gravado é um lote completo.

## R9. Execuções simultâneas (FR-019)

- **Decision**: antes de um lote, procurar em `ctl_ingestion_runs` uma linha `running` do mesmo
  recurso iniciada há menos de 6 h. Se houver, a execução termina como `skipped`. Linhas
  `running` com mais de 6 h passam a `failed` com motivo `stale`.
- **Rationale**: simples e sem infraestrutura extra. 6 h fica acima da maior execução prevista
  (~4 h de fornecedores).

## R10. Fila de fornecedores (FR-017)

- **Decision**: a fila é a lista de CNPJs válidos (14 dígitos) que aparecem em
  `bronze_camara.despesas` (no `payload`, campo `txtCNPJCPF` ou `cnpjCpfFornecedor`) e ainda não
  estão em `bronze_transparencia.pessoa_juridica`, seja com cadastro, seja como não encontrado.
  O parâmetro `limite` define quantos CNPJs cada execução processa.
- **Rationale**: o Portal não oferece um cadastro de PJ em lote. Buscar só quem aparece nas
  despesas limita a carga a ~68 mil chamadas, ou ~4 h 45 min de madrugada a ~240/min, o que cabe
  em duas madrugadas antes do SC-004 (2026-11-30).
- **Desvio da constituição**: a ingestão do Portal lê a Bronze da Câmara para montar a fila,
  antes da Gold (Princípio I). Está justificado no Complexity Tracking do [plan.md](./plan.md).
  Quando a `silver_camara.despesas` existir, a fila passa a ler da Silver.
- **Alternatives considered**: a lista de CNPJs como parâmetro do pipeline (move o mesmo
  cruzamento para fora do notebook e não cabe em um parâmetro com 68 mil valores); a BrasilAPI
  (outra fonte fora da constituição).

## R11. Janelas padrão e agendamento

- **Decision**:
  - Despesas pela API: por padrão, o mês corrente e os dois anteriores, no fuso
    America/Sao_Paulo.
  - Emendas: por padrão, o ano corrente e o anterior, porque emendas de anos anteriores continuam
    recebendo pagamentos.
  - Agendas, só em produção:
    - `pl-010-bronze-transparencia-gastos` às 01:00, para usar o limite de madrugada;
    - `pl-010-bronze-camara-gastos` às 05:00.
  As agendas não fazem parte da definição Git do item. Elas entram como duas entradas em
  `ci/schedules.json` (formato da feature 002, fuso `E. South America Standard Time`), que o
  `ci/deploy.py` aplica só em produção.
- **Rationale**: atende ao FR-005, ao FR-009 e ao Princípio III, e reusa o mecanismo de agendas
  da feature 002 (research R8 da 002). Em dev não existe agenda.

## R12. Verificação de completude

- **Decision**:
  - **Despesas** (SC-001): comparar a contagem e a soma de `vlrLiquido` por ano na Bronze com as
    do arquivo anual (tabela R2).
  - **API da Câmara**: comparar o coletado com o `X-Total-Count` de cada consulta.
  - **Emendas** (SC-002): paginar até a lista vazia e conferir que o coletado é igual ao gravado.
  - **Fornecedores**: tamanho da fila antes e depois.
