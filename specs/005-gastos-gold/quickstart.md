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
3. Rodar a Gold de novo e conferir que o modelo mostra a nova versão sem refresh manual (atualização
   automática do Direct Lake).

## 7. Produção (SC-005, SC-006, SC-009, SC-010)

1. PR `dev` → `main`, `deploy-prd` verde: `gold_gastos`, os dois notebooks, o orquestrador com a
   atividade nova e o `sm-gastos` publicados; `expressions.tmdl` de prd apontando para o SQL
   endpoint do `gold_gastos` de prd (conferir pela API `getDefinition`).
2. Carga inicial manual da Gold em prd, fora da rotina; conferir os §1 a §4 com os números de
   produção.
3. Refresh manual único do `sm-gastos` pela API; se o enquadramento falhar com o modelo de
   propriedade da service principal, assumir o modelo com a conta do engenheiro e repetir
   (research R9). Conferir o §6.2 em prd.
4. Na manhã seguinte: a rotina rodou a Gold depois da Silver, terminou antes das 07:00,
   `ctl_quality_checks` do `gold_gastos` tem a noite com `environment = 'prd'`, e o modelo mostra os
   dados da noite sem refresh manual.

## Registro da validação

_(preencher durante a implementação)_
