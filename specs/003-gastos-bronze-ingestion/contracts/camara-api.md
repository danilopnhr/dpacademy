# Contrato: dependência da API de Dados Abertos da Câmara dos Deputados

Consultado em 2026-11-12. Se a fonte mudar, este é o arquivo a revisar primeiro.

| Item | Valor |
|---|---|
| Base | `https://dadosabertos.camara.leg.br/api/v2` |
| Autenticação | nenhuma |
| Limite | não documentado; o cliente usa no mínimo 0,25 s entre requisições, uma por vez |
| Paginação | `pagina` (desde 1) e `itens` (até 100); resposta traz `links[]` com `rel: next` enquanto houver páginas |
| Total | cabeçalho `X-Total-Count` |
| Formato | `{"dados": [ … ], "links": [ … ]}`; detalhe por id devolve `{"dados": { … }}` |
| Header enviado | `Accept: application/json` |

## Endpoints usados

| Endpoint | Parâmetros | Uso | Tabela |
|---|---|---|---|
| `GET /legislaturas` | `itens=100` | cadastro inteiro | `legislaturas` |
| `GET /partidos` | `itens=100` | cadastro inteiro | `partidos` |
| `GET /deputados` | `idLegislatura`, `itens=100` | só fila de ids (não gravado) | — |
| `GET /deputados/{id}` | — | detalhe de cada deputado da fila | `deputados` |
| `GET /deputados/{id}/despesas` | `ano`, `mes`, `itens=100` | despesas da carga recorrente | `despesas` (`_origem = api`) |

Campos principais de uma despesa da API (amostra real de 2026-11-12): `ano`, `mes`,
`tipoDespesa`, `codDocumento`, `tipoDocumento`, `dataDocumento`, `numDocumento`,
`valorDocumento`, `urlDocumento`, `nomeFornecedor`, `cnpjCpfFornecedor`, `valorLiquido`,
`valorGlosa`, `numRessarcimento`, `codLote`, `parcela`.

## Arquivo anual da cota parlamentar

| Item | Valor |
|---|---|
| URL | `https://www.camara.leg.br/cotas/Ano-<AAAA>.csv.zip` |
| Conteúdo | um CSV `Ano-<AAAA>.csv`, separador `;`, UTF-8 com BOM, cabeçalho na 1ª linha, 32 colunas |
| Tamanho | 6 a 9 MB compactado; 46 a 72 MB descompactado |
| Atualização | diária (arquivo do ano corrente) |
| Cópia local | `bronze_camara/Files/_landing/cotas/Ano-<AAAA>.csv.zip`, sobrescrita a cada carga |

Colunas: `txNomeParlamentar`, `cpf`, `ideCadastro`, `nuCarteiraParlamentar`, `nuLegislatura`,
`sgUF`, `sgPartido`, `codLegislatura`, `numSubCota`, `txtDescricao`, `numEspecificacaoSubCota`,
`txtDescricaoEspecificacao`, `txtFornecedor`, `txtCNPJCPF`, `txtNumero`, `indTipoDocumento`,
`datEmissao`, `vlrDocumento`, `vlrGlosa`, `vlrLiquido`, `numMes`, `numAno`, `numParcela`,
`txtPassageiro`, `txtTrecho`, `numLote`, `numRessarcimento`, `datPagamentoRestituicao`,
`vlrRestituicao`, `nuDeputadoId`, `ideDocumento`, `urlDocumento`.

## Erros tratados

| Código | Tratamento |
|---|---|
| 429 | retentativa com espera (respeita `Retry-After`) |
| 5xx, timeout, conexão | retentativa com espera exponencial (15, 30, 60, 120, 240 s) |
| 404 em `/deputados/{id}` | falha do lote (id da fila sumiu: inconsistência da fonte) |
| outros 4xx | falha imediata com o código e o corpo truncado em 300 caracteres |
| arquivo anual 404 | ano sem arquivo: zero registros e aviso, status `succeeded` |

## Fora do escopo desta feature

`/votacoes`, `/proposicoes`, `/eventos`, `/orgaos`, frentes e presenças.
