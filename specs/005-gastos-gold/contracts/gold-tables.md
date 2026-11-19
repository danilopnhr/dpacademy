# Contrato: tabelas do `gold_gastos`

Todas as tabelas são Delta, gravadas por `overwrite` com `delta.parquet.vorder.enabled = true`, e
têm `_carregado_em TIMESTAMP`. Valores `DECIMAL(15,2)`. Membros reservados `-1` ("Não informado") e
`-2` ("Não se aplica") em todas as dimensões, exceto `dim_data`; nos reservados, os textos
obrigatórios recebem o rótulo do membro e os demais ficam nulos.

## `dim_data`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_data` | INT | `AAAAMMDD` |
| `data` | DATE | a data |
| `ano` | INT | |
| `trimestre` | INT | 1 a 4 |
| `nome_trimestre` | STRING | `T1` a `T4` |
| `mes` | INT | 1 a 12 |
| `nome_mes` | STRING | `janeiro` … |
| `mes_abreviado` | STRING | `jan` … |
| `mes_ano` | STRING | `jan/2024` |
| `ordem_mes_ano` | INT | `202401` (ordenação de `mes_ano`) |
| `dia` | INT | |
| `dia_semana` | INT | 1 (domingo) a 7 |
| `nome_dia_semana` | STRING | `domingo` … |

## `dim_deputado`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_deputado` | BIGINT | R2 |
| `codigo_deputado` | INT | id da Câmara; nulo em lideranças e reservados |
| `nome_parlamentar` | STRING | do cadastro, ou das despesas |
| `nome_civil` | STRING | do cadastro |
| `sigla_partido_atual` | STRING | cadastro, ou linha mais recente das despesas |
| `sigla_uf_atual` | STRING | idem |
| `sexo` | STRING | cadastro |
| `data_nascimento` | DATE | cadastro |
| `escolaridade` | STRING | cadastro |
| `situacao` | STRING | cadastro |
| `url_foto` | STRING | cadastro |
| `e_lideranca` | BOOLEAN | |
| `no_cadastro` | BOOLEAN | presente em `silver_camara.deputados` |
| `tipo_membro` | STRING | `Deputado`, `Liderança`, `Não informado`, `Não se aplica` |
| `chave_natural` | STRING | `D:…` ou `L:…` (técnica, oculta no modelo) |

## `dim_partido`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_partido` | BIGINT | |
| `codigo_partido` | INT | do cadastro, quando houver |
| `sigla_partido` | STRING | |
| `nome_partido` | STRING | cadastro, ou a sigla |

## `dim_uf`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_uf` | BIGINT | |
| `sigla_uf` | STRING | `SP` … |
| `nome_uf` | STRING | `São Paulo` … |
| `regiao` | STRING | `Sudeste` … |

## `dim_tipo_despesa`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_tipo_despesa` | BIGINT | |
| `codigo_subcota` | INT | |
| `tipo_despesa` | STRING | descrição mais recente da subcota |
| `codigo_especificacao_subcota` | INT | |
| `especificacao_despesa` | STRING | nula quando a subcota não tem especificação |

## `dim_fornecedor`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_fornecedor` | BIGINT | |
| `tipo_documento` | STRING | `CNPJ`, `CPF`, `Sem documento` |
| `documento_exibicao` | STRING | `00.000.000/0000-00` ou `***.456.789-**`; nulo sem documento |
| `cnpj` | STRING | 14 dígitos; nulo para CPF e sem documento |
| `nome_fornecedor` | STRING | nome mais frequente nas despesas |
| `situacao_portal` | STRING | `Encontrado`, `Não encontrado`, `Não consultado`, `Não se aplica` |
| `razao_social` | STRING | Portal |
| `nome_fantasia` | STRING | Portal |
| `possui_sancao` | BOOLEAN | CEIS, CNEP, CEPIM ou CEAF; nulo se não encontrado |
| `sancionado_ceis`, `sancionado_cnep`, `sancionado_cepim`, `sancionado_ceaf` | BOOLEAN | Portal |
| `possui_contratacao`, `possui_convenios`, `participante_licitacao`, `favorecido_transferencias`, `beneficiado_renuncia_fiscal` | BOOLEAN | Portal |
| `chave_natural` | STRING | técnica, oculta |

## `dim_autor_emenda`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_autor_emenda` | BIGINT | |
| `nome_autor` | STRING | como publicado |
| `grupo_emenda` | STRING | `Individual`, `Bancada`, `Comissão`, `Relator` |
| `tipo_autor` | STRING | `Deputado`, `Parlamentar não identificado`, `Relator`, `Bancada`, `Comissão`, `Sem informação` |
| `ligado_a_deputado` | BOOLEAN | |
| `motivo_sem_ligacao` | STRING | `não casou`, `ambíguo`, `não se aplica`; nulo se ligado |
| `chave_natural` | STRING | técnica, oculta |

## `dim_tipo_emenda`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_tipo_emenda` | BIGINT | |
| `tipo_emenda` | STRING | como publicado |
| `grupo_emenda` | STRING | `Individual`, `Bancada`, `Comissão`, `Relator` |

## `dim_funcao`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_funcao` | BIGINT | |
| `funcao` | STRING | |
| `subfuncao` | STRING | |

## `dim_localidade`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `sk_localidade` | BIGINT | |
| `localidade_gasto` | STRING | como publicado |
| `nivel_localidade` | STRING | `Múltiplo`, `Nacional`, `Estado`, `Município`, `Outro` |
| `sigla_uf_localidade` | STRING | nos níveis `Estado` e `Município` |

## `fat_despesas`

| Coluna | Tipo | Origem (`silver_camara.despesas`) |
|---|---|---|
| `chave_despesa` | STRING | `chave_despesa` |
| `sk_data_competencia` | INT | `ano`, `mes` → `AAAAMM01` |
| `sk_deputado` | BIGINT | `codigo_deputado` ou liderança |
| `sk_partido` | BIGINT | `sigla_partido` da linha |
| `sk_uf` | BIGINT | `sigla_uf` da linha |
| `sk_tipo_despesa` | BIGINT | `codigo_subcota`, `codigo_especificacao_subcota` |
| `sk_fornecedor` | BIGINT | documento e nome do fornecedor |
| `ano`, `mes` | INT | |
| `data_emissao` | DATE | |
| `numero_documento` | STRING | |
| `codigo_documento` | BIGINT | |
| `url_documento` | STRING | |
| `passageiro`, `trecho` | STRING | |
| `valor_documento`, `valor_glosa`, `valor_liquido`, `valor_restituicao` | DECIMAL(15,2) | |
| `_batch_id` | STRING | linhagem da Silver |

## `fat_emendas`

| Coluna | Tipo | Origem (`silver_transparencia.emendas`) |
|---|---|---|
| `chave_emenda` | STRING | `chave_emenda` |
| `sk_data_ano` | INT | `ano` → `AAAA0101` |
| `sk_deputado` | BIGINT | autor ligado, ou `-2` |
| `sk_autor_emenda` | BIGINT | `nome_autor` e grupo |
| `sk_tipo_emenda` | BIGINT | `tipo_emenda` |
| `sk_funcao` | BIGINT | `funcao`, `subfuncao` |
| `sk_localidade` | BIGINT | `localidade_gasto` |
| `ano` | INT | |
| `codigo_emenda`, `numero_emenda` | STRING | |
| `valor_empenhado`, `valor_liquidado`, `valor_pago`, `valor_resto_inscrito`, `valor_resto_cancelado`, `valor_resto_pago` | DECIMAL(15,2) | |
| `_batch_id` | STRING | linhagem da Silver |

## `ctl_quality_checks`

Mesmo esquema da `ctl_quality_checks` da Silver
(`specs/004-gastos-silver/contracts/silver-tables.md`). Valores de `verificacao` na Gold:
`unicidade`, `obrigatorias`, `integridade`, `conciliacao`, `privacidade`, `ligacao_autor`,
`contagem`.
