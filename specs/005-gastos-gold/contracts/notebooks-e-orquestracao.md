# Contrato: notebooks da Gold e orquestração

## `nb-util-010-gold-gastos-comum`

Biblioteca chamada por `%run`, com `gold_gastos` como lakehouse padrão. Não grava tabelas.

Funções puras (testadas em `tests/unit/test_gold_comum.py`, carregadas pelo `conftest.py`):

| Função | Entrada → saída |
|---|---|
| `normalizar_nome(texto)` | `"  José  da Silva "` → `"JOSE DA SILVA"`; `None` → `None` |
| `mascarar_cpf(digitos)` | `"12345678901"` → `"***.456.789-**"`; outro tamanho → `None` |
| `formatar_cnpj(digitos)` | `"12345678000190"` → `"12.345.678/0001-90"`; outro tamanho → `None` |
| `grupo_emenda(tipo_emenda)` | `"Emenda Individual - …"` → `"Individual"`; `"Emenda de Bancada"` → `"Bancada"`; `"Emenda de Comissão"` → `"Comissão"`; `"Emenda de Relator"` → `"Relator"` |
| `ler_localidade(texto, ufs)` | `"SÃO PAULO (UF)"` → `("Estado", "SP")`; `"CAMPINAS - SP"` → `("Município", "SP")`; `"MÚLTIPLO"` → `("Múltiplo", None)`; `"Nacional"` → `("Nacional", None)` |
| `UFS` | 27 tuplas `(sigla, nome, regiao)` |

Funções Spark: `sk(coluna_chave_natural)` (`xxhash64`), `membros_reservados(...)`, `verificar_*`
(uma por verificação do research R7, devolvendo as linhas para `ctl_quality_checks`),
`gravar(df, tabela)` (overwrite + V-Order), `registrar(resultados)`, `encerrar(resultados)` (levanta
exceção se houver `failed`).

## `nb-full-020-gold-gastos-modelo`

| Parâmetro | Padrão | Uso |
|---|---|---|
| `injetar_orfao_para_teste` | `false` | só em dev: acrescenta uma linha órfã ao fato de despesas preparado (SC-008) |

Passos: lê `silver_camara.{deputados,partidos,despesas}` e
`silver_transparencia.{emendas,pessoa_juridica}`; monta as dimensões e os fatos
([gold-tables.md](./gold-tables.md)); roda as verificações; se todas passarem, grava as dimensões e
depois os fatos, registra a `contagem` e pede o refresh do `sm-gastos` (`reenquadramento`, research
R9); senão, registra e falha sem gravar.

Proteções de privacidade na montagem (research R5): CPF completo dentro de nome de fornecedor,
razão social ou nome fantasia é trocado pela máscara (`mascarar_cpf_em_texto`, testada em `pytest`);
fornecedor sem nome publicado recebe a razão social do Portal ou o documento exibido.

Saída do notebook (`notebookutils.notebook.exit`): JSON com `run_id`, `status` e as contagens por
tabela, para leitura no monitor do pipeline.

## `pl-010-orq-gastos-diario` (mudança)

Atividades novas, depois das oito existentes:

| Atividade | Tipo | Depende de | Política |
|---|---|---|---|
| `gold_gastos` | Notebook `nb-full-020-gold-gastos-modelo` | `silver_camara_despesas` = `Succeeded` **e** `silver_transparencia_fornecedores` = `Succeeded` | timeout 1 h, 2 retentativas, intervalo 180 s |
| `falha_gold_gastos` | Fail | `gold_gastos` = `Failed` | — |

A agenda continua sendo só a do orquestrador, às 04:00 de Brasília, em `ci/schedules.json` (sem
mudança).

## `ci/parameter.yml` (entradas novas)

```yaml
  # Lakehouse padrão do notebook da Gold (feature 005)
  - find_value: "<GUID gold_gastos em dev>"
    replace_value:
      prd: "$items.Lakehouse.gold_gastos.$id"

  # Direct Lake do sm-gastos: servidor SQL e SQL endpoint do gold_gastos (feature 005, research R9)
  - find_value: "<servidor SQL de dev>.datawarehouse.fabric.microsoft.com"
    replace_value:
      prd: "$items.Lakehouse.gold_gastos.$sqlendpoint"
    item_type: "SemanticModel"
    file_path: "**/expressions.tmdl"
  - find_value: "<GUID do SQL endpoint do gold_gastos em dev>"
    replace_value:
      prd: "$items.Lakehouse.gold_gastos.$sqlendpointid"
    item_type: "SemanticModel"
    file_path: "**/expressions.tmdl"
```

Os marcadores são substituídos pelos valores reais de dev na implementação (o `deploy.py` recusa
`<GUID` no arquivo).

## `ci/validate_names.py` (mudança)

`validate_table_name` passa a aceitar `ctl_<assunto>` em lakehouses `gold_`, além de `dim_`, `fat_`
e `agg_`. Teste novo em `tests/unit/test_validate_names.py`.
