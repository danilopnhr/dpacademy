# Contrato: notebooks da Silver, mudança na Bronze e orquestração

## Notebooks novos

Lakehouse padrão: o Silver da fonte. A Bronze é lida pelo nome qualificado
(`bronze_camara.<tabela>`, `bronze_transparencia.<tabela>`).

| Notebook | Parâmetros | Grava |
|---|---|---|
| `nb-util-010-silver-camara-comum` | — (biblioteca, via `%run`) | `ctl_quality_checks` |
| `nb-full-020-silver-camara-cadastros` | `recursos` (padrão `legislaturas,partidos,deputados`) | `legislaturas`, `partidos`, `deputados` |
| `nb-incr-030-silver-camara-despesas` | `anos` (vazio = todos os anos com lote novo; lista = só esses, mesmo sem lote novo) | `despesas` |
| `nb-util-010-silver-transparencia-comum` | — (biblioteca, via `%run`) | `ctl_quality_checks` |
| `nb-incr-020-silver-transparencia-emendas` | `anos` (mesma regra) | `emendas` |
| `nb-incr-030-silver-transparencia-fornecedores` | `completo` (padrão `false`; `true` reprocessa todos os CNPJs) | `pessoa_juridica` |

Biblioteca `comum` (as duas iguais, mudando só a fonte):

- `ambiente()`, igual à da Bronze.
- `lotes_validos(tabela_bronze, recurso, origem=None)`: lotes `succeeded` em
  `ctl_ingestion_runs` da Bronze.
- `valor_br(col)` e `valor_ponto(col)` → `DECIMAL(15,2)`; `data(col)` → `DATE`; `vazio_nulo(col)`.
- `verificar(df, tabela, chave, obrigatorias, run_id, detalhe)`: grava `unicidade` e
  `obrigatorias` em `ctl_quality_checks` e devolve se passou.
- `mesclar_particao(df, tabela, chave, condicao_particao)`: `MERGE` com inserção, atualização da
  linhagem e remoção restrita à partição (`None` = tabela toda).
- `registrar_contagem(tabela, run_id, detalhe)` e `encerrar(run_id, resultados)`: resumo,
  `notebookutils.notebook.exit` com JSON e exceção se alguma verificação falhou.

Saída de cada notebook (JSON do `exit`): `{"run_id", "tabelas": {"<tabela>": {"particoes",
"linhas_preparadas", "linhas_tabela", "status"}}}`. Uma verificação `failed` termina o notebook
com exceção depois de registrar o resultado.

## Mudança no `nb-incr-040-bronze-camara-despesas`

- `origem=arquivo` com `anos` vazio passa a significar "2019 até o ano corrente, só os que
  mudaram". `anos` informado mantém o comportamento atual para esses anos.
- Parâmetro novo `forcar` (padrão `false`): `true` grava mesmo com hash igual.
- Para cada ano: baixa o zip, extrai o CSV, calcula o SHA-256 do CSV e compara com o
  `source_hash` do último lote `succeeded` do ano. Igual e sem `forcar`: lote `skipped`,
  `message = 'arquivo sem mudança'`. Diferente: grava e salva o hash no lote.
- `origem=api` continua igual, só por disparo manual.
- `nb-util-010-bronze-camara-cliente` (Python puro, testado): `hash_csv(caminho)` (SHA-256 em
  blocos) e `anos_padrao(hoje)` (2019 até o ano corrente no fuso `America/Sao_Paulo`).
- `nb-util-020-bronze-camara-gravacao`: `garantir_tabelas()` acrescenta `source_hash` em
  `ctl_ingestion_runs` se faltar; `finalizar_lote` aceita `source_hash`; função nova
  `ultimo_hash(recurso, recorte)`.
- `pl-010-bronze-camara-gastos`: a atividade de despesas passa `origem=arquivo`.

## `pl-010-orq-gastos-diario`

Atividades de notebook, cada uma com timeout de 2 h e duas retentativas com 180 s de intervalo (o Trial
demora a liberar a sessão da atividade anterior e recusa a seguinte com `TooManyRequestsForCapacity`;
visto em 3 das 8 atividades no teste em dev de 2026-11-17):

```text
camara_cadastros (nb-full-030-bronze-camara-cadastros)
  └─Completed─► camara_despesas (nb-incr-040-bronze-camara-despesas, origem=arquivo)
                  └─Completed─► transparencia_emendas (nb-incr-030-bronze-transparencia-emendas)
                                  └─Completed─► transparencia_fornecedores (nb-incr-040-bronze-transparencia-fornecedores)
camara_cadastros + camara_despesas ─Succeeded─► silver_camara_cadastros ─Succeeded─► silver_camara_despesas
transparencia_emendas + transparencia_fornecedores ─Succeeded─► silver_transparencia_emendas ─Succeeded─► silver_transparencia_fornecedores
```

- As quatro atividades da Silver rodam depois das quatro da Bronze (dependem também da última
  Bronze com `Completed`), para nunca abrir duas sessões Spark ao mesmo tempo.
- Atividade Fail no fim, se qualquer atividade falhar, para o pipeline terminar como falha.
- Agenda em `ci/schedules.json`: `pl-010-orq-gastos-diario`, `04:00`,
  `E. South America Standard Time`. As entradas dos dois pipelines por fonte saem, e o
  `ci/deploy.py` desativa as agendas deles em produção (comportamento já existente, T039 da 002).
