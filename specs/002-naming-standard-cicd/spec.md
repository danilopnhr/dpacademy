# Feature Specification: Padrão de nomenclatura e CI/CD do dpacademy

**Feature Branch**: `002-naming-standard-cicd`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description: "Contexto do que faremos. Nesse primeiro caso, iremos ingerir todos os
dados da API referente a UEFA CHAMPIONS LEAGUE. Pretendo padronizar as nomenclaturas conforme
essa página https://docs.datasource.expert/padroes-desenvolvimento/temas/nomenclaturas. Além
disso, vamos inserir a metodologia CI/CD."

## Clarifications

### Session 2026-10-22

- Q: Quais são as regras do padrão de nomenclatura (a página exige login)? → A: O engenheiro
  forneceu o conteúdo da página; aplicado em FR-001 a FR-004, substituindo o Princípio IV.
- Q: Qual esporte é o primeiro caso? → A: NBA. A Champions League foi descartada porque o plano
  gratuito da fonte não libera partidas; a NBA libera times, jogadores e jogos desde 1946. A
  ingestão da NBA já está especificada na feature 001; esta feature cobre a nomenclatura e o
  CI/CD, e renomeia o que a 001 definiu.
- Q: Como separar cases futuros (NFL, UCL...)? → A: Mesmo par de workspaces; Bronze e Silver por
  fonte, Gold por case; ingestão genérica com a liga como parâmetro (constituição 2.1.0).
- Q: A publicação em produção é automática ou manual? → A: Automática, logo após a conclusão da
  solicitação de mudança aprovada (FR-010).
- Q: Onde ficam repositório e CI/CD, já que o Azure DevOps passou a exigir assinatura Azure para
  criar organização (descoberto em 2026-10-23)? → A: GitHub, com repositório público e GitHub
  Actions (constituição 2.2.0). Com um engenheiro só, a "aprovação" de um PR é a sua conclusão com
  as validações verdes, registrada como quem mesclou, porque o GitHub não deixa o autor aprovar o
  próprio PR.

## User Scenarios & Testing *(mandatory)*

Os atores são o engenheiro de dados do dpacademy (dono do case), que desenvolve e publica
mudanças, e o avaliador do portfólio, que precisa ver nomes previsíveis e que nada chega à
produção sem revisão.

### User Story 1 - Padrão de nomenclatura aplicado ao projeto (Priority: P1)

O engenheiro consulta o padrão de nomenclatura no repositório e sabe, para cada tipo de item e
camada, como nomeá-lo. Todo item já existente ou planejado (inclusive os da ingestão NBA da
feature 001) passa a seguir o padrão.

**Why this priority**: os nomes precisam estar definidos antes de qualquer item ser criado nos
ambientes; renomear depois da publicação em produção é caro e quebra referências.

**Independent Test**: comparar a lista de itens do ambiente de desenvolvimento e os nomes citados
nos artefatos da feature 001 com o padrão documentado; zero divergências.

**Acceptance Scenarios**:

1. **Given** o padrão documentado, **When** o engenheiro precisa criar um notebook incremental da
   Bronze, **Then** o documento dá o formato e um exemplo do qual o nome sai sem ambiguidade.
2. **Given** os artefatos da feature 001 com nomes antigos, **When** esta feature é concluída,
   **Then** nenhum artefato da 001 cita os nomes antigos e todos usam os nomes do padrão.

---

### User Story 2 - Fluxo de CI/CD de desenvolvimento para produção (Priority: P2)

O engenheiro desenvolve no ambiente de desenvolvimento, salva no repositório e abre uma
solicitação de mudança para produção. Antes da aprovação, validações automáticas conferem a
convenção de nomes e a ausência de segredos. Aprovada a mudança, ela é publicada no ambiente de
produção sem passos manuais de cópia, já apontando para os recursos de produção.

**Why this priority**: é o requisito explícito do case (metodologia CI/CD) e o que diferencia o
portfólio; depende dos nomes (P1) para que as validações tenham o que conferir.

**Independent Test**: alterar um item no ambiente de desenvolvimento, abrir a solicitação de
mudança, ver as validações rodarem e, após a aprovação, conferir que o item ficou idêntico em
produção.

**Acceptance Scenarios**:

1. **Given** uma mudança salva no ramo de desenvolvimento, **When** o engenheiro abre a
   solicitação de mudança para produção, **Then** as validações automáticas rodam e o resultado
   aparece na própria solicitação.
2. **Given** uma mudança com um item fora da convenção de nomes ou com um segredo no conteúdo,
   **When** as validações rodam, **Then** a solicitação fica bloqueada e a mensagem aponta o item
   e a regra violada.
3. **Given** uma solicitação aprovada e concluída, **When** a publicação termina, **Then** o
   ambiente de produção contém a versão aprovada de cada item alterado, e o histórico mostra quem
   aprovou e quando.
4. **Given** qualquer tentativa de gravar diretamente no ramo de produção, sem solicitação de
   mudança, **When** o engenheiro tenta gravar, **Then** a gravação é recusada.

---

### User Story 3 - Ingestão NBA operando em produção (Priority: P3)

Depois da primeira publicação, a carga diária da NBA (feature 001) roda no ambiente de produção e
grava na Bronze de produção; o ambiente de desenvolvimento só recebe cargas disparadas
manualmente, para teste.

**Why this priority**: fecha o ciclo e demonstra que o que foi publicado funciona, mas depende de
P1, P2 e da feature 001.

**Independent Test**: após uma publicação, conferir que a execução agendada do dia seguinte
aparece no registro de execuções de produção e gravou na Bronze de produção, sem tocar a de
desenvolvimento.

**Acceptance Scenarios**:

1. **Given** a ingestão publicada em produção, **When** a carga diária agendada roda, **Then** os
   dados vão para a Bronze de produção e a execução fica registrada como de produção.
2. **Given** o ambiente de desenvolvimento, **When** nenhuma carga é disparada manualmente,
   **Then** nenhuma carga roda nele.

### Edge Cases

- Publicação para produção que falha no meio: o run de publicação fica com falha, o engenheiro é
  avisado por e-mail e produção pode ficar parcialmente atualizada; ela volta à última versão
  aprovada rodando de novo a última publicação bem-sucedida (ou revertendo o commit em `main`).
- Item renomeado para obedecer ao padrão: a publicação não deixa em produção uma cópia órfã com o
  nome antigo.
- Duas solicitações de mudança abertas ao mesmo tempo: a segunda só publica depois que a primeira
  termina, e cada uma é validada contra o estado atual do ramo de produção.
- Item novo de um tipo que o padrão não cobre (por exemplo, modelo semântico): a validação o
  sinaliza como "tipo sem regra" em vez de aprová-lo ou bloqueá-lo em silêncio.
- Mudança feita diretamente no ambiente de produção, fora do fluxo: é detectada e revertida na
  próxima publicação, e a divergência fica registrada.
- Segredo encontrado no histórico do repositório: a validação o aponta, e o segredo é trocado na
  fonte (Princípio VI), não apenas apagado.

## Requirements *(mandatory)*

### Functional Requirements

**Nomenclatura**

- **FR-001**: Todo item do projeto MUST seguir o padrão de nomenclatura datasource.expert (lado
  Microsoft), que substitui o Princípio IV da constituição. Nomes do primeiro caso (NBA):

  | Item | Padrão | Nome no dpacademy |
  |------|--------|-------------------|
  | Workspace | `ws-ambiente-bi` | `ws-dev-dpacademy`, `ws-prd-dpacademy` |
  | Lakehouse Bronze (por fonte) | `bronze_<fonte>` | `bronze_balldontlie` |
  | Lakehouse Silver (por fonte) | `silver_<fonte>` | `silver_balldontlie` |
  | Lakehouse Gold (por case) | `gold_<case>` | `gold_nba` |
  | Tabela Bronze | `<liga>_<endpoint>` | `nba_teams`, `nba_players`, `nba_games` |
  | Tabela de controle (Bronze/Silver) | `ctl_<assunto>` | `ctl_ingestion_runs` |
  | Tabela Silver (entidade limpa) | `<liga>_<entidade>` | `nba_times`, `nba_jogadores`, `nba_jogos` |
  | Tabela Gold | `dim_` / `fat_` / `agg_` | `dim_data`, `dim_time`, `dim_jogador`, `dim_temporada`, `fat_jogo`, `agg_desempenho_temporada` |
  | Notebook de biblioteca | `nb-util-999-camada-fonte-assunto` | `nb-util-010-bronze-balldontlie-cliente` |
  | Notebook Bronze | `nb-mode-999-bronze-fonte-assunto` | `nb-full-020-bronze-balldontlie-cadastros`, `nb-incr-030-bronze-balldontlie-jogos` |
  | Notebook Silver | `nb-mode-999-silver-fonte-assunto` | `nb-full-010-silver-balldontlie-cadastros`, `nb-incr-020-silver-balldontlie-jogos` |
  | Notebook Gold | `nb-mode-999-gold-case-assunto` | `nb-full-010-gold-nba-dimensoes`, `nb-incr-020-gold-nba-fatos` |
  | Dataflow Gen2 | `df-mode-999-camada-fonte-assunto` | nenhum previsto |
  | Pipeline de camada | `pl-999-camada-fonte-assunto` | `pl-010-bronze-balldontlie-nba` |
  | Pipeline de orquestração | `pl-999-orq-case-assunto` | `pl-010-orq-nba-diario` |
  | Modelo semântico | `sm-<case>` | `sm-nba` |
  | Relatório | `rpt-<case>-<assunto>` | `rpt-nba-temporadas` |

  Bronze e Silver são compartilhadas entre os cases da mesma fonte (NBA, e depois NFL ou UCL);
  cada case tem a sua Gold, orquestração, modelo semântico e relatórios.

- **FR-002**: Regras gerais MUST valer para todo nome: itens do workspace em minúsculas com hífen;
  lakehouses, tabelas e colunas em `snake_case`; sem acentos nem espaços; `mode` é `full`
  (cadastro recoletado inteiro), `incr` (coleta por janela) ou `util` (biblioteca que não grava
  tabelas); `999` é um sequencial de três dígitos, de 10 em 10, único por tipo, camada e fonte ou
  case.
- **FR-003**: Na Bronze, as colunas MUST manter os nomes e a estrutura devolvidos pela fonte
  (as-is); apenas as colunas de auditoria definidas na constituição são acrescentadas. Na Silver e
  na Gold, colunas MUST usar `snake_case` em português (por exemplo, `data_jogo`), com chave
  substituta `sk_<entidade>` e id da fonte `codigo_<entidade>`.
- **FR-004**: O padrão MUST ficar documentado no repositório, com as três camadas, as regras
  gerais e um exemplo por tipo de item.
- **FR-005**: Todos os artefatos da feature 001 (spec, plano, tarefas, contratos, modelo de dados
  e guia rápido) MUST ser atualizados para os nomes do FR-001, antes de qualquer item da 001 ser
  criado nos ambientes.

**CI/CD**

- **FR-006**: O projeto MUST ter dois ambientes separados, `ws-dev-dpacademy` e
  `ws-prd-dpacademy`, cada um ligado a um ramo próprio do repositório (`dev` e `main`).
- **FR-007**: Mudanças MUST chegar à produção apenas por solicitação de mudança aprovada de `dev`
  para `main`; gravação direta em `main` MUST ser recusada.
- **FR-008**: Cada solicitação de mudança MUST disparar validações automáticas que conferem, no
  mínimo, os nomes dos itens contra o padrão (FR-001 e FR-002) e a ausência de segredos; a
  solicitação MUST ficar bloqueada se alguma validação falhar.
- **FR-009**: A publicação em produção MUST acontecer sem cópia manual de itens e MUST ajustar as
  referências específicas de ambiente (por exemplo, para qual lakehouse cada notebook grava) para
  apontarem para produção.
- **FR-010**: A publicação em produção MUST ser disparada automaticamente logo após a conclusão
  da solicitação de mudança aprovada, sem nenhuma ação manual.
- **FR-011**: Cada publicação MUST ficar registrada com a versão publicada, quem aprovou, quando e
  o resultado.
- **FR-012**: A carga agendada da ingestão MUST rodar apenas em produção; em desenvolvimento, as
  cargas são só manuais.
- **FR-013**: Cada execução da ingestão MUST registrar o ambiente em que rodou.

### Key Entities *(include if feature involves data)*

- **Padrão de nomenclatura**: conjunto de regras por tipo de item e camada, com formato e
  exemplo.
- **Ambiente**: workspace de desenvolvimento ou de produção, ligado a um ramo do repositório.
- **Solicitação de mudança**: proposta de levar `dev` para `main`; resultado das validações,
  aprovador e situação.
- **Publicação**: uma promoção de desenvolvimento para produção; versão, aprovador, horários e
  resultado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos itens nos dois ambientes seguem o padrão de nomenclatura documentado.
- **SC-002**: Zero ocorrências dos nomes antigos (`lh_`, `nb_`, `pl_`, `bdl_`, `fato_`,
  `dpacademy-dev`, `dpacademy-prod`) nos artefatos do repositório, verificado por busca textual.
- **SC-003**: 100% das mudanças em produção têm uma solicitação de mudança aprovada
  correspondente; zero alterações diretas.
- **SC-004**: 100% das solicitações com nome fora do padrão ou com segredo são bloqueadas (testado
  com uma solicitação de cada tipo plantada de propósito).
- **SC-005**: Uma mudança aprovada chega à produção em menos de 15 minutos, sem nenhum passo
  manual de cópia.
- **SC-006**: Após a primeira publicação, 100% das cargas agendadas rodam em produção e nenhuma em
  desenvolvimento.

## Assumptions

- O primeiro caso é a NBA, com a ingestão especificada na feature 001 (times, jogadores e jogos,
  desde 1946-47, plano gratuito da balldontlie). A UEFA Champions League foi avaliada e descartada
  em 2026-10-22: o plano gratuito não libera partidas.
- A constituição precisa de emenda via `/speckit-constitution` antes do plano técnico: o
  Princípio IV (`lh_`, `nb_`, `pl_`, `fato_`, `dpacademy-dev`/`dpacademy-prod`) é substituído pelo
  padrão do FR-001 (emendas 2.0.0 a 2.2.0, já aplicadas).
- O padrão traz dois formatos de pipeline (`pl-inc-999-...` no modelo e `pl-001-...` no exemplo);
  adotamos o do exemplo, sem o modo.
- O padrão não cobre notebooks de biblioteca, orquestração, modelo semântico nem relatório; as
  regras do FR-001 para esses itens são extensões do dpacademy, registradas na constituição 2.1.0.
- As dimensões e os fatos ficam na Gold, e não na Silver como sugere o padrão, porque a Gold é a
  camada lida pelo Direct Lake (Princípio I); o padrão permite, já que a Gold aceita nome livre.
- O fluxo de CI/CD usa o GitHub (repositório público, Actions e Issues), conforme a constituição
  2.2.0, e não gera custo (Princípio VII).
- A capacidade Trial do Fabric comporta os dois ambientes até cerca de 2026-12-05.
- A mesma chave da fonte serve aos dois ambientes.
- Fora do escopo: a lógica de ingestão (feature 001), transformações de Silver e Gold, modelo
  semântico, relatórios e testes automatizados de lógica de negócio além das validações listadas.
