# Contrato: modelo semântico `sm-gastos`

Direct Lake sobre o SQL endpoint do `gold_gastos` do próprio ambiente (research R9). Versionado em
`workspace/sm-gastos.SemanticModel/` (TMDL), publicado pelo `fabric-cicd`.

## Tabelas

Todas as tabelas `dim_` e `fat_` do [contrato da Gold](./gold-tables.md), em partições Direct Lake,
com estes nomes de exibição:

| Tabela Gold | Nome no modelo |
|---|---|
| `fat_despesas` | Despesas |
| `fat_emendas` | Emendas |
| `dim_data` | Calendário |
| `dim_deputado` | Deputado |
| `dim_partido` | Partido |
| `dim_uf` | UF |
| `dim_tipo_despesa` | Tipo de despesa |
| `dim_fornecedor` | Fornecedor |
| `dim_autor_emenda` | Autor da emenda |
| `dim_tipo_emenda` | Tipo de emenda |
| `dim_funcao` | Função |
| `dim_localidade` | Localidade |

`ctl_quality_checks` não entra no modelo. Colunas ocultas: todas as `sk_*`, `chave_natural`,
`chave_despesa`, `chave_emenda`, `_batch_id`, `_carregado_em` e as colunas de valor dos fatos
(expostas pelas medidas). Colunas visíveis com nome de exibição em português (ex.:
`nome_parlamentar` → "Nome parlamentar").

## Relacionamentos

Todos muitos para um, filtro de uma direção (dimensão → fato), ativos:

| De (fato) | Para (dimensão) |
|---|---|
| `fat_despesas[sk_data_competencia]` | `dim_data[sk_data]` |
| `fat_despesas[sk_deputado]` | `dim_deputado[sk_deputado]` |
| `fat_despesas[sk_partido]` | `dim_partido[sk_partido]` |
| `fat_despesas[sk_uf]` | `dim_uf[sk_uf]` |
| `fat_despesas[sk_tipo_despesa]` | `dim_tipo_despesa[sk_tipo_despesa]` |
| `fat_despesas[sk_fornecedor]` | `dim_fornecedor[sk_fornecedor]` |
| `fat_emendas[sk_data_ano]` | `dim_data[sk_data]` |
| `fat_emendas[sk_deputado]` | `dim_deputado[sk_deputado]` |
| `fat_emendas[sk_autor_emenda]` | `dim_autor_emenda[sk_autor_emenda]` |
| `fat_emendas[sk_tipo_emenda]` | `dim_tipo_emenda[sk_tipo_emenda]` |
| `fat_emendas[sk_funcao]` | `dim_funcao[sk_funcao]` |
| `fat_emendas[sk_localidade]` | `dim_localidade[sk_localidade]` |

## Calendário

`dim_data` marcada como tabela de datas (coluna `data`); hierarquia **Período**: Ano > Trimestre
(`nome_trimestre`) > Mês (`mes_ano`, ordenado por `ordem_mes_ano`); `nome_mes` ordenado por `mes`.
Emendas só têm sentido no nível de Ano (descrição da tabela Emendas avisa).

## Medidas

| Medida | Tabela | Definição (DAX, indicativa) | Formato |
|---|---|---|---|
| Gasto líquido | Despesas | `SUM(fat_despesas[valor_liquido])` | R$ #,0.00 |
| Valor do documento | Despesas | `SUM(fat_despesas[valor_documento])` | R$ #,0.00 |
| Glosa | Despesas | `SUM(fat_despesas[valor_glosa])` | R$ #,0.00 |
| Quantidade de despesas | Despesas | `COUNTROWS(fat_despesas)` | #,0 |
| Deputados com despesa | Despesas | `CALCULATE(DISTINCTCOUNT(fat_despesas[sk_deputado]), dim_deputado[tipo_membro] = "Deputado")` | #,0 |
| Gasto médio por deputado | Despesas | `DIVIDE(CALCULATE([Gasto líquido], dim_deputado[tipo_membro] = "Deputado"), [Deputados com despesa])` | R$ #,0.00 |
| Emendas empenhado | Emendas | `SUM(fat_emendas[valor_empenhado])` | R$ #,0.00 |
| Emendas liquidado | Emendas | `SUM(fat_emendas[valor_liquidado])` | R$ #,0.00 |
| Emendas pago | Emendas | `SUM(fat_emendas[valor_pago])` | R$ #,0.00 |
| Quantidade de emendas | Emendas | `COUNTROWS(fat_emendas)` | #,0 |
| Emendas individuais pago | Emendas | `CALCULATE([Emendas pago], dim_tipo_emenda[grupo_emenda] = "Individual")` | R$ #,0.00 |
| % pago ligado a deputado | Emendas | `DIVIDE(CALCULATE([Emendas individuais pago], dim_autor_emenda[ligado_a_deputado] = TRUE()), [Emendas individuais pago])` | 0.0% |

Sem colunas calculadas nem tabelas calculadas (Direct Lake). Sem segurança em nível de linha.

## Ambiente

- `expressions.tmdl`: `DatabaseQuery` = `Sql.Database("<servidor SQL>", "<id do SQL endpoint>")`
  do `gold_gastos` de dev no repositório; trocados na publicação (`ci/parameter.yml`).
- Modo de consulta Direct Lake padrão (automático, com fallback para DirectQuery).
- Atualização automática do Direct Lake ativa nos dois ambientes; nenhuma agenda de refresh.
