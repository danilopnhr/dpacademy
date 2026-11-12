# Data Model: Ingestão Bronze do case gastos

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-12

Esquema físico das tabelas em [contracts/bronze-tables.md](./contracts/bronze-tables.md). Aqui
ficam as entidades, a chave natural de cada uma (usada pela Silver para deduplicar), as
relações e as regras de validação da Bronze.

## Entidades da Câmara (`bronze_camara`)

| Entidade | Tabela | Chave natural (no `payload`) | Origem | Volume |
|---|---|---|---|---|
| Legislatura | `legislaturas` | `id` | API `/legislaturas` | 57 |
| Partido | `partidos` | `id` | API `/partidos` | ~20 |
| Deputado | `deputados` | `id` | API `/deputados/{id}` (fila: `/deputados?idLegislatura=56,57`) | ~1.200 |
| Despesa da cota | `despesas` | arquivo: `ideDocumento`; API: `codDocumento` (com `ano`, `mes`, `parcela` e deputado) | arquivo anual ou API | ~1,27 mi (2019–2026) |

Relações (resolvidas na Silver):

- Despesa → Deputado: arquivo `ideCadastro` (vazio em despesas de liderança) ou `nuDeputadoId`;
  na API, o `id` do deputado vai em `_recorte`.
- Despesa → Fornecedor: `txtCNPJCPF` (arquivo) ou `cnpjCpfFornecedor` (API), quando tem 14
  dígitos.
- Deputado → Partido: `ultimoStatus.siglaPartido` (detalhe do deputado).
- Deputado → Legislatura: `ultimoStatus.idLegislatura` e a legislatura da fila em `_recorte`.

## Entidades do Portal da Transparência (`bronze_transparencia`)

| Entidade | Tabela | Chave natural (no `payload`) | Origem | Volume |
|---|---|---|---|---|
| Emenda parlamentar | `emendas` | `codigoEmenda` | API `/emendas?ano=` | a medir (quickstart §5) |
| Pessoa jurídica (fornecedor) | `pessoa_juridica` | `cnpj` | API `/pessoa-juridica?cnpj=` | ~68 mil |

Relações (resolvidas na Silver ou na Gold):

- Emenda → Deputado: pelo nome do autor (`autor`/`nomeAutor`). Não há id comum entre as fontes;
  o casamento por nome normalizado é trabalho da Gold.
- Pessoa jurídica ← Despesa: pelo CNPJ.

## Controle (`ctl_ingestion_runs`, um por lakehouse)

Uma linha por lote. Estados:

```text
running ──► succeeded
   │
   ├──────► failed     (erro após retentativas, chave inválida, ou stale após 6 h)
   └──────► skipped    (outro lote running do mesmo recurso)
```

- `running` é gravado antes da primeira requisição; o estado final é gravado com `MERGE` pelo
  `run_id` ao terminar.
- Um lote `failed` nunca tem linhas na tabela de dados (append só no sucesso, research R8).
- `records_written` de um lote `succeeded` MUST ser igual a `records_collected`.

## Regras de validação na Bronze

- Todo registro tem `payload` não nulo e JSON válido, exceto `pessoa_juridica` com
  `_resultado = 'nao_encontrado'`, em que `payload` pode ser nulo.
- Todo registro tem `_ingested_at`, `_source_endpoint`, `_batch_id`, `_origem` e `_recorte`.
- A chave natural da entidade existe no `payload`; um registro da API sem a chave aborta o lote
  como `failed` (sinal de mudança de contrato da fonte). Linhas do arquivo anual sem
  `ideDocumento` são aceitas e contadas num aviso.
- Unicidade, nulos e integridade referencial não são verificados na Bronze; começam na Silver
  (Princípio V).

## Versões e deduplicação

A Bronze é append-only: recarregar uma janela grava uma nova versão de cada registro com outro
`_batch_id`. A Silver escolhe, por chave natural, a versão de maior `_ingested_at`; para
despesas, quando a mesma despesa vem das duas origens, a versão mais recente vence
independentemente da origem.
