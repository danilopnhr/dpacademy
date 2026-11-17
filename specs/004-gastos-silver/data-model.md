# Data Model: Camada Silver do case gastos

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-17

Esquema físico em [contracts/silver-tables.md](./contracts/silver-tables.md). Aqui ficam as
entidades, a chave, a regra de versão, as colunas obrigatórias e as relações.

## Regras comuns

- Cada linha tem `_batch_id` (lote da Bronze de onde veio) e `_ingested_at` (momento da coleta
  desse lote).
- Só entram lotes com `status = 'succeeded'` em `ctl_ingestion_runs` da Bronze (FR-012).
- Texto vazio vira nulo. Valores monetários em `DECIMAL(15,2)`; datas em `DATE`.
- Nenhuma tabela tem CPF de deputado (FR-008).

## `silver_camara`

| Tabela | Chave | Versão (de onde vem cada linha) | Obrigatórias |
|---|---|---|---|
| `legislaturas` | `codigo_legislatura` | último lote `succeeded` do recurso | `codigo_legislatura`, `data_inicio` |
| `partidos` | `codigo_partido` | último lote `succeeded` do recurso | `codigo_partido`, `sigla_partido`, `nome_partido` |
| `deputados` | `codigo_deputado` | último lote `succeeded` do recurso | `codigo_deputado`, `nome_civil`, `nome_parlamentar` |
| `despesas` | `chave_despesa` (SHA-256 do `payload`) | por ano, último lote `succeeded` com `_origem = 'arquivo'` | `chave_despesa`, `ano`, `mes`, `nome_parlamentar`, `tipo_despesa`, `valor_documento`, `valor_liquido` |

Relações, verificadas só na Gold:

- `despesas.codigo_deputado` → `deputados.codigo_deputado` (nulo nas lideranças).
- `despesas.documento_fornecedor` → `silver_transparencia.pessoa_juridica.cnpj` quando
  `tipo_documento_fornecedor = 'CNPJ'`.
- `deputados.sigla_partido` → `partidos.sigla_partido`; `deputados.codigo_legislatura` →
  `legislaturas.codigo_legislatura`.

## `silver_transparencia`

| Tabela | Chave | Versão | Obrigatórias |
|---|---|---|---|
| `emendas` | `chave_emenda` (SHA-256 do `payload`) | por ano, último lote `succeeded` | `chave_emenda`, `ano`, `tipo_emenda`, `autor`, `valor_empenhado`, `valor_liquidado`, `valor_pago` |
| `pessoa_juridica` | `cnpj` | por CNPJ, resultado mais recente | `cnpj` (14 dígitos), `encontrado` |

Relações (Gold): `emendas.nome_autor` → deputado pelo nome normalizado; `pessoa_juridica.cnpj` ←
despesas.

## Ciclo de uma partição (despesas e emendas, por ano)

```text
Bronze: novo lote succeeded do ano ─► Silver compara _batch_id
   igual ───────────► ano pulado (nada muda)
   diferente ───────► prepara o ano ─► verificações ─┬─ passam ─► MERGE (insere, atualiza linhagem,
                                                     │            apaga o que sumiu do ano)
                                                     └─ falham ─► nada gravado; execução falha
```

## Controle de qualidade (`ctl_quality_checks`, um por lakehouse Silver)

Uma linha por execução, tabela e verificação:

- `unicidade`: linhas com chave repetida no conjunto preparado; passa com 0.
- `obrigatorias`: linhas com alguma coluna obrigatória nula; passa com 0.
- `contagem`: linhas da tabela depois do `MERGE`; sempre `passed`, serve de histórico.

Uma verificação `failed` faz o notebook levantar exceção depois de registrar o resultado, e o
orquestrador não segue para a etapa seguinte (FR-014).

## Mudança na Bronze (`bronze_camara.ctl_ingestion_runs`)

Coluna nova `source_hash STRING`: SHA-256 do CSV do arquivo anual em lotes `origem = 'arquivo'`;
nula nos outros. Um lote de arquivo com o mesmo hash do último `succeeded` do ano termina
`skipped` com `message = 'arquivo sem mudança'` e zero registros (research R2).
