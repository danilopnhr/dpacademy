# Quickstart: validar a Gold e o `sm-gastos`

**Feature**: [spec.md](./spec.md) | Contratos: [gold-tables.md](./contracts/gold-tables.md),
[notebooks-e-orquestracao.md](./contracts/notebooks-e-orquestracao.md),
[sm-gastos.md](./contracts/sm-gastos.md)

## 0. Pré-requisitos

- `az` sempre com `AZURE_CONFIG_DIR=~/.azure-dpacademy`, tenant do dpacademy conferido.
- Silver de dev atualizada (rodar os quatro notebooks da Silver se a última carga for antiga).
- Nenhuma outra sessão Spark aberta (Trial: uma por vez). Em produção, nada entre 04:00 e 06:30.
- Consultas de conferência em T-SQL no SQL endpoint do `gold_gastos` e da Silver (nomes de três
  partes no mesmo workspace).

## 1. Despesas (US1, SC-001)

Rodar `nb-full-020-gold-gastos-modelo` em dev. Esperado:

- Por ano, `COUNT(*)` e `SUM(valor_liquido)` de `fat_despesas` iguais aos de
  `silver_camara.despesas`.
- Toda linha de `fat_despesas` encontra membro em cada dimensão (JOIN sem perdas).
- Lideranças com `tipo_membro = 'Liderança'`; deputados fora do cadastro com `no_cadastro = false`
  e nome preenchido (perfil de prd: 234).
- `sk_partido` de uma despesa = partido publicado na linha (conferir um deputado que trocou de
  partido).
- Despesas sem `data_emissao` com `sk_data_competencia` preenchido.

## 2. Fornecedores (US2)

- Todo `sk_fornecedor` do fato existe em `dim_fornecedor`; soma do valor líquido por
  `situacao_portal` fecha com o total.
- `tipo_documento = 'CPF'` só com `documento_exibicao` no formato `***.ddd.ddd-**`; nenhuma coluna
  com 11 dígitos seguidos (verificação `privacidade` `passed`).
- Um CNPJ com várias grafias aparece uma vez.
- Em prd, a quantidade de `Não consultado` cai a cada noite até a fila zerar.

## 3. Emendas (US3, SC-002, SC-004)

- Por ano e tipo, quantidade e somas de empenhado, liquidado e pago de `fat_emendas` iguais às de
  `silver_transparencia.emendas`.
- Emendas de relator, bancada e comissão com `sk_deputado = -2`.
- `ligacao_autor` em `ctl_quality_checks` com percentual ≥ 60% do valor pago das individuais;
  autores `ambíguo` contados.

## 4. Qualidade (US5, SC-003, SC-008)

1. Execução normal: `ctl_quality_checks` do `gold_gastos` com `unicidade` e `obrigatorias` de cada
   tabela, `integridade` de cada chave estrangeira, `conciliacao` dos dois fatos, `privacidade`,
   `ligacao_autor` e `contagem`, todas `passed`.
2. Rodar com `injetar_orfao_para_teste=true`: a execução falha, `integridade` de
   `fat_despesas.sk_fornecedor` aparece `failed` com a chave órfã em `detalhe`, e nenhuma tabela
   da Gold ganha versão Delta nova (`DESCRIBE HISTORY`).
3. Reexecutar sem parâmetro: mesmas contagens e mesmos `sk` da primeira execução.

## 5. Orquestrador em dev (US4)

Disparar `pl-010-orq-gastos-diario` à mão em dev. Esperado: `gold_gastos` roda por último, só
depois de `silver_camara_despesas` e `silver_transparencia_fornecedores` com sucesso. Teste de
dependência: com uma Silver forçada a falhar, `gold_gastos` não roda.

## 6. Modelo semântico em dev (US6)

1. Criar `sm-gastos` pela API com o TMDL do contrato; fazer o commit pela Git integration.
2. Conferir pela API `executeQueries`:
   - `EVALUATE SUMMARIZECOLUMNS(dim_data[ano], "g", [Gasto líquido], "p", [Emendas pago])` igual aos
     totais por ano da Gold em T-SQL;
   - `[% pago ligado a deputado]` igual ao `ligacao_autor` da última execução;
   - filtro por partido respeitando o partido da despesa.
3. Rodar a Gold de novo e conferir que ela termina com `reenquadramento` `passed` e que o histórico
   de refresh do modelo mostra o reenquadramento pedido pelo notebook (research R9).

## 7. Produção (SC-005, SC-006, SC-009, SC-010)

1. PR `dev` → `main`, `deploy-prd` verde: `gold_gastos`, os dois notebooks, o orquestrador com a
   atividade nova e o `sm-gastos` publicados; `expressions.tmdl` de prd apontando para o SQL
   endpoint do `gold_gastos` de prd (conferir pela API `getDefinition`).
2. `refreshMetadata` do SQL endpoint do `gold_gastos` de prd depois da carga; carga inicial manual
   da Gold em prd, fora da rotina; conferir os §1 a §4 com os números de produção.
3. Conferir `reenquadramento` `passed` na carga inicial; se o enquadramento falhar com o modelo de
   propriedade da service principal, assumir o modelo com a conta do engenheiro e repetir
   (research R9). Conferir o §6.2 em prd.
4. Na manhã seguinte: a rotina rodou a Gold depois da Silver, terminou antes das 07:00,
   `ctl_quality_checks` do `gold_gastos` tem a noite com `environment = 'prd'` (inclusive
   `reenquadramento`), e o modelo mostra os dados da noite sem refresh manual.

## Registro da validação

### 2026-11-18: `ws-dev-dpacademy`

Base: Silver de dev de 2026-11-17 (1.686.374 despesas; 55.044 emendas; 68.057 CNPJs, fila completa).

- **Primeira execução**: falhou de propósito pelo portão de qualidade, sem gravar nenhuma tabela:
  `dim_fornecedor` com 3 fornecedores sem nome publicado (`obrigatorias`) e 32 razões sociais de
  MEI com CPF completo (`privacidade`). Correção: nome cai para a razão social ou o documento
  exibido; CPF dentro de nome, razão social e nome fantasia passa a ser mascarado
  (`mascarar_cpf_em_texto`, research R5). As outras 46 verificações já passavam.
- **§1 Despesas**: execução seguinte `Completed` em 7,0 min, 61 verificações `passed`. Os 8 anos
  iguais à Silver em linhas e valor líquido (ex.: 2024 com 232.926 linhas e R$ 250.384.236,66).
  `dim_deputado`: 929 do cadastro, 234 só das despesas, 21 lideranças (6.064 linhas), reservados
  `-1` e `-2`. 54.501 despesas sem data de emissão, todas com competência. 196 deputados com mais
  de um partido nas despesas (ex.: Alan Rick em DEM e UNIÃO), cada despesa no partido da linha.
- **§2 Fornecedores**: 33.977 CNPJs `Encontrado` (1.250.740 linhas), 34.126 `Não encontrado`
  (421.111) e 795 CPFs `Não se aplica` (14.523), somando o total; nenhum `Não consultado` porque a
  fila de dev está completa. Todos os CPFs no formato `***.ddd.ddd-**`; 32 razões sociais
  mascaradas; 95 fornecedores com sanção; 5 sem nome publicado.
- **§3 Emendas**: iguais à Silver por ano e tipo. Relator, bancada e comissão com `sk_deputado =
  -2`. 82,0% do valor pago das emendas individuais ligado a deputado (1.026 autores; SC-004 ≥ 60%);
  3 nomes ambíguos (MARIANA CARVALHO, ATILA LIRA, BEBETO); os maiores não ligados são senadores
  (Davi Alcolumbre, Eduardo Braga, Otto Alencar…). Localidades: 27 estados, 3.406 municípios,
  6 `Outro`.
- **§4 Qualidade**: com `injetar_orfao_para_teste=true`, `Failed` em 3,7 min com `integridade`
  (`fat_despesas.sk_fornecedor`, chave 123) e `conciliacao` (ano 2019) `failed`; nenhuma das 12
  tabelas ganhou versão Delta. A reexecução normal (6,7 min) reproduziu as mesmas contagens e a
  mesma soma de `sk` em todas as tabelas. V-Order ligado. Ajuste: a propriedade de V-Order só é
  aplicada na primeira gravação (antes, cada execução criava duas versões Delta por tabela).
- **§6 Modelo**: `sm-gastos` criado pela API com o TMDL gerado do esquema real (12 tabelas, 12
  relacionamentos, 12 medidas); o SQL endpoint precisou de `refreshMetadata` para enxergar as
  tabelas novas. Refresh `Completed`; por DAX, gasto líquido por ano idêntico à Gold nos 8 anos;
  `[% pago ligado a deputado]` = 82,04%, igual ao `ligacao_autor`; `[Deputados com despesa]` =
  1.161; filtro por partido respeitando o partido da linha; consulta cota × emendas por deputado
  funcionando. Atualização automática: depois de regravar a Gold, nenhum reenquadramento apareceu no
  histórico em mais de 8 min; o notebook passou a pedir o refresh (research R9), e a execução
  seguinte (7,3 min) registrou o `ViaEnhancedApi` no histórico do modelo.
- **§5 Orquestrador**: `pl-010-orq-gastos-diario` disparado à mão, `Completed` em 74,7 min, na
  ordem do contrato (Bronze da Câmara 15:10–15:25, Bronze do Portal 15:25–15:38, Silver 15:38–15:59,
  Gold 15:59–16:24 UTC); `gold_gastos` só começou depois das duas Silver com sucesso. As quatro
  Silver e a primeira tentativa da Gold falharam em ~20 s com `TooManyRequestsForCapacity` e
  passaram na retentativa. A segunda tentativa da Gold gravou as tabelas mas falhou no
  `reenquadramento`: a atualização automática do Direct Lake disparou junto com o refresh do
  notebook, falhou por conflito de bloqueio, e o refresh do notebook levou 5,5 min (limite era
  5 min). A terceira passou. Ajuste no `reenquadrar_modelo` (research R9). O teste de dependência
  com uma Silver forçada a falhar não foi executado: a regra é a dependência `Succeeded` nas duas
  atividades da Silver, conferida na definição do pipeline, a mesma semântica já testada na 004.
- **`parameter.yml`**: validado com `validate_parameter_file` do `fabric-cicd` 1.4.0 para `prd`; o
  servidor SQL e o SQL endpoint de dev só aparecem no `expressions.tmdl` do `sm-gastos`.
