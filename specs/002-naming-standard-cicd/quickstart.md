# Quickstart: validar o padrão de nomenclatura e o CI/CD

Roteiro para provar, de ponta a ponta, que a feature atende à spec. Regras em
[contracts/naming-rules.md](./contracts/naming-rules.md); workflows em
[contracts/ci-pipelines.md](./contracts/ci-pipelines.md); configuração em
[contracts/deploy-config.md](./contracts/deploy-config.md).

## Pré-requisitos

- Repositório público `dpacademy` no GitHub, com as branches `main` e `dev`, secret scanning e
  push protection ativos e o ruleset `main-protegida`.
- `ws-dev-dpacademy` conectado a `dev`, pasta `workspace/`; `ws-prd-dpacademy` criado e **não**
  conectado ao Git.
- `sp-dpacademy-cicd` registrada, Admin no `ws-prd-dpacademy`, liberada nas configurações de tenant
  do Fabric; repository secret `BDL_NBA_API_KEY` e Environment `ws-prd-dpacademy` preenchidos.
- Python 3.11+ local com `pytest`.

## 1. Validador local (US1)

```powershell
python -m pytest tests/unit -q
python ci/validate_names.py workspace/
```

Esperado: testes verdes; o validador sai com `0` e não lista violações.

## 2. Documento do padrão (US1, FR-004)

Abra `docs/padrao-nomenclatura.md`. Esperado: Bronze, Silver e Gold, regras gerais e um exemplo
por tipo. Teste: escreva, só olhando o documento, o nome de um notebook incremental da Silver da
NFL. Esperado: `nb-incr-<seq>-silver-balldontlie-<assunto>`, aceito pelo validador.

## 3. Nomes antigos (SC-002)

```powershell
git grep -n -E "lh_|bdl_|fato_|(^|[^-])dpacademy-(dev|prod)|(^|[^a-z])(nb|pl)_" -- README.md docs/ specs/001-balldontlie-bronze-ingestion/ workspace/
```

Esperado: nenhum resultado.

## 4. PR bloqueado por nome (US2 cenário 2, SC-004)

1. Em `ws-dev-dpacademy`, crie um notebook chamado `nb_teste` e faça commit em `dev`.
2. Abra PR `dev` → `main`. Esperado: `pr-validation` vermelho, com
   a anotação `Notebook "nb_teste" viola ...` no PR; botão de merge bloqueado pelo ruleset.
3. Apague o notebook, faça commit. Esperado: validação verde.

## 5. PR bloqueado por segredo (US2 cenário 2, SC-004)

O repositório é público: **nunca** use a chave real neste teste, porque ela ficaria exposta no
momento do push.

1. Troque temporariamente o repository secret `BDL_NBA_API_KEY` por um valor de teste, por exemplo
   `teste-segredo-dpacademy-0001`.
2. Numa branch descartável a partir de `dev`, faça commit de um arquivo com esse valor de teste e
   abra PR para `main`. Esperado: a etapa 3 falha com "segredo conhecido encontrado", sem mostrar
   o valor.
3. Feche o PR sem merge, apague a branch e **restaure** o secret com a chave real.

## 6. Push direto recusado (US2 cenário 4, SC-003)

```powershell
git push origin HEAD:main
```

Esperado: recusado pelo ruleset (`GH013: Repository rule violations`), mesmo sendo você o
administrador do repositório.

## 7. Primeira publicação (US2 cenários 1 e 3, SC-005)

1. Crie `bronze_balldontlie` em dev (se ainda não existir), faça commit e abra PR.
2. Com o `pr-validation` verde, conclua com squash. Esperado: `deploy-prd` inicia sozinho e termina verde em menos de 15 min
   após a conclusão do PR.
3. Em `ws-prd-dpacademy`, confira o lakehouse `bronze_balldontlie`. No Environment
   `ws-prd-dpacademy` do GitHub (Settings → Environments, ou a aba Deployments), confira a
   publicação com commit, horário e resultado.

## 8. Referências de ambiente e agendamento (US3, FR-009, FR-012, SC-006)

Depois que a 001 publicar `nb-incr-030-bronze-balldontlie-jogos` e
`pl-010-bronze-balldontlie-nba`:

1. Abra o notebook em produção. Esperado: lakehouse padrão = `bronze_balldontlie` de **produção**.
2. Liste os agendamentos pela API nos dois workspaces. Esperado: o pipeline agendado às 06:00
   (`E. South America Standard Time`) só em `ws-prd-dpacademy`; nenhum em `ws-dev-dpacademy`.
3. No dia seguinte, consulte `ctl_ingestion_runs` em produção. Esperado: uma execução com
   `environment = 'prd'`; nenhuma execução nova em dev.

## 9. Renomeação sem órfão e divergência (edge cases)

1. Renomeie um item em dev, publique. Esperado: em produção só existe o nome novo.
2. Altere um item direto em produção e depois publique qualquer PR. Esperado: o item volta à versão
   de `main`, e o log do deploy o lista como republicado.

## 10. Laboratório DP-600 (research R12)

1. Em `dpl-dpacademy-lab`, use "Compare" depois de alterar um item em dev. Esperado: o item
   aparece como diferente entre "Desenvolvimento" e "Laboratório".
2. Implante um notebook da 001 e abra-o em `ws-lab-dpacademy`. Esperado: o lakehouse padrão é o
   `bronze_balldontlie` **do laboratório** (auto-binding ou regra de implantação).
3. Confira que `ws-prd-dpacademy` não mudou e que `ws-lab-dpacademy` não tem Git conectado nem
   agendamentos.
4. Confira que `docs/estudo-dp600.md` tem as seções §2, §4, §5 e §6 preenchidas.

## 11. Padrão em produção (SC-001)

```powershell
python ci/validate_names.py workspace/
```

E, no resumo do último `deploy-prd`, zero avisos de tabela. Esperado: 100% dos itens e tabelas no
padrão.
