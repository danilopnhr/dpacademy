# ADR-005: Gold reconstruída a cada noite e modelo Direct Lake sobre o SQL endpoint

- **Status:** aceita
- **Data:** 2026-11-18
- **Feature:** [005-gastos-gold](../specs/005-gastos-gold/spec.md) (research R1, R2, R5, R6 e R9)

## Contexto

A Gold do case `gastos` é o único lugar onde Câmara e Portal da Transparência se cruzam
(Princípio I). Ela junta cinco tabelas da Silver num star schema de dez dimensões e dois fatos
(1,69 milhão de despesas e 55 mil emendas), e alimenta o modelo semântico `sm-gastos`, que precisa
estar em produção antes do fim da capacidade Trial (~2026-12-04).

Quatro pontos pediam decisão:

1. Como carregar a Gold sem que uma falha de qualidade chegue ao relatório (Princípio V).
2. Como gerar chaves substitutas que não mudem a cada noite.
3. Como tratar o CPF dos fornecedores pessoa física num portfólio público. A Câmara publica o CPF,
   e a razão social de MEIs no Portal também traz o CPF do dono.
4. Que variante de Direct Lake usar, como apontar o modelo de produção para a Gold de produção sem
   GUID de produção no repositório, e como garantir que o modelo leia a versão nova da Gold.

## Decisão

1. **Reconstrução total com verificação antes de gravar.** Um único notebook
   (`nb-full-020-gold-gastos-modelo`) monta todas as tabelas em memória, roda unicidade,
   obrigatórias, integridade de cada fato com cada dimensão, conciliação dos totais com a Silver e
   privacidade, e só então grava (dimensões, depois fatos) com `overwrite` e V-Order. Se qualquer
   verificação falhar, nenhuma tabela é gravada.
2. **Chaves por hash da chave natural.** `sk_<entidade>` é `xxhash64` da chave natural com prefixo
   por tipo de membro; `-1` (não informado) e `-2` (não se aplica) são reservados. A mesma Silver
   gera as mesmas chaves em qualquer execução e nos dois ambientes.
3. **CPF mascarado, nunca completo nem em hash.** CPF de fornecedor vira `***.456.789-**`, inclusive
   quando aparece dentro de nomes e razões sociais. A chave do fornecedor pessoa física usa a
   máscara e o nome normalizado, não um hash do CPF, porque um hash de CPF pode ser revertido por
   força bruta (são cerca de 10⁹ CPFs válidos). Uma verificação `privacidade` impede a gravação se
   sobrar um CPF completo.
4. **Direct Lake sobre o SQL endpoint, reapontado pelo `fabric-cicd`, com reenquadramento
   explícito.** É a variante GA e a cobrada na DP-600. No TMDL, `Sql.Database(servidor, id do SQL
   endpoint)` de dev é trocado na publicação pelos atributos dinâmicos
   `$items.Lakehouse.gold_gastos.$sqlendpoint` e `$sqlendpointid`, só no `expressions.tmdl`. O
   notebook da Gold termina pedindo o refresh do modelo pelo semantic link, que em Direct Lake é um
   reenquadramento de segundos; o resultado vai para `ctl_quality_checks`.

## Consequências

- Uma falha de qualidade deixa a Gold e o modelo com os dados da noite anterior. Em dev, uma linha
  órfã injetada fez a execução falhar sem criar versão Delta em nenhuma tabela, e a reexecução
  normal reproduziu exatamente as mesmas contagens e chaves.
- A Gold leva cerca de 7 minutos por noite no Trial. Se o volume crescer muito, a carga
  incremental pode ser adotada sem renumerar chaves.
- O autor da emenda é ligado ao deputado por nome normalizado, com candidato único: 82% do valor
  pago das emendas individuais fica ligado. O restante são, em boa parte, senadores e 3 nomes
  ambíguos. Casamento aproximado ficou fora do escopo.
- O reenquadramento explícito torna a atualização do modelo visível e versionada. Na implementação,
  a atualização automática do Direct Lake não reenquadrou o modelo em mais de 8 minutos, e a opção
  não é exposta pela API nem pelo TMDL. Em troca, se o refresh falhar, a execução da Gold fica
  vermelha, mesmo com os dados já gravados (a retentativa é idempotente).
- O modelo de produção pertence à service principal do deploy. Se o enquadramento falhar por isso, o
  plano B é assumir o modelo com a conta do engenheiro, uma vez.

## Alternativas consideradas

- **`MERGE` incremental por tabela:** a Gold depende de várias tabelas da Silver ao mesmo tempo, e
  detectar o que mudou em cada uma custa mais do que reconstruir 1,7 milhão de linhas.
- **Um notebook por tabela:** perde a verificação de integridade entre fatos e dimensões antes de
  gravar e soma uma sessão Spark por notebook no Trial.
- **`row_number()` ou coluna identity como chave:** mudam a cada execução ou não são estáveis entre
  ambientes.
- **Membro único "pessoa física" para fornecedores com CPF:** máxima privacidade, mas perde a
  análise por fornecedor; descartado em 2026-11-18.
- **Direct Lake sobre OneLake:** ainda tratado como preview em parte da documentação, sem ganho para
  este case.
- **Atualização automática do Direct Lake:** invisível e não versionável.
- **Atividade de refresh de modelo no pipeline:** exige uma conexão do Fabric com credencial própria
  em cada ambiente.
