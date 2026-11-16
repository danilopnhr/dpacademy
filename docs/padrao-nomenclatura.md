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

- **Bronze e Silver** são organizadas por **fonte** e compartilhadas entre os cases
  (`bronze_camara`, `bronze_transparencia`).
- **Gold** é organizada por **case**, com um lakehouse para cada um (`gold_gastos`). É o único
  lugar onde as fontes se cruzam.
- Os dois workspaces (`ws-dev-dpacademy` e `ws-prd-dpacademy`) abrigam todos os cases.

## Itens do workspace

| Item | Padrão | Exemplo |
|---|---|---|
| Workspace | `ws-<ambiente>-dpacademy` | `ws-dev-dpacademy`, `ws-prd-dpacademy`, `ws-lab-dpacademy` (laboratório DP-600) |
| Deployment pipeline do Fabric | `dpl-dpacademy-<finalidade>` | `dpl-dpacademy-lab` |
| Lakehouse Bronze | `bronze_<fonte>` | `bronze_camara`, `bronze_transparencia` |
| Lakehouse Silver | `silver_<fonte>` | `silver_camara` |
| Lakehouse Gold | `gold_<case>` | `gold_gastos` |
| Notebook de biblioteca | `nb-util-<999>-<camada>-<fonte>-<assunto>` | `nb-util-010-bronze-camara-cliente` |
| Notebook de carga completa | `nb-full-<999>-<camada>-<fonte\|case>-<assunto>` | `nb-full-030-bronze-camara-cadastros` |
| Notebook de carga por janela | `nb-incr-<999>-<camada>-<fonte\|case>-<assunto>` | `nb-incr-040-bronze-camara-despesas` |
| Dataflow Gen2 | `df-<full\|incr>-<999>-<camada>-<fonte\|case>-<assunto>` | `df-full-010-silver-camara-cadastros` |
| Pipeline de camada | `pl-<999>-<camada>-<fonte\|case>-<assunto>` | `pl-010-bronze-camara-gastos` |
| Pipeline de orquestração | `pl-<999>-orq-<case>-<assunto>` | `pl-010-orq-gastos-diario` |
| Modelo semântico | `sm-<case>` | `sm-gastos` |
| Relatório | `rpt-<case>-<assunto>` | `rpt-gastos-parlamentares` |

Na Silver e na Gold, os notebooks usam a fonte ou o case como escopo:
`nb-incr-020-silver-camara-despesas`, `nb-full-010-gold-gastos-dimensoes`.

### Modo da carga

- `full`: o cadastro é recoletado inteiro a cada execução (deputados, partidos, legislaturas).
- `incr`: os dados são coletados por janela (ano ou mês) ou por fila (fornecedores pendentes). A
  carga histórica é só uma janela grande, com o mesmo notebook (Princípio II).
- `util`: notebook de biblioteca que não grava tabelas e só é chamado por outros notebooks.

### Sequencial (`999`)

- Três dígitos, de 10 em 10 (`010`, `020`, `030`). O intervalo deixa espaço para encaixar um
  item novo sem renumerar os outros.
- É único por tipo, camada e fonte ou case, e recomeça em cada fonte ou case. Por isso
  `nb-util-010-bronze-camara-cliente` e `nb-util-010-bronze-transparencia-cliente` podem
  coexistir, mas `nb-full-010-gold-gastos-dimensoes` e `nb-incr-010-gold-gastos-fatos` não.
- Indica a ordem de execução dentro da camada.

## Tabelas

| Camada | Padrão | Exemplo |
|---|---|---|
| Bronze | `<entidade>` (nome da entidade na fonte, sem prefixo) | `despesas`, `deputados`, `emendas`, `pessoa_juridica` |
| Silver | `<entidade>` (entidade limpa, em português) | `despesas`, `deputados`, `fornecedores` |
| Controle da fonte (Bronze ou Silver) | `ctl_<assunto>`, com endpoint e recorte em colunas | `ctl_ingestion_runs` |
| Gold: dimensão | `dim_<entidade>` | `dim_data`, `dim_deputado`, `dim_partido`, `dim_fornecedor` |
| Gold: fato | `fat_<processo>` | `fat_despesa`, `fat_emenda` |
| Gold: agregada | `agg_<assunto>` | `agg_gasto_mensal` |

Bronze e Silver não levam prefixo porque o lakehouse já identifica a fonte (constituição v3.0.0).
A Silver não usa `dim_` nem `fat_`.

## Colunas

- **Bronze**: o registro da fonte fica em `payload` (JSON com os nomes de campo da fonte, sem
  alteração). Só se acrescentam as colunas de auditoria, iniciadas por `_`: `_ingested_at`,
  `_source_endpoint`, `_batch_id`, `_origem` e `_recorte`.
- **Silver e Gold**: `snake_case` em português (`data_documento`, `valor_liquido`).
  - chave substituta: `sk_<entidade>` (`sk_deputado`);
  - id da fonte: `codigo_<entidade>` (`codigo_deputado`).

## Regras gerais

- Itens do workspace em minúsculas com hífen; lakehouses, tabelas e colunas em `snake_case`.
- Sem acentos, sem espaços e sem maiúsculas.
- Cada parte (`<fonte>`, `<case>`, `<assunto>`) é uma palavra só, sem hífen nem underscore
  interno (`cadastros`, `despesas`, `fornecedores`).

## Como estender

- **Fonte nova**: ganha o par `bronze_<fonte>`/`silver_<fonte>` e os próprios notebooks
  `nb-util-010-bronze-<fonte>-cliente` e `nb-util-020-bronze-<fonte>-gravacao`. Nada muda no
  validador.
- **Case novo**: ganha `gold_<case>`, `pl-010-orq-<case>-diario`, `sm-<case>` e
  `rpt-<case>-<assunto>`, reaproveitando as fontes existentes.
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
