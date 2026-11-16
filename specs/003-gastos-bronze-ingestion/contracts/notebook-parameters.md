# Contrato: parâmetros dos notebooks e pipelines

Os notebooks recebem parâmetros pela célula marcada como *parameters* (sobrescrita pelo
pipeline ou pela execução manual). Listas são texto separado por vírgula. Vazio = padrão.

## `nb-full-030-bronze-camara-cadastros`

| Parâmetro | Tipo | Padrão | Significado |
|---|---|---|---|
| `recursos` | str | `legislaturas,partidos,deputados` | recursos a recoletar; cada um é um lote |
| `legislaturas` | str | `56,57` | legislaturas cuja lista de deputados forma a fila do detalhe |

## `nb-incr-040-bronze-camara-despesas`

| Parâmetro | Tipo | Padrão | Significado |
|---|---|---|---|
| `origem` | str | `api` | `api` (por mês) ou `arquivo` (por ano) |
| `anos` | str | vazio | só com `origem=arquivo`; ex.: `2019,2020,2021`; cada ano é um lote; obrigatório nesse modo |
| `meses` | str | vazio → mês corrente e os dois anteriores (America/Sao_Paulo) | só com `origem=api`; ex.: `2026-08,2026-09`; cada mês é um lote |
| `legislatura` | str | `57` | só com `origem=api`; legislatura cuja lista de deputados é percorrida |

## `nb-incr-030-bronze-transparencia-emendas`

| Parâmetro | Tipo | Padrão | Significado |
|---|---|---|---|
| `anos` | str | vazio → ano corrente e o anterior | cada ano é um lote |

## `nb-incr-040-bronze-transparencia-fornecedores`

| Parâmetro | Tipo | Padrão | Significado |
|---|---|---|---|
| `limite` | int | `15000` | máximo de CNPJs processados nesta execução |
| `tamanho_bloco` | int | `500` | CNPJs por lote (append atômico) |

## Saída de todo notebook de carga

`notebookutils.notebook.exit` devolve um JSON `{"run_id": "...", "lotes": n, "succeeded": n,
"failed": n, "skipped": n, "registros": n}`. Se algum lote terminar `failed`, o notebook termina
com exceção depois de registrar todos os lotes, para a atividade do pipeline falhar.

## Pipelines

| Pipeline | Atividades (em sequência) | Agenda (só produção) |
|---|---|---|
| `pl-010-bronze-camara-gastos` | `nb-full-030-bronze-camara-cadastros` → `nb-incr-040-bronze-camara-despesas` (padrões) | diária, 05:00 America/Sao_Paulo |
| `pl-010-bronze-transparencia-gastos` | `nb-incr-030-bronze-transparencia-emendas` → `nb-incr-040-bronze-transparencia-fornecedores` (padrões) | diária, 01:00 America/Sao_Paulo |

A segunda atividade de cada pipeline roda mesmo se a primeira falhar (dependência
"Completed"), porque os recursos são independentes; o pipeline termina com falha se qualquer
atividade falhar.
