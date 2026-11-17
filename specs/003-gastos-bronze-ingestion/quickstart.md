# Quickstart: validar a ingestão Bronze do case gastos

Roteiro para provar que a feature funciona de ponta a ponta em `ws-dev-dpacademy`. Os nomes e
parâmetros estão em [contracts/notebook-parameters.md](./contracts/notebook-parameters.md); as
tabelas em [contracts/bronze-tables.md](./contracts/bronze-tables.md).

## 0. Pré-requisitos

- Workspace `ws-dev-dpacademy` na capacidade Trial, conectado à branch `dev` (feature 002).
- Lakehouses `bronze_camara` e `bronze_transparencia` criados.
- Chave do Portal da Transparência cadastrada em https://portaldatransparencia.gov.br/api-de-dados
  (conta gov.br), gravada **à mão** em `bronze_transparencia/Files/_secrets/transparencia_api_key`
  (só o valor, sem quebra de linha). Necessária a partir do §5.
- Localmente: Python 3.11 e `pytest`.

## 1. Testes unitários dos clientes (local, sem rede)

```powershell
pytest tests/unit -q
```

Esperado: todos verdes, cobrindo paginação (link `next` da Câmara; lista vazia do Portal),
retentativa em 429/5xx com `Retry-After`, falha imediata em 401/403 sem a chave na mensagem,
ritmo por faixa de horário do Portal, conversão de linha CSV em JSON e "não encontrado" de PJ.

## 2. Cadastros da Câmara (US1)

Rodar `nb-full-030-bronze-camara-cadastros` com os padrões.

```sql
SELECT recurso, status, records_collected, records_written, expected_total
FROM bronze_camara.ctl_ingestion_runs ORDER BY started_at DESC LIMIT 3;
```

Esperado: 3 lotes `succeeded`; `deputados` com ~1.200 registros e `records_written =
records_collected`; tempo total < 20 min.

## 3. Histórico de despesas pelo arquivo (US1, SC-001, SC-003)

1. Rodar `nb-incr-040-bronze-camara-despesas` com `origem=arquivo`, `anos=2024`.
2. Conferir contra a tabela de [research.md R2](./research.md#r2-volume-da-câmara-medido-nos-arquivos-anuais-em-2026-11-12):

```sql
SELECT get_json_object(payload,'$.numAno') AS ano, COUNT(*) AS despesas,
       ROUND(SUM(CAST(REPLACE(get_json_object(payload,'$.vlrLiquido'),',','.') AS DOUBLE)),2) AS liquido
FROM bronze_camara.despesas WHERE _origem='arquivo'
GROUP BY 1;
```

   Esperado: 173.961 despesas e ~211,4 mi em 2024 (o arquivo do ano corrente cresce a cada dia).
3. Rodar de novo o mesmo ano: novo lote `succeeded`, o lote anterior continua na tabela com
   outro `_batch_id` (cenário 2 da US1).
4. Rodar `anos=2019,2020,2021,2022,2023,2025,2026`. Esperado: 7 lotes, total da Câmara
   (cadastros + 8 anos) em menos de 2 h somadas.

## 4. Despesas recorrentes pela API (US2)

Rodar `nb-incr-040-bronze-camara-despesas` com os padrões (`origem=api`).

Esperado: 3 lotes (mês corrente e dois anteriores) `succeeded`; para cada um,
`records_collected` = soma dos `X-Total-Count` (`expected_total`). Repetir com
`meses=<mês passado>` para simular recuperação de um mês perdido.

## 5. Portal: confirmações com a chave e emendas (US3, SC-002)

1. Chamada avulsa (num notebook de rascunho, sem imprimir a chave) para confirmar:
   - tamanho da página de `/emendas?ano=2024&pagina=1`;
   - resposta de `/pessoa-juridica?cnpj=00000000000000` (CNPJ inexistente);
   - que 0,7 s de dia não gera 429 em 200 chamadas seguidas.
   Registrar os achados em [contracts/transparencia-api.md](./contracts/transparencia-api.md).
2. Rodar `nb-incr-030-bronze-transparencia-emendas` com `anos=2024`. Esperado: lote
   `succeeded`, `records_written = records_collected`.
3. Renomear temporariamente o arquivo da chave e rodar de novo. Esperado: lote `failed` em
   segundos, `message` = "chave da API ausente ou inválida", zero registros. Restaurar o arquivo.

## 6. Fornecedores (US4, SC-004)

1. Rodar `nb-incr-040-bronze-transparencia-fornecedores` com `limite=1000`.
2. Conferir que a fila diminuiu 1.000 e que existem 2 lotes de 500:

```sql
SELECT _resultado, COUNT(*) FROM bronze_transparencia.pessoa_juridica GROUP BY 1;
```

3. Rodar de novo com `limite=1000`: nenhum CNPJ repetido (cenário 3 da US4).
4. Carga completa (~68 mil): rodar de madrugada, com os padrões, em produção ou em dev
   manualmente; acompanhar até a fila zerar antes de 2026-11-30.

## 7. Registro de execuções e concorrência (US5)

- Disparar duas vezes seguidas `nb-full-030-bronze-camara-cadastros`: a segunda termina com os
  lotes `skipped`.
- Conferir que toda execução dos passos anteriores aparece em `ctl_ingestion_runs` com status
  correto (SC-007).

## 8. Segredo fora do código (SC-008)

```powershell
git grep -n -F "<valor da chave>" $(git rev-list --all)
```

Esperado: nenhum resultado. Conferir também a saída das células dos notebooks executados e a
coluna `message` de `ctl_ingestion_runs`.

## Registro da validação

### 2026-11-13: US1 (cadastros e histórico de despesas), `ws-dev-dpacademy`

- **Cadastros** (§2): `legislaturas` 57, `partidos` 38 distintos (62 registros somando as
  legislaturas 56 e 57) e `deputados` 929; 949 requisições, nenhuma retentativa; 5,7 min.
- **Despesas pelo arquivo** (§3): os 8 anos conferem exatamente com o arquivo do dia, em contagem e
  em valor líquido. 2019: 289.832; 2020: 167.144; 2021: 155.274; 2022: 148.193; 2023: 173.515;
  2024: 173.961 (R$ 211.437.069,03); 2025: 170.589; 2026: 123.968. São 1.402.476 despesas e
  68.043 CNPJs distintos. Cada ano leva de 12 a 25 s quando a fonte responde; cadastros e
  histórico somam menos de 10 min de execução útil (SC-003).
- **Recarga** (cenário 2 da US1): 2024 carregado duas vezes, com dois `_batch_id`, e a versão
  anterior preservada.
- **Instabilidade da fonte**: `www.camara.leg.br` ficou inacessível a partir do Fabric por cerca
  de 75 min (2026-11-13, das 00:54 às 02:11 UTC). Os lotes de 2019 e 2020 terminaram `failed` após
  6 tentativas, sem dados parciais, e foram recarregados depois só com `anos=2019,2020` (FR-008).
  Na operação diária, rodar de novo um lote `failed` antes de tratá-lo como perda.
- **Republicação**: a Câmara republicou os arquivos de 2019 e 2020 entre 12 e 13/11 (research R2).

### 2026-11-13: US2 (despesas pela API e pipeline), `ws-dev-dpacademy`

- **Janela padrão** (§4): 3 lotes (09, 10 e 11/2026), cada um com `records_collected =
  expected_total` (7.249, 7.049 e 874); 648 deputados por mês, cerca de 5 min por mês, nenhuma
  retentativa HTTP. A recuperação de um mês específico (`meses=2026-09`) também funcionou.
- **Registro sem `codDocumento`**: em 09/2026, uma passagem aérea de missão oficial ("Recibos/Outros",
  sem lote, sem link de nota). Na primeira execução o lote falhou pela regra de chave obrigatória;
  a regra mudou para gravar e avisar (data-model.md), e o mês foi recarregado.
- **Pipeline**: a primeira execução falhou ao abrir a sessão da 2ª atividade
  (`TooManyRequestsForCapacity`: o Trial ainda liberava a sessão da 1ª). Por isso há uma
  retentativa de 5 min em cada atividade.
- **API × arquivo**: as duas origens divergem em contagem e no sinal do valor líquido (pendência
  registrada em data-model.md para a Silver).

- **Execução verde**: com a regra corrigida e uma retentativa por atividade, o pipeline rodou à mão de ponta a ponta com sucesso em 21,8 min (cadastros + 3 meses pela API).

### 2026-11-13: US3 (emendas do Portal), `ws-dev-dpacademy`

- **Confirmações com a chave** (§5.1): 15 emendas por página; CNPJ inexistente devolve HTTP 200
  com corpo vazio; `/pessoa-juridica` traz sanções e vínculos com o governo federal, mas não
  atividade, porte nem município; 150 chamadas a 0,7 s sem nenhum 429 (contracts/transparencia-api.md).
- **Emendas** (§5.2, SC-002): 8 anos, todos `succeeded` com coletado = gravado e nenhuma
  retentativa. 2019: 8.456; 2020: 8.539; 2021: 6.595; 2022: 6.108; 2023: 6.110; 2024: 6.990;
  2025: 6.310; 2026: 5.936. Total de 55.044, de 4,7 a 6,8 min por ano no ritmo de dia.
- **Chave natural**: o mesmo `codigoEmenda` aparece em mais de uma linha, dividido por tipo de
  transferência e localidade (4 casos em 2024). A chave é `codigoEmenda` + `tipoEmenda` +
  `localidadeDoGasto` (data-model.md).
- **Chave inválida** (§5.3): com o arquivo da chave renomeado temporariamente, o lote terminou
  `failed` em cerca de 1 min, com `message` = "ErroChave: chave da API ausente ou inválida", sem
  coletar nada. O arquivo foi restaurado (32 bytes). Na primeira tentativa a execução não
  aparecia em `ctl_ingestion_runs`, porque a falha vinha antes do primeiro lote; corrigido com
  `lote_falho` (SC-007).

### 2026-11-13: US4 (fornecedores), `ws-dev-dpacademy`

- **Teste curto** (§6.1–6.2): `limite=1000` gerou 2 lotes de 500; 700 `encontrado` e 300
  `nao_encontrado`; 2 fornecedores com sanção no CEIS.
- **1ª rodada da carga completa** (`limite=15000`, de dia): 30 lotes de 500, todos `succeeded`,
  15.000 requisições a 0,7 s, nenhuma retentativa, 184 min. Acumulado: 32 lotes, 16.000 linhas e
  16.000 `_cnpj` distintos (nenhum repetido, §6.3); 10.606 `encontrado` (66%) e 5.394
  `nao_encontrado`. Restam cerca de 52 mil CNPJs na fila.
- **Carga completa concluída** (2026-11-14): mais 3 rodadas (15.000, 15.000 e 22.057). No total,
  137 lotes `succeeded`, 68.057 requisições sem nenhuma retentativa nem 429, 68.057 linhas e
  68.057 `_cnpj` distintos (§6.3). A fila zerou: a última rodada pediu 25.000 e só havia 22.057
  pendentes. São 68.057 e não 68.043 porque os meses carregados pela API trouxeram CNPJs novos.
  33.967 `encontrado` e 34.090 `nao_encontrado`.
- **Taxa de não encontrados por faixa de CNPJ**: fica em ~30% nas raízes abaixo de 20 milhões e
  acima de 68 milhões, e entre 55% e 75% nas raízes de 20 a 64 milhões (empresas abertas a partir
  de ~2014, muitas MEI). A taxa acompanha a faixa, não o horário: nos mesmos lotes, ritmo e
  respostas não mudaram. Leitura para a Silver: `/pessoa-juridica` cobre melhor quem tem relação
  com o governo federal; ausência não é erro.
- **Operação**: a 2ª rodada terminou às 23:22, e o encadeamento local parou porque o PC suspendeu;
  a madrugada ficou ociosa. Uma rodada disparada às 08:06 falhou com `TooManyRequestsForCapacity`
  porque havia uma sessão Spark de conferência aberta ao mesmo tempo (falha de plataforma, sem
  lote). No Trial, não abrir sessões enquanto uma carga roda; em produção o agendamento das
  01:00 resolve o encadeamento.

### 2026-11-14: US5 (registro e concorrência), `ws-dev-dpacademy`

- **Método**: o Trial não comporta duas sessões Spark ao mesmo tempo, então a concorrência foi
  simulada com duas linhas `running` inseridas à mão em `bronze_camara.ctl_ingestion_runs`
  (`run_id = teste-t034`): `partidos` recém-iniciado e `legislaturas` iniciado 7 h antes. Em
  seguida, `nb-full-030-bronze-camara-cadastros` com `recursos=partidos,legislaturas`.
- **Lote em andamento** (§7): `partidos` terminou `skipped`, com "outro lote do mesmo recurso em
  andamento" e zero registros.
- **Lote travado**: a linha antiga de `legislaturas` virou `failed` com `message` = `stale`, e o
  novo lote rodou `succeeded` com 57 registros. A linha de teste de `partidos` foi encerrada à
  mão depois ("linha de teste T034 encerrada à mão").
- **Registro completo** (SC-007): nenhuma linha `running` sobrou nas duas fontes. Os `failed`
  são todos os casos registrados acima: 3 anos de despesas no apagão de `www.camara.leg.br`, 2
  tentativas de 09/2026 antes da regra do `codDocumento` e o teste de chave inválida de emendas.
  Câmara: 30 `succeeded`, 7 `failed`, 1 `skipped`. Portal: 146 `succeeded`, 1 `failed`.

### 2026-11-16: primeira publicação e carga histórica, `ws-prd-dpacademy` (T042)

- **Publicação**: PR #4 (`dev` → `main`). O `deploy-prd` ficou verde em ~1 min, com 2 lakehouses,
  8 notebooks e 2 pipelines. Os notebooks de carga apontam para os lakehouses de produção, sem
  nenhum ID de dev no conteúdo, e os pipelines chamam os notebooks de produção. As agendas ficaram
  ativas só em prd (Câmara às 05:00, Portal à 01:00); em dev não há nenhuma. A chave do Portal foi
  enviada à mão para `bronze_transparencia/Files/_secrets/` de prd (32 bytes, igual à de dev).
- **Carga histórica** (manual, uma vez, todas as linhas com `environment = 'prd'`):
  - cadastros: 57 legislaturas, 38 partidos e 929 deputados, em 6,5 min;
  - despesas pelo arquivo, 2019 a 2026: 1.685.598 linhas em 3,3 min;
  - emendas, 2019 a 2026: 55.044, igual a dev.
- **Nova republicação da Câmara**: os arquivos de 2021 a 2026 foram republicados em 2026-11-16 às
  07:23 UTC, depois da carga de dev, com cerca de 35% mais linhas. Em 2024, o arquivo passou de
  173.961 linhas e R$ 211,4 mi para 232.926 linhas e R$ 250.384.236,66, conferido no arquivo
  baixado; a Bronze de prd bate exatamente. O esquema continua com as mesmas 32 colunas. Agora
  aparecem linhas sem `ideDocumento`, marcadas como despesas de liderança (1 em 2025, 5 em 2026).
  A Bronze de dev ficou com a versão anterior de 2021 a 2026. Para a Silver: recarregar dev
  antes de comparar ambientes, e tratar a republicação como rotina (data-model.md).
- **Falha transitória do Portal**: o lote de emendas de 2024 terminou `failed` com HTTP 400
  `{"Erro na API":"Erro ao executar a consulta"}` depois de ~1 min lendo páginas. Os outros 7 anos
  passaram. A repetição só de `anos=2024` deu `succeeded` com 6.990 registros. O cliente trata
  400 como falha definitiva e não tenta de novo; essa resposta específica parece instável no
  servidor (pendência abaixo).
- **Pendência**: avaliar se o cliente do Portal deve tentar de novo um 400 com "Erro ao executar
  a consulta".
- **Primeira execução agendada** (2026-11-17, conferida no histórico de jobs e em
  `ctl_ingestion_runs`): os dois pipelines rodaram por agenda e terminaram `Completed`, todos os
  lotes com `environment = 'prd'`, `succeeded` e `records_written = records_collected`. Em dev não
  houve nenhuma execução nova.
  - Portal (01:00 a 02:20): emendas de 2025 e 2026, com 12.246 registros em 819 páginas; 30 lotes
    de `pessoa_juridica` com 15.000 CNPJs distintos (9.964 `encontrado`, 5.036
    `nao_encontrado`), 15.000 requisições, nenhuma retentativa. A fila de produção começou do zero,
    então a fila de ~68 mil CNPJs leva cerca de 5 noites.
  - Câmara (05:00 a 05:30): cadastros (57 legislaturas, 38 partidos, 929 deputados) e despesas pela
    API de 09, 10 e 11/2026, com 16.518 registros (7.370, 7.792 e 1.356), cada mês com
    `records_collected = expected_total`; 7 retentativas HTTP em 1.952 requisições; 1 despesa sem
    `codDocumento` em 09/2026, registrada no aviso.
  - Total em prd: Câmara com 17 lotes `succeeded`; Portal com 40 `succeeded` e 1 `failed` (o lote
    de emendas de 2024 da carga histórica, já recarregado).
