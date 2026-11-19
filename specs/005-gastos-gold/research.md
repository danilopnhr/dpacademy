# Research: Camada Gold e modelo semântico do case gastos

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-18

Perfis feitos em produção (`ws-prd-dpacademy`, SQL endpoint, só leitura) em 2026-11-18, depois da
primeira rotina noturna com a Silver.

## R1. Forma de carga: reconstrução total com verificação antes de gravar

Volume: 1.687.037 despesas, 55.057 emendas, cerca de 70 mil fornecedores e menos de 5 mil linhas
somando as demais dimensões.

**Decisão**: o notebook da Gold monta todas as dimensões e os dois fatos em memória a partir da
Silver, roda todas as verificações (R7) sobre esses conjuntos preparados e só então grava cada
tabela com `overwrite` (cada gravação é uma versão Delta nova, atômica por tabela). Se qualquer
verificação falhar, nada é gravado e as tabelas da noite anterior continuam publicadas (FR-013).
Ordem de gravação: dimensões, depois fatos. Reexecutar sobre a mesma Silver produz as mesmas
tabelas (FR-011), porque as chaves são determinísticas (R2).
**Riscos aceitos**: uma falha de gravação no meio (não de verificação) pode deixar dimensões novas
com fatos antigos até a próxima execução; como as chaves são estáveis, os fatos antigos continuam
encontrando seus membros, exceto membros novos. A reexecução manual corrige.
**Alternativas rejeitadas**: `MERGE` incremental por tabela (a Gold depende de várias tabelas da
Silver ao mesmo tempo, e detectar o que mudou em cada uma custa mais do que reconstruir 1,7 mi de
linhas, que leva poucos minutos; Princípio VII); um notebook por tabela (perde a verificação de
integridade entre fatos e dimensões antes de gravar e soma uma sessão Spark por notebook no Trial).

**V-Order**: as tabelas da Gold são lidas pelo Direct Lake, que se beneficia do V-Order. As tabelas
são gravadas com a propriedade `delta.parquet.vorder.enabled = true`, independente do perfil de
recursos do workspace. Uma gravação por `overwrite` gera poucos arquivos por tabela, muito abaixo
do limite de arquivos do Direct Lake.

## R2. Chaves substitutas determinísticas

**Decisão**: `sk_<entidade>` é `BIGINT`, calculado como `xxhash64` da chave natural com um prefixo
por tipo de membro (ex.: `D:<codigo_deputado>`, `L:<nome normalizado da liderança>`). Membros
reservados: `-1` = "Não informado" e `-2` = "Não se aplica" (usado no deputado das emendas sem
autor ligado, R6). A verificação de unicidade de cada dimensão confere o `sk` e a chave natural;
uma colisão de hash faria a execução falhar, e não passar em silêncio.
**Por quê**: a mesma chave natural gera o mesmo `sk` em todas as execuções e nos dois ambientes,
o que permite comparar dev e prd, conferir uma noite contra a anterior e, se um dia for preciso,
migrar para carga incremental sem renumerar.
**Alternativas rejeitadas**: `row_number()` (muda a cada execução); coluna identity do Delta (não
combina com `overwrite` total e não é estável entre ambientes); usar a chave natural em texto
como chave de relacionamento (colunas de texto longas pesam mais no Direct Lake).

## R3. Calendário e grão temporal

- As despesas têm ano e mês obrigatórios na Silver; `data_emissao` é nula em cerca de 3% das
  linhas.
- As emendas só têm o ano.

**Decisão**: `dim_data` diária, de 2019-01-01 a 31/12 do ano corrente, com `sk_data INT` no formato
`AAAAMMDD`, gerada no notebook (não vem da fonte). `fat_despesas.sk_data_competencia` aponta para o
primeiro dia do mês de competência; `data_emissao` fica como coluna de data no fato, sem
relacionamento (simplicidade; um relacionamento inativo pode ser acrescentado na feature do
relatório se for preciso). `fat_emendas.sk_data_ano` aponta para 1º de janeiro do ano da emenda; o
modelo documenta que emendas só podem ser lidas no nível de ano.
**Exceção ao FR-004**: `dim_data` não tem membro "não informado", porque toda linha de fato tem ano
(e mês, nas despesas) obrigatórios, e a tabela de datas do modelo semântico exige datas únicas,
não nulas e contínuas. A verificação de integridade do calendário continua valendo.

## R4. Deputado, partido e UF

Perfil: 1.161 deputados distintos nas despesas, 234 deles ausentes do cadastro (5.157 linhas);
6.074 linhas de liderança (sem `codigo_deputado`).

**Decisão**:

- `dim_deputado`: um membro por `codigo_deputado` (cadastro ∪ despesas) e um por liderança (nome
  parlamentar normalizado). Atributos do cadastro quando existir; senão, os da linha mais recente
  das despesas (ano e mês mais altos). Colunas `e_lideranca`, `no_cadastro` e `tipo_membro`
  (`Deputado`, `Liderança`, `Não informado`, `Não se aplica`).
- Partido e UF de cada despesa vêm da linha da despesa (FR-006): `fat_despesas.sk_partido` e
  `sk_uf`. `dim_partido` tem um membro por sigla, das despesas, do cadastro de deputados e do de
  partidos; o nome vem do cadastro de partidos, ou fica igual à sigla para partidos extintos.
- `dim_uf`: as 27 UFs com nome e região, em lista fixa no notebook comum (testada em
  `pytest`), mais os membros reservados.
- Nada de histórico de atributos (SCD 2) nas dimensões: o histórico relevante, o partido na data da
  despesa, já está no fato.

## R5. Fornecedor e privacidade do CPF

Perfil: 1.672.509 linhas com CNPJ (68.121 CNPJs), 14.528 com CPF e o restante sem documento; dos
CNPJs, 18.355 encontrados no Portal, 11.645 não encontrados e 38.121 ainda na fila (termina por
volta de 2026-11-21). O mesmo CNPJ aparece com grafias diferentes de nome nas despesas.

**Decisão**:

- Chave natural: `J:<cnpj>` para CNPJ; `F:<cpf mascarado>|<nome normalizado>` para CPF;
  `S:<nome normalizado>` para fornecedor sem documento.
- CPF mascarado no formato `***.456.789-**` (dígitos 4 a 9 visíveis, o padrão de anonimização de
  documentos do governo federal). O CPF completo não entra na Gold **nem como hash**: o hash de um
  CPF pode ser revertido por força bruta (são só 10⁹ CPFs válidos), por isso a chave usa a máscara
  e o nome.
- `nome_fornecedor`: o nome mais frequente do documento nas despesas (empate: o mais recente).
  `razao_social` e os indicadores vêm do Portal quando encontrado; se a razão social vier vazia
  (89 casos), fica nula e o relatório usa `nome_fornecedor`.
- `situacao_portal`: `Encontrado`, `Não encontrado`, `Não consultado` (CNPJ ainda na fila) ou
  `Não se aplica` (CPF ou sem documento). `possui_sancao` = qualquer um dos quatro cadastros de
  sanção.
- Uma verificação `privacidade` confere que nenhuma coluna de texto do `dim_fornecedor` contém uma
  sequência de 11 dígitos seguidos (CPF sem máscara).

## R6. Ligação do autor da emenda ao deputado

Perfil: 51.662 emendas individuais; 1.216 autores distintos, 785 casando por nome exato
(maiúsculas) com o nome parlamentar dos deputados, cerca de 63% do valor pago. Os demais são, na
maior parte, senadores (o Portal traz as emendas de todo o Congresso). Emendas de relator (`RELATOR
GERAL`), bancada (`Sem informação` em boa parte) e comissão não têm parlamentar autor.

**Decisão**:

- Normalização dos dois lados: maiúsculas, sem acentos (`unicodedata` NFKD), espaços colapsados e
  aparados. Função pura no notebook comum, testada em `pytest`.
- Candidatos: `nome_parlamentar` dos membros `Deputado` da `dim_deputado`. Um candidato: ligado.
  Mais de um: `ambíguo`, sem ligação. Nenhum: sem ligação.
- `dim_autor_emenda`: um membro por (nome do autor, grupo da emenda), com `tipo_autor`
  (`Deputado`, `Parlamentar não identificado`, `Relator`, `Bancada`, `Comissão`, `Sem
  informação`) e `motivo_sem_ligacao` (`não casou`, `ambíguo`, `não se aplica`).
- `fat_emendas.sk_deputado`: o deputado ligado, ou `-2` ("Não se aplica") quando não há ligação.
- A parcela do valor pago das emendas individuais ligada a deputado é registrada a cada execução
  numa verificação informativa `ligacao_autor` (sempre `passed`, com o percentual em `detalhe`);
  o SC-004 é conferido no quickstart, não bloqueia a rotina.
- Casamento aproximado (fuzzy) fica fora do escopo (spec).

## R7. Verificações de qualidade da Gold

`ctl_quality_checks` no `gold_gastos`, com o mesmo esquema da Silver (contrato da 004). Antes de
gravar, sobre os conjuntos preparados:

| Verificação | Onde | Passa quando |
|---|---|---|
| `unicidade` | cada tabela, no `sk` e na chave natural | 0 repetidas |
| `obrigatorias` | cada tabela | 0 linhas com obrigatória nula |
| `integridade` | cada chave estrangeira de cada fato | 0 linhas sem membro na dimensão |
| `conciliacao` | `fat_despesas` × Silver por ano (linhas e valor líquido); `fat_emendas` × Silver por ano e tipo (linhas, empenhado, liquidado, pago) | diferença 0 |
| `privacidade` | `dim_fornecedor` | nenhuma sequência de 11 dígitos sem máscara |
| `ligacao_autor` | `fat_emendas` | sempre `passed` (informativa) |

Depois de gravar: `contagem` de cada tabela. Qualquer `failed` faz o notebook levantar exceção
depois de registrar os resultados, sem gravar nenhuma tabela da Gold.

Teste de falha em dev (US5, SC-008): parâmetro `injetar_orfao_para_teste` (padrão `false`) que
acrescenta ao fato de despesas preparado uma linha com `sk_fornecedor` inexistente; a integridade
precisa falhar e nenhuma tabela pode ganhar versão Delta nova.

**Ajuste no validador**: `ci/validate_names.py` hoje só aceita `dim_`, `fat_` e `agg_` em
lakehouses `gold_`; a tabela `ctl_quality_checks` geraria aviso no deploy. A regra passa a aceitar
também `ctl_<assunto>` na Gold, como a constituição já prevê para tabelas de controle (Princípio
IV), com teste em `tests/unit/test_validate_names.py`.

## R8. Notebooks e orquestração

**Decisão**:

- `nb-util-010-gold-gastos-comum`: funções puras (normalização de nome, máscara de CPF, formato de
  CNPJ, classificação do autor, leitura da localidade, lista de UFs), testadas por `pytest` pelo
  mesmo `conftest.py` da 003, e funções Spark (chave substituta, verificações, gravação com
  V-Order, registro em `ctl_quality_checks`).
- `nb-full-020-gold-gastos-modelo`: monta, verifica e grava todas as tabelas (R1). Lakehouse padrão
  `gold_gastos`; lê a Silver pelo nome qualificado (`silver_camara.despesas`), como a Silver lê a
  Bronze.
- `pl-010-orq-gastos-diario` ganha a atividade `gold_gastos` (notebook, duas retentativas de 180 s,
  como as outras), que depende de `silver_camara_despesas` **e** `silver_transparencia_fornecedores`
  com `Succeeded`, e a atividade `falha_gold_gastos` (Fail). Se a Silver de uma fonte falhar ou
  for pulada, a Gold não roda (US4, cenário 2). Nenhuma agenda nova.
- `ci/parameter.yml`: entrada do GUID de dev do `gold_gastos` (lakehouse padrão do notebook) e as
  duas entradas do modelo semântico (R9).

Tempo estimado da Gold: 5 a 10 min no Trial; a rotina continua terminando por volta das 06:00
enquanto durar a fila de fornecedores, e das 05:00 depois (SC-005).

## R9. Modelo semântico `sm-gastos`

**Modo**: Direct Lake sobre o SQL endpoint do `gold_gastos`. É a variante GA e a cobrada na DP-600,
com fallback para DirectQuery se um limite for excedido. A variante sobre OneLake aparece como
preview em parte da documentação e da comunidade, e relatos indicam que regras de implantação não
a reapontam; não há ganho para este case.

**Criação em dev**: o modelo é escrito em TMDL num rascunho local e criado no `ws-dev-dpacademy`
pela API REST (`createItem` com definição TMDL), usando o token do contexto `~/.azure-dpacademy`;
depois vai para `workspace/sm-gastos.SemanticModel/` pelo commit da Git integration, como os
notebooks. O servidor MCP de modelagem não é usado: ele autentica fora do contexto isolado do
dpacademy (o servidor MCP do SQL endpoint respondeu "resource not found" em 2026-11-18 pelo mesmo
motivo).

**Reapontamento para produção**: no TMDL, a expressão `DatabaseQuery` usa
`Sql.Database("<servidor SQL de dev>", "<id do SQL endpoint de dev>")`. O `fabric-cicd` 1.4.0
substitui os dois por `find_replace` em `ci/parameter.yml`, com os atributos dinâmicos
`$items.Lakehouse.gold_gastos.$sqlendpoint` e `$items.Lakehouse.gold_gastos.$sqlendpointid`
(conferidos em `fabric_cicd/constants.py`, `PROPERTY_PATH_ATTR_MAPPING`), limitando a regra a
`item_type: SemanticModel` e `file_path: **/expressions.tmdl`. Nenhum GUID de produção no
repositório (contrato da 002). Sem `semantic_model_binding`: o modelo usa o SSO padrão do Direct
Lake.

**Reenquadramento explícito (revisto na implementação, 2026-11-18)**: em dev, depois de criar o
modelo e regravar a Gold, nenhum reenquadramento automático apareceu no histórico em mais de 8
minutos, e a opção "manter os dados do Direct Lake atualizados" não é exposta pela API nem pelo
TMDL, então não pode ser versionada. **Decisão**: o `nb-full-020-gold-gastos-modelo`, depois de
gravar com sucesso, pede o refresh do `sm-gastos` pelo semantic link
(`sempy.fabric.refresh_dataset`), que num modelo Direct Lake é um reenquadramento de segundos, não
uma importação (FR-017 continua atendido). O resultado vai para `ctl_quality_checks` como
`reenquadramento`; se falhar, a execução falha (os dados já gravados ficam, e a retentativa é
idempotente). Modelo ausente no workspace (antes da primeira publicação) não é falha.
**Concorrência com a atualização automática (orquestrador em dev, 2026-11-18)**: a atualização
automática existe, mas dispara de forma irregular: às 16:09:12 ela começou sozinha logo depois da
gravação, o refresh do notebook começou 15 s depois, a automática falhou por "locking conflicts" e
o pedido do notebook só concluiu em 5,5 min, acima do limite de espera então usado (5 min), e a
Gold falhou na segunda tentativa (passou na terceira). Ajuste: espera de até 15 min, e conta como
sucesso qualquer reenquadramento `Completed` iniciado depois do começo da gravação, pedido pelo
notebook ou automático; a mensagem de falha distingue falha depois da gravação ("a Gold foi
atualizada, o modelo pode estar com a versão anterior").
**Alternativas rejeitadas**: depender só da atualização automática (irregular, invisível e não
versionável);
atividade de refresh de modelo semântico no pipeline (exige uma conexão do Fabric com credencial
própria em cada ambiente).

**Primeira publicação**: o `gold_gastos` de produção nasce vazio no deploy; o modelo só enquadra
depois da carga inicial manual da Gold, que já termina pedindo o refresh. O SQL endpoint precisa
ter sincronizado as tabelas novas antes (em dev, a sincronização demorou; a API `refreshMetadata`
do SQL endpoint resolve). Se o enquadramento falhar com o modelo de propriedade da service
principal, o plano B é assumir o modelo (take over) com a conta do engenheiro, uma vez; registrar
no quickstart.

**Conteúdo**: as dez dimensões e os dois fatos (sem `ctl_quality_checks`); relacionamentos muitos
para um, filtro de uma direção, da dimensão para o fato; `dim_data` marcada como tabela de datas
com hierarquia Ano > Trimestre > Mês; `sk_*`, chaves naturais técnicas e colunas `_` ocultas;
nomes de exibição em português; medidas nos fatos (Direct Lake não permite tabela calculada
para medidas). Lista de medidas no contrato [sm-gastos.md](./contracts/sm-gastos.md).

**Validação**: consultas DAX pela API `executeQueries` do Power BI com o token do contexto
dpacademy, comparadas com consultas T-SQL no SQL endpoint da Gold (SC-009).

## R10. Prazos e capacidade

Uma sessão Spark por vez no Trial (R9 da 004): cargas manuais e diagnósticos fora de 04:00–06:30 em
produção. Ordem de entrega com marcos: Gold validada em dev até 2026-11-22; PR e Gold em prd até
2026-11-26 (SC-006); modelo em prd até 2026-11-30 (SC-010). O modelo pode ser desenvolvido em dev
assim que a Gold de dev existir, em paralelo com a revisão do PR da Gold, mas vai para produção no
mesmo PR `dev` → `main` ou num segundo, conforme o andamento.
