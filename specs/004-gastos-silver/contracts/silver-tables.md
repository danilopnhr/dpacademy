# Contrato: tabelas da Silver do case gastos

Todas as tabelas são Delta, com as colunas abaixo mais `_batch_id STRING` e
`_ingested_at TIMESTAMP` (linhagem, research R6). "Origem" é o campo do `payload` da Bronze.
Valores: `DECIMAL(15,2)`. Texto vazio vira nulo.

## `silver_camara.legislaturas`

| Coluna | Tipo | Origem |
|---|---|---|
| `codigo_legislatura` | INT | `id` |
| `data_inicio` | DATE | `dataInicio` |
| `data_fim` | DATE | `dataFim` |

## `silver_camara.partidos`

| Coluna | Tipo | Origem |
|---|---|---|
| `codigo_partido` | INT | `id` |
| `sigla_partido` | STRING | `sigla` |
| `nome_partido` | STRING | `nome` |

## `silver_camara.deputados`

| Coluna | Tipo | Origem |
|---|---|---|
| `codigo_deputado` | INT | `id` |
| `nome_civil` | STRING | `nomeCivil` |
| `nome_parlamentar` | STRING | `ultimoStatus.nomeEleitoral` |
| `sigla_partido` | STRING | `ultimoStatus.siglaPartido` |
| `sigla_uf` | STRING | `ultimoStatus.siglaUf` |
| `codigo_legislatura` | INT | `ultimoStatus.idLegislatura` |
| `situacao` | STRING | `ultimoStatus.situacao` |
| `condicao_eleitoral` | STRING | `ultimoStatus.condicaoEleitoral` |
| `data_status` | DATE | `ultimoStatus.data` |
| `email` | STRING | `ultimoStatus.email` |
| `url_foto` | STRING | `ultimoStatus.urlFoto` |
| `sexo` | STRING | `sexo` |
| `data_nascimento` | DATE | `dataNascimento` |
| `data_falecimento` | DATE | `dataFalecimento` |
| `uf_nascimento` | STRING | `ufNascimento` |
| `municipio_nascimento` | STRING | `municipioNascimento` |
| `escolaridade` | STRING | `escolaridade` |

`cpf` não é lido (FR-008).

## `silver_camara.despesas`

Só `_origem = 'arquivo'`. Nomes de origem como no cabeçalho do CSV normalizado na Bronze.

| Coluna | Tipo | Origem |
|---|---|---|
| `chave_despesa` | STRING | SHA-256 do `payload` (hex) |
| `ano` | INT | `numAno` |
| `mes` | INT | `numMes` |
| `codigo_deputado` | INT | `ideCadastro` (nulo nas lideranças) |
| `numero_deputado_cota` | INT | `nuDeputadoId` |
| `nome_parlamentar` | STRING | `txNomeParlamentar` |
| `sigla_uf` | STRING | `sgUF` |
| `sigla_partido` | STRING | `sgPartido` |
| `codigo_legislatura` | INT | `codLegislatura` |
| `codigo_subcota` | INT | `numSubCota` |
| `tipo_despesa` | STRING | `txtDescricao` |
| `codigo_especificacao_subcota` | INT | `numEspecificacaoSubCota` |
| `especificacao_despesa` | STRING | `txtDescricaoEspecificacao` |
| `nome_fornecedor` | STRING | `txtFornecedor` |
| `documento_fornecedor` | STRING | `txtCNPJCPF`, só dígitos |
| `tipo_documento_fornecedor` | STRING | `CNPJ` (14 dígitos), `CPF` (11) ou nulo |
| `numero_documento` | STRING | `txtNumero` |
| `codigo_tipo_documento` | INT | `indTipoDocumento` |
| `data_emissao` | DATE | `datEmissao` (nula em ~3% das linhas) |
| `valor_documento` | DECIMAL(15,2) | `vlrDocumento` |
| `valor_glosa` | DECIMAL(15,2) | `vlrGlosa` |
| `valor_liquido` | DECIMAL(15,2) | `vlrLiquido` |
| `valor_restituicao` | DECIMAL(15,2) | `vlrRestituicao` |
| `numero_parcela` | INT | `numParcela` |
| `passageiro` | STRING | `txtPassageiro` |
| `trecho` | STRING | `txtTrecho` |
| `numero_lote` | BIGINT | `numLote` |
| `numero_ressarcimento` | STRING | `numRessarcimento` |
| `data_pagamento_restituicao` | DATE | `datPagamentoRestituicao` |
| `codigo_documento` | BIGINT | `ideDocumento` (`0` é marcador da fonte, não id) |
| `url_documento` | STRING | `urlDocumento` |

`cpf` e `nuCarteiraParlamentar` não são lidos.

## `silver_transparencia.emendas`

| Coluna | Tipo | Origem |
|---|---|---|
| `chave_emenda` | STRING | SHA-256 do `payload` (hex) |
| `codigo_emenda` | STRING | `codigoEmenda` (tem marcadores como `S/I`) |
| `ano` | INT | `ano` |
| `numero_emenda` | STRING | `numeroEmenda` |
| `tipo_emenda` | STRING | `tipoEmenda` |
| `autor` | STRING | `autor` |
| `nome_autor` | STRING | `nomeAutor` |
| `localidade_gasto` | STRING | `localidadeDoGasto` |
| `funcao` | STRING | `funcao` |
| `subfuncao` | STRING | `subfuncao` |
| `valor_empenhado` | DECIMAL(15,2) | `valorEmpenhado` |
| `valor_liquidado` | DECIMAL(15,2) | `valorLiquidado` |
| `valor_pago` | DECIMAL(15,2) | `valorPago` |
| `valor_resto_inscrito` | DECIMAL(15,2) | `valorRestoInscrito` |
| `valor_resto_cancelado` | DECIMAL(15,2) | `valorRestoCancelado` |
| `valor_resto_pago` | DECIMAL(15,2) | `valorRestoPago` |

## `silver_transparencia.pessoa_juridica`

| Coluna | Tipo | Origem |
|---|---|---|
| `cnpj` | STRING | `_cnpj` da Bronze (14 dígitos) |
| `encontrado` | BOOLEAN | `_resultado = 'encontrado'` |
| `razao_social` | STRING | `razaoSocial` |
| `nome_fantasia` | STRING | `nomeFantasia` |
| `favorecido_despesas` | BOOLEAN | `favorecidoDespesas` |
| `possui_contratacao` | BOOLEAN | `possuiContratacao` |
| `possui_convenios` | BOOLEAN | `convenios` |
| `favorecido_transferencias` | BOOLEAN | `favorecidoTransferencias` |
| `participante_licitacao` | BOOLEAN | `participanteLicitacao` |
| `emitiu_nfe` | BOOLEAN | `emitiuNFe` |
| `sancionado_ceis` | BOOLEAN | `sancionadoCEIS` |
| `sancionado_cnep` | BOOLEAN | `sancionadoCNEP` |
| `sancionado_cepim` | BOOLEAN | `sancionadoCEPIM` |
| `sancionado_ceaf` | BOOLEAN | `sancionadoCEAF` |
| `beneficiado_renuncia_fiscal` | BOOLEAN | `beneficiadoRenunciaFiscal` |
| `isento_imune_renuncia_fiscal` | BOOLEAN | `isentoImuneRenunciaFiscal` |
| `habilitado_renuncia_fiscal` | BOOLEAN | `habilitadoRenunciaFiscal` |

Nos não encontrados, só `cnpj`, `encontrado` e a linhagem são preenchidos.

## `ctl_quality_checks` (mesmo esquema nos dois lakehouses Silver)

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `run_id` | STRING | UUID da execução do notebook |
| `checked_at` | TIMESTAMP | momento da verificação (UTC) |
| `tabela` | STRING | nome da tabela Silver |
| `verificacao` | STRING | `unicidade`, `obrigatorias` ou `contagem` |
| `status` | STRING | `passed` ou `failed` |
| `linhas_com_problema` | BIGINT | linhas que violaram (0 em `contagem`) |
| `linhas_tabela` | BIGINT | linhas do conjunto preparado (`unicidade`, `obrigatorias`) ou da tabela depois do `MERGE` (`contagem`) |
| `detalhe` | STRING | partições processadas (ex.: `anos=2025,2026`) e até 5 chaves de exemplo quando falha |
| `environment` | STRING | `dev` ou `prd`, do nome do workspace |

## Mudança na `bronze_camara.ctl_ingestion_runs`

Nova coluna `source_hash STRING` (research R2), acrescentada com `ALTER TABLE ... ADD COLUMNS`
quando ausente. O contrato da 003 (`specs/003-gastos-bronze-ingestion/contracts/bronze-tables.md`)
recebe uma nota apontando para cá.
