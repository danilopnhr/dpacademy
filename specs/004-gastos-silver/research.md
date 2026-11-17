# Research: Camada Silver do case gastos

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-17

## R1. Origem das despesas: arquivo anual × API (2026-11-17, prd, só leitura)

Base: arquivo Ano-2026 carregado em 2026-11-16 14:59 UTC (125.528 linhas); API de 09, 10 e 11/2026
da execução agendada de 2026-11-17 (16.518 linhas). Cruzamento por `ideDocumento` (arquivo) =
`codDocumento` (API), excluindo `ideDocumento = '0'`.

### Achados

1. `ideDocumento = '0'` é um marcador, não um id (detalhe em R4). Passagens aéreas (SIGEPA)
   repetem o mesmo `ideDocumento` em até 9 linhas (trechos e passageiros). O `ideDocumento`
   sozinho não é chave.
2. Casados (14.875): mesmo mês nas duas origens (1 exceção), |valor líquido| igual em ~99% e
   `valorDocumento` igual. **A API inverte o sinal do valor líquido**: 14.733 positivos no arquivo
   vêm negativos na API, e as 52 compensações negativas do arquivo vêm positivas. Soma: arquivo
   +R$ 21,05 mi, API −R$ 20,97 mi.
3. Só na API (1.644): 912 com `codDocumento` em GUID (sem id numérico, muitos em pares +x/−x de
   cancelamento), 731 numéricos (prováveis documentos ainda não publicados no arquivo do dia
   anterior) e 1 sem documento. Soma líquida −R$ 127 mil, mas R$ 2,8 mi em valor absoluto.
4. Só no arquivo (82, meses 9–11): quase todos despesas de liderança (`ideCadastro` vazio), que a
   API por deputado não devolve.

**Decisão**: a Silver de despesas usa só `_origem = 'arquivo'`. O arquivo é a origem mais completa
(inclui lideranças), tem o sinal correto e ids numéricos, custa ~20 s por ano e absorve as
republicações; a API só é ~1 dia mais recente. A coleta pela API sai da rotina diária e continua
disponível por disparo manual (`origem=api`).
**Alternativas rejeitadas**: API como oficial (sinal invertido, ids GUID, sem lideranças);
conciliar as duas origens (não há chave comum para os GUIDs e a regra seria frágil).

## R2. Detecção de mudança nos arquivos anuais

Cabeçalhos HTTP em 2026-11-17: todos os arquivos de 2019 a 2026 têm `last-modified` do mesmo dia,
entre 06:39:05 e 06:39:19 UTC, com `etag` no formato `"<mtime>-<tamanho>"` do nginx. A Câmara
regera todos os arquivos todos os dias, mesmo os de anos fechados.

**Decisão**: baixar o zip de cada ano (6 a 9 MB, poucos segundos), calcular o SHA-256 do CSV
descompactado e comparar com o hash do último lote `succeeded` daquele ano. Igual: o lote termina
`skipped` com a mensagem `arquivo sem mudança` e não grava linhas. Diferente: grava como hoje. O
hash vai numa coluna nova `source_hash` em `ctl_ingestion_runs` da `bronze_camara`; os lotes
anteriores a esta feature não têm hash, então a primeira execução de cada ano grava uma vez.
**Por que o CSV e não o zip**: um zip regerado pode mudar só pelos metadados internos (datas),
com o mesmo conteúdo.
**Alternativas rejeitadas**: `last-modified`/`etag` (mudam todo dia); tamanho do arquivo (uma
correção de valor pode manter o tamanho); recarregar todos os anos todo dia (1,7 mi de linhas por
noite numa Bronze append-only, cerca de 600 mi por ano).

## R3. Horário e ordem da rotina diária

- A Câmara regera os arquivos por volta das 06:39 UTC (03:39 em Brasília). A agenda atual da
  Câmara (05:00) é posterior; uma agenda única à 01:00 pegaria o arquivo do dia anterior.
- O Portal tem limite maior das 00:00 às 05:59 (research R3 da 003). Os fornecedores rodam 15.000
  consultas em ~70 min nesse ritmo; a fila de produção zera por volta de 2026-11-21, e depois cada
  noite tem só os CNPJs novos.

**Decisão**: `pl-010-orq-gastos-diario` às **04:00** (Brasília), nesta ordem:

1. Bronze da Câmara: cadastros e despesas pelo arquivo (só anos alterados), ~10 a 15 min.
2. Bronze do Portal: emendas e fornecedores, até ~75 min enquanto durar a fila. Roda depois da
   Câmara em qualquer resultado dela (`Completed`) e já enxerga os CNPJs novos do arquivo do dia.
3. Silver da Câmara, só se a Bronze da Câmara terminou com sucesso.
4. Silver do Portal, só se a Bronze do Portal terminou com sucesso.

Fim previsto por volta das 06:00 enquanto durar a fila de fornecedores e das 04:45 depois.
**Alternativas rejeitadas**: Portal primeiro à 01:00 e Câmara depois (a Câmara rodaria antes da
regeneração); duas agendas separadas (concorrência de sessões Spark no Trial e sem dependência
entre Bronze e Silver).

## R4. Chave das tabelas da Silver

Perfil em dev, depois da recarga de 2026-11-17 (1.686.374 despesas no último lote de cada ano):

- Despesas: nenhuma linha idêntica a outra. `ideDocumento` repete em 209.878 linhas (inclusive
  entre anos); `ideDocumento = '0'` marca 107.524 linhas de telefonia (74.307) e serviços postais
  (33.217). Mesmo combinando documento, deputado, ano, mês, parcela, passageiro, trecho, número e
  valores, sobram 91 linhas repetidas.
- Emendas (55.044 no último lote de cada ano): nenhuma linha idêntica; `codigoEmenda` usa
  marcadores como `REL. GERAL` e `S/I`; código + tipo + localidade repete em 241 linhas, e
  acrescentando função e subfunção ainda sobram 18.
- Cadastros: um registro por `id` no último lote (57, 38 e 929). Fornecedores: um registro por
  `_cnpj` (68.057), sem CNPJ consultado duas vezes.

**Decisão**: despesas e emendas têm como chave o SHA-256 do `payload` (`chave_despesa`,
`chave_emenda`). Funciona porque a Silver trata cada ano como foto completa (R6): uma correção na
fonte troca a linha antiga pela nova. Os códigos da fonte ficam como atributos. Cadastros usam o
`id` (`codigo_<entidade>`); fornecedores, o CNPJ em dígitos. Como não há linhas idênticas, a
regra de linhas idênticas do SC-001 não descarta nada; se um dia aparecerem, a verificação de
unicidade falha e a regra é revista.
**Alternativas rejeitadas**: chave composta de campos (sempre sobra repetição, e um campo novo na
fonte quebraria a regra); número da linha no arquivo (muda quando a Câmara reordena).

## R5. Formatos e conteúdo

- Arquivo: valores com ponto decimal (`1467`, `-108.18`), nenhum com vírgula; datas
  `AAAA-MM-DDTHH:MM:SS`; `datEmissao` vazia em 54.501 linhas; `txtCNPJCPF` formatado, com 14
  dígitos (1.671.851) ou 11 (CPF de fornecedor pessoa física, 14.523); `ideCadastro` vazio em
  6.064 linhas (lideranças); o arquivo também tem a coluna `cpf` do deputado.
- Portal: valores em texto `1.200.000,00`; `ano` numérico.
- Deputados: `ultimoStatus` aninhado; tem `cpf`.
- Fornecedores: 89 dos 33.967 CNPJs encontrados em dev vêm com `razaoSocial` e `nomeFantasia`
  vazios, mas com os indicadores preenchidos (achado pela verificação de obrigatórias na primeira
  carga, 2026-11-17). Razão social fica opcional; a Gold pode usar o nome do fornecedor das
  despesas.

**Decisão**: valores `DECIMAL(15,2)`, convertidos por fonte (arquivo: texto com ponto; Portal:
remove `.` e troca `,` por `.`); texto vazio vira nulo; conversão que falha vira nulo e é pega pela
verificação de obrigatórias. Datas como `DATE`. Documento do fornecedor só com dígitos e o tipo
(`CNPJ` com 14 dígitos, `CPF` com 11). O CPF do deputado não entra em nenhuma tabela: nem a coluna
`cpf` do arquivo de despesas, nem a do detalhe do deputado.

## R6. Carga incremental e remoção de linhas

**Decisão**: carga por partição de versão, sem marca d'água separada:

- Despesas e emendas: para cada ano, o lote de referência é o último `succeeded` na Bronze. Se o
  `_batch_id` da Silver para aquele ano já é esse, o ano é pulado. Senão, um `MERGE` por chave
  restrito ao ano: insere as novas, atualiza a linhagem das que continuam e apaga as que sumiram
  (`WHEN NOT MATCHED BY SOURCE AND ano = <ano> THEN DELETE`).
- Cadastros: o último lote `succeeded` de cada recurso; o mesmo `MERGE` com remoção na tabela toda.
- Fornecedores: as linhas da Bronze com `_ingested_at` maior que o máximo já presente na Silver
  entram por `MERGE` por CNPJ (só inserção e atualização, nunca remoção).
- As verificações de qualidade rodam sobre o conjunto preparado **antes** do `MERGE`; se falharem,
  nada é gravado (FR-014). Depois do `MERGE`, a contagem da tabela é registrada.

**Alternativas rejeitadas**: `replaceWhere` por ano (a constituição pede `MERGE`, e ele não
preserva a linhagem das linhas que não mudaram); sobrescrever a tabela inteira a cada execução
(reprocessa 1,7 mi de linhas toda noite).

## R7. Orquestração no Fabric

**Decisão**: o `pl-010-orq-gastos-diario` chama os notebooks diretamente (atividades de notebook),
com uma retentativa de 5 min em cada uma, como os pipelines da 003, e uma atividade Fail no fim
quando qualquer etapa falhar. Os pipelines por fonte continuam existindo para disparo manual, sem
agenda; no da Câmara, a atividade de despesas passa a usar `origem=arquivo`.
**Alternativas rejeitadas**: chamar os pipelines por fonte com a atividade Invoke Pipeline (exige
conexão própria e referência entre pipelines na publicação do `fabric-cicd`, mais um ponto de
falha sem ganho); um pipeline por camada (duas agendas de novo).

## R8. Nomes e fluxo Git

- O validador aceita um único termo no `<assunto>`, então os notebooks são
  `nb-util-010-silver-camara-comum`, `nb-full-020-silver-camara-cadastros`,
  `nb-incr-030-silver-camara-despesas`, `nb-util-010-silver-transparencia-comum`,
  `nb-incr-020-silver-transparencia-emendas` e `nb-incr-030-silver-transparencia-fornecedores`.
- Fluxo igual ao da 003: lakehouses e notebooks criados no `ws-dev-dpacademy` e levados ao
  repositório pelo commit da Git integration em `dev`; documentos, `ci/` e `tests/` editados na
  branch `004-gastos-silver`, que recebe `dev` antes do PR.
- `ci/parameter.yml` ganha as entradas dos GUIDs de dev de `silver_camara` e
  `silver_transparencia` (lakehouse padrão dos notebooks novos).
- Os notebooks da Silver leem a Bronze pelo nome qualificado (`bronze_camara.despesas`), que
  funciona no mesmo workspace (conferido nas sessões de diagnóstico da 003 e desta pesquisa).

## R9. Capacidade

O Trial permite uma sessão Spark por vez. A rotina roda as etapas em sequência; cargas manuais e
sessões de diagnóstico não podem coincidir com ela (04:00 a ~06:00 em produção). A carga inicial
da Silver em produção é feita uma vez à mão, fora desse horário.
