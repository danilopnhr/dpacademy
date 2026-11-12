# ADR-003: chave do Portal da Transparência num arquivo da área Files do lakehouse

- **Status:** aceita
- **Data:** 2026-11-12
- **Feature:** [003-gastos-bronze-ingestion](../specs/003-gastos-bronze-ingestion/spec.md)
  (research R5)

## Contexto

A API do Portal da Transparência exige uma chave, gratuita e pessoal, no header
`chave-api-dados`. A constituição proíbe a chave no repositório, em notebooks, em pipelines e em
logs (Princípio VI), e o projeto não pode usar recursos pagos (Princípio VII). A API da Câmara
dos Deputados não exige chave.

## Decisão

A chave fica num arquivo texto, só com o valor e sem quebra de linha, em:

```text
bronze_transparencia/Files/_secrets/transparencia_api_key
```

- O notebook cliente lê o arquivo em tempo de execução
  (`/lakehouse/default/Files/_secrets/transparencia_api_key`).
- O valor nunca é impresso, nunca vai para `ctl_ingestion_runs`, e as mensagens de erro são
  sanitizadas.
- O arquivo é enviado à mão, uma vez em `ws-dev-dpacademy` e uma vez em `ws-prd-dpacademy`.
  Arquivos da área Files são dados, não itens: não passam pela Git integration nem pelo
  `fabric-cicd`.
- O `pr-validation` procura o valor exato da chave em todo o histórico do Git usando o secret
  `TRANSPARENCIA_API_KEY` do repositório, além do `gitleaks` e do secret scanning do GitHub.

## Alternativas rejeitadas

- **Azure Key Vault** com `notebookutils.credentials.getSecret`: exige assinatura Azure, e o
  tenant roda sem assinatura.
- **Variable Library do Fabric:** é sincronizada com o Git, então o valor iria para o
  repositório público.
- **Header na Copy activity do pipeline:** fica em texto na definição do pipeline, que vai para
  o Git.

## Consequências

- **Risco aceito:** qualquer membro do workspace com acesso ao lakehouse consegue ler o arquivo.
  É aceitável num tenant pessoal com um único usuário.
- **Troca da chave:** gerar outra no Portal, sobrescrever o arquivo nos dois workspaces e
  atualizar o secret `TRANSPARENCIA_API_KEY` do GitHub.
- **Migração futura:** se houver Key Vault, troca-se só a leitura da chave no
  `nb-util-010-bronze-transparencia-cliente`.
