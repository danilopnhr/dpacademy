# Padrão de nomenclatura do dpacademy

Todo item do Fabric, tabela e coluna do projeto segue este padrão. Ele é o Princípio IV da
[constituição](../.specify/memory/constitution.md), e o validador `ci/validate_names.py` o aplica em
todo pull request para `main`. As expressões regulares usadas pelo validador estão no
[contrato de regras](../specs/002-naming-standard-cicd/contracts/naming-rules.md).

## Origem

A base é o padrão [datasource.expert](https://docs.datasource.expert/padroes-desenvolvimento/temas/nomenclaturas)
(lado Microsoft). O dpacademy acrescenta regras para o que ele não cobre: o modo `util`, o pipeline
de orquestração, o modelo semântico, o relatório, as tabelas de controle e os sequenciais de 10 em
10. Também diverge do padrão num ponto: as dimensões e os fatos ficam na Gold, não na Silver,
porque é a Gold que o Direct Lake lê.

## Organização por fonte e por case

- **Bronze e Silver** são organizadas por **fonte** e compartilhadas entre os cases da mesma
  fonte. A NBA, e no futuro NFL ou UCL, usam o mesmo `bronze_balldontlie`.
- **Gold** é organizada por **case**, com um lakehouse para cada um (`gold_nba`).
- Os dois workspaces (`ws-dev-dpacademy` e `ws-prd-dpacademy`) abrigam todos os cases.

## Itens do workspace

| Item | Padrão | Exemplo |
|---|---|---|
| Workspace | `ws-<ambiente>-dpacademy` | `ws-dev-dpacademy`, `ws-prd-dpacademy`, `ws-lab-dpacademy` (laboratório DP-600) |
| Deployment pipeline do Fabric | `dpl-dpacademy-<finalidade>` | `dpl-dpacademy-lab` |
| Lakehouse Bronze | `bronze_<fonte>` | `bronze_balldontlie` |
| Lakehouse Silver | `silver_<fonte>` | `silver_balldontlie` |
| Lakehouse Gold | `gold_<case>` | `gold_nba` |
| Notebook de biblioteca | `nb-util-<999>-<camada>-<fonte>-<assunto>` | `nb-util-010-bronze-balldontlie-cliente` |
| Notebook de carga completa | `nb-full-<999>-<camada>-<fonte\|case>-<assunto>` | `nb-full-020-bronze-balldontlie-cadastros` |
| Notebook de carga por janela | `nb-incr-<999>-<camada>-<fonte\|case>-<assunto>` | `nb-incr-030-bronze-balldontlie-jogos` |
| Dataflow Gen2 | `df-<full\|incr>-<999>-<camada>-<fonte\|case>-<assunto>` | `df-full-010-silver-balldontlie-cadastros` |
| Pipeline de camada | `pl-<999>-<camada>-<fonte\|case>-<assunto>` | `pl-010-bronze-balldontlie-nba` |
| Pipeline de orquestração | `pl-<999>-orq-<case>-<assunto>` | `pl-010-orq-nba-diario` |
| Modelo semântico | `sm-<case>` | `sm-nba` |
| Relatório | `rpt-<case>-<assunto>` | `rpt-nba-temporadas` |

Na Silver e na Gold, os notebooks usam a fonte ou o case como escopo:
`nb-incr-020-silver-balldontlie-jogos`, `nb-full-010-gold-nba-dimensoes`.

### Modo da carga

- `full`: o cadastro é recoletado inteiro a cada execução (times, jogadores).
- `incr`: os dados são coletados por janela, de datas ou de temporada. A carga histórica é só
  uma janela grande, com o mesmo notebook (Princípio II).
- `util`: notebook de biblioteca que não grava tabelas e só é chamado por outros notebooks.

### Sequencial (`999`)

- Três dígitos, de 10 em 10 (`010`, `020`, `030`). O intervalo deixa espaço para encaixar um
  item novo sem renumerar os outros.
- É único por tipo, camada e fonte ou case, e recomeça em cada fonte ou case. Por isso
  `nb-full-010-gold-nba-dimensoes` e `nb-full-010-gold-nfl-dimensoes` podem coexistir, mas
  `nb-full-010-gold-nba-dimensoes` e `nb-incr-010-gold-nba-fatos` não.
- Indica a ordem de execução dentro da camada.

## Tabelas

| Camada | Padrão | Exemplo |
|---|---|---|
| Bronze | `<liga>_<endpoint>` (nome do endpoint da fonte) | `nba_teams`, `nba_players`, `nba_games` |
| Silver | `<liga>_<entidade>` (entidade limpa, em português) | `nba_times`, `nba_jogadores`, `nba_jogos` |
| Controle da fonte (Bronze ou Silver) | `ctl_<assunto>`, com a liga numa coluna | `ctl_ingestion_runs` |
| Gold: dimensão | `dim_<entidade>` | `dim_data`, `dim_time`, `dim_jogador`, `dim_temporada` |
| Gold: fato | `fat_<processo>` | `fat_jogo` |
| Gold: agregada | `agg_<assunto>` | `agg_desempenho_temporada` |

A Silver não usa `dim_` nem `fat_`, e a Gold não leva prefixo de liga, porque o lakehouse já é
do case.

## Colunas

- **Bronze**: os nomes e a estrutura vêm da fonte, sem alteração. Só se acrescentam as colunas de
  auditoria, iniciadas por `_`: `_ingested_at`, `_source_endpoint` e `_batch_id`.
- **Silver e Gold**: `snake_case` em português (`data_jogo`, `pontos_mandante`).
  - chave substituta: `sk_<entidade>` (`sk_time`);
  - id da fonte: `codigo_<entidade>` (`codigo_time`).

## Regras gerais

- Itens do workspace em minúsculas com hífen; lakehouses, tabelas e colunas em `snake_case`.
- Sem acentos, sem espaços e sem maiúsculas.
- Cada parte (`<fonte>`, `<case>`, `<assunto>`) é uma palavra só, sem hífen nem underscore
  interno (`cadastros`, `jogos`, `temporadas`).

## Como estender

- **Liga nova da mesma fonte** (por exemplo, NFL): acrescente a liga à constante `LIGAS` em
  `ci/validate_names.py` no mesmo PR que a configura na ingestão. As tabelas ficam com o prefixo
  `nfl_`, e o case ganha `gold_nfl`, `pl-010-orq-nfl-diario`, `sm-nfl` e `rpt-nfl-<assunto>`.
- **Tipo de item novo** (por exemplo, Variable Library): o PR fica bloqueado com "tipo sem regra"
  até que a regra seja definida na feature que cria o item. A regra precisa entrar neste
  documento, em `ITEM_RULES` de `ci/validate_names.py` e no contrato de regras.
- **Mudança de regra**: é uma mudança do Princípio IV e passa por `/speckit-constitution`.

## Como validar

```powershell
python ci/validate_names.py workspace/
```

O comando sai com `0` quando não há violação. Os nomes de tabela não estão no Git, por isso são
conferidos depois de cada publicação em produção, como avisos no resumo do `deploy-prd`.
