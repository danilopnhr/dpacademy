# Contrato: regras de nomenclatura verificáveis

As expressões abaixo são a interface entre o padrão documentado em
`docs/padrao-nomenclatura.md` e o validador `ci/validate_names.py`. Qualquer mudança nelas é uma
mudança do Princípio IV e passa por `/speckit-constitution`.

Blocos reutilizados:

- `SEQ` = `(?!000)\d{2}0` (três dígitos, de 10 em 10, nunca `000`)
- `CAMADA` = `(bronze|silver|gold)`
- `NOME` = `[a-z0-9]+` (sem hífen, sem underscore, sem acento)

## Itens do workspace (bloqueiam o PR)

Lidos de `workspace/**/.platform` (`metadata.type`, `metadata.displayName`).

| `metadata.type` | Expressão | Exemplo válido |
|---|---|---|
| `Lakehouse` | `^(bronze\|silver)_NOME$\|^gold_NOME$` | `bronze_balldontlie`, `gold_nba` |
| `Notebook` | `^nb-(full\|incr\|util)-SEQ-CAMADA-NOME-NOME$` | `nb-incr-030-bronze-balldontlie-jogos` |
| `Dataflow` | `^df-(full\|incr)-SEQ-CAMADA-NOME-NOME$` | `df-full-010-silver-balldontlie-cadastros` |
| `DataPipeline` | `^pl-SEQ-(bronze\|silver\|gold\|orq)-NOME-NOME$` | `pl-010-orq-nba-diario` |
| `SemanticModel` | `^sm-NOME$` | `sm-nba` |
| `Report` | `^rpt-NOME-NOME$` | `rpt-nba-temporadas` |
| qualquer outro | sem regra: **bloqueia** com "tipo sem regra" | — |

Regras adicionais:

- **Sequencial único**: para `Notebook`, `Dataflow` e `DataPipeline`, a combinação (tipo, camada,
  primeiro `NOME`, `SEQ`) não se repete. Ex.: `nb-full-010-gold-nba-dimensoes` e
  `nb-incr-010-gold-nba-fatos` violam (mesmo `010` em gold/nba).
- **Nome do workspace** não está no `.platform`; o validador não o confere. Os dois workspaces são
  criados uma vez com os nomes do FR-001 da spec e conferidos no quickstart.

## Tabelas (relatório pós-publicação, não bloqueia)

Lidas pela API de tabelas de cada lakehouse de produção depois do deploy.

| Lakehouse | Expressão | Exceções |
|---|---|---|
| `bronze_*`, `silver_*` | `^(LIGA\|ctl)_[a-z0-9_]+$`, com `LIGA` ∈ ligas configuradas (`nba`); `ctl_` = tabela de controle da fonte (`ctl_ingestion_runs`) | nenhuma |
| `gold_*` | `^(dim\|fat\|agg)_[a-z0-9_]+$` | nenhuma |

A lista de ligas fica em `ci/validate_names.py` (constante `LIGAS`). Uma liga nova entra nessa
lista no mesmo PR que a configura na ingestão.

## Saída do validador

- Código de saída `0`: nenhuma violação.
- Código de saída `1`: uma linha por violação, no formato
  `ERRO <caminho do .platform>: <tipo> "<displayName>" viola <regra>: <motivo>`,
  e uma anotação `::error file=<caminho do .platform>::<mesma linha>` por violação, para aparecer
  no PR, ligada ao arquivo.
- Avisos de tabela usam a anotação `::warning::` e não alteram o código de saída.
