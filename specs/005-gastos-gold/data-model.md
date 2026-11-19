# Data Model: Camada Gold e modelo semântico do case gastos

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-18

Esquema físico em [contracts/gold-tables.md](./contracts/gold-tables.md); modelo semântico em
[contracts/sm-gastos.md](./contracts/sm-gastos.md). Aqui ficam o diagrama, os grãos, as chaves, as
regras de membro e as verificações.

## Estrela

```text
                 dim_data ◄──────────────┐                       ┌──────► dim_data
                 dim_deputado ◄──────────┤                       ├──────► dim_deputado (-2 sem ligação)
                 dim_partido ◄───────────┤                       ├──────► dim_autor_emenda
                 dim_uf ◄────────────────┼── fat_despesas        fat_emendas ──┼──────► dim_tipo_emenda
                 dim_tipo_despesa ◄──────┤                       ├──────► dim_funcao
                 dim_fornecedor ◄────────┘                       └──────► dim_localidade
```

`dim_data` e `dim_deputado` são compartilhadas pelos dois fatos (dimensões conformadas): é o que
permite comparar cota e emendas do mesmo deputado no mesmo ano.

## Regras comuns

- Reconstrução total a cada execução, verificações antes de gravar (research R1).
- `sk_<entidade> BIGINT` = `xxhash64` da chave natural com prefixo (R2). Membros reservados em toda
  dimensão, exceto `dim_data`: `-1` "Não informado" e `-2` "Não se aplica".
- Toda tabela tem `_carregado_em TIMESTAMP` (início da execução, UTC); os fatos também têm
  `_batch_id` (o lote da Silver de onde a linha veio).
- Texto em português, `snake_case`; valores `DECIMAL(15,2)`; nenhuma coluna com CPF de deputado ou
  CPF completo de fornecedor.

## Fatos

| Fato | Grão | Chave | Chaves estrangeiras | Medidas físicas |
|---|---|---|---|---|
| `fat_despesas` | uma linha por despesa da `silver_camara.despesas` | `chave_despesa` | `sk_data_competencia`, `sk_deputado`, `sk_partido`, `sk_uf`, `sk_tipo_despesa`, `sk_fornecedor` | `valor_documento`, `valor_glosa`, `valor_liquido`, `valor_restituicao` |
| `fat_emendas` | uma linha por emenda × tipo × localidade da `silver_transparencia.emendas` | `chave_emenda` | `sk_data_ano`, `sk_deputado`, `sk_autor_emenda`, `sk_tipo_emenda`, `sk_funcao`, `sk_localidade` | `valor_empenhado`, `valor_liquidado`, `valor_pago`, `valor_resto_inscrito`, `valor_resto_cancelado`, `valor_resto_pago` |

Atributos degenerados: `fat_despesas` guarda `ano`, `mes`, `data_emissao`, `numero_documento`,
`codigo_documento`, `url_documento`, `passageiro`, `trecho`; `fat_emendas` guarda `ano`,
`codigo_emenda`, `numero_emenda`.

## Dimensões

| Dimensão | Chave natural (antes do hash) | Origem | Obrigatórias |
|---|---|---|---|
| `dim_data` | `AAAAMMDD` (o próprio `sk_data`) | gerada, 2019-01-01 a 31/12 do ano corrente | `sk_data`, `data`, `ano`, `mes` |
| `dim_deputado` | `D:<codigo_deputado>` ou `L:<nome normalizado>` | `deputados` ∪ `despesas` | `sk_deputado`, `nome_parlamentar`, `tipo_membro` |
| `dim_partido` | `P:<sigla>` | `despesas`, `deputados`, `partidos` | `sk_partido`, `sigla_partido`, `nome_partido` |
| `dim_uf` | `U:<sigla>` | lista fixa (27 UFs) | `sk_uf`, `sigla_uf`, `nome_uf`, `regiao` |
| `dim_tipo_despesa` | `T:<codigo_subcota>:<codigo_especificacao_subcota>` | `despesas` | `sk_tipo_despesa`, `tipo_despesa` |
| `dim_fornecedor` | `J:<cnpj>`, `F:<cpf mascarado>\|<nome normalizado>`, `S:<nome normalizado>` | `despesas` + `pessoa_juridica` | `sk_fornecedor`, `tipo_documento`, `nome_fornecedor`, `situacao_portal` |
| `dim_autor_emenda` | `A:<grupo>:<nome normalizado>` | `emendas` + `dim_deputado` | `sk_autor_emenda`, `nome_autor`, `tipo_autor` |
| `dim_tipo_emenda` | `E:<tipo_emenda>` | `emendas` | `sk_tipo_emenda`, `tipo_emenda`, `grupo_emenda` |
| `dim_funcao` | `FN:<funcao>:<subfuncao>` | `emendas` | `sk_funcao`, `funcao` |
| `dim_localidade` | `LC:<localidade_gasto>` | `emendas` | `sk_localidade`, `localidade_gasto`, `nivel_localidade` |

Regras de cada membro:

- **Deputado**: atributos do cadastro quando `no_cadastro`; senão, da linha mais recente das
  despesas. Lideranças: `e_lideranca = true`, `codigo_deputado` nulo. O membro `-2` é usado nas
  emendas sem autor ligado.
- **Partido**: nome do cadastro de partidos; se ausente, igual à sigla.
- **Fornecedor**: nome mais frequente nas despesas (empate: mais recente); `situacao_portal` de
  `pessoa_juridica` (`Encontrado`, `Não encontrado`), `Não consultado` se o CNPJ não está lá,
  `Não se aplica` para CPF e sem documento; `documento_exibicao` = CNPJ formatado ou CPF mascarado.
- **Autor de emenda**: `grupo` vem do tipo da emenda (`Individual`, `Bancada`, `Comissão`,
  `Relator`); nas individuais, ligação ao deputado por nome normalizado com candidato único
  (research R6).
- **Localidade**: `nivel_localidade` = `Múltiplo`, `Nacional`, `Estado` (`<NOME> (UF)`) ou
  `Município` (`<NOME> - XX`); `sigla_uf_localidade` derivada nos dois últimos, nula nos outros.

Uma linha de fato com chave da fonte vazia (ex.: despesa sem fornecedor, emenda sem função) aponta
para `-1`.

## Ciclo de uma execução

```text
lê a Silver ─► monta dimensões ─► monta fatos ─► verificações (unicidade, obrigatórias,
integridade, conciliação, privacidade, ligação) ─┬─ todas passam ─► grava dimensões, depois fatos
                                                 │                  (overwrite, V-Order) ─► contagem
                                                 └─ alguma falha ─► registra e levanta exceção;
                                                                    nenhuma tabela gravada
```

## Controle de qualidade (`gold_gastos.ctl_quality_checks`)

Mesmo esquema da Silver (contrato da 004). Verificações: `unicidade`, `obrigatorias`,
`integridade` (uma linha por fato × chave estrangeira), `conciliacao` (uma por fato), `privacidade`,
`ligacao_autor` (informativa) e `contagem`. `detalhe` traz, quando falha, até 5 exemplos (ano com
diferença, chave órfã) e, em `ligacao_autor`, o percentual ligado.
