# dpacademy

Case de engenharia de dados de ponta a ponta no Microsoft Fabric, da ingestão à camada Gold, com
versionamento no GitHub e CI/CD com GitHub Actions.

## Fontes de dados

Duas APIs públicas e gratuitas do governo brasileiro:

| Fonte | O que vem | Volume (2019–2026) | Acesso |
|---|---|---|---|
| [Dados Abertos da Câmara dos Deputados](https://dadosabertos.camara.leg.br/swagger/api.html) | deputados, partidos, legislaturas e despesas da cota parlamentar | 1,7 milhão de despesas, 1.161 deputados com despesa | sem chave; arquivo anual para o histórico e API para a carga diária |
| [Portal da Transparência](https://api.portaldatransparencia.gov.br/swagger-ui/index.html) | emendas parlamentares e cadastro dos fornecedores (sanções e vínculos com o governo federal) | 55 mil emendas, cerca de 68 mil CNPJs | chave gratuita via gov.br, guardada fora do Git ([ADR-003](docs/adr-003-segredo-api-em-lakehouse-files.md)) |

O primeiro case é **`gastos`**: quanto cada deputado gasta da cota parlamentar, com quais
fornecedores e quanto destina em emendas. As fontes só se cruzam na Gold.

## Arquitetura

| Camada | Responsabilidade | Itens no Fabric |
|---|---|---|
| Ingestão e Bronze | Resposta da fonte em Delta (JSON em `payload`), sem transformação, com colunas de auditoria e registro de cada lote em `ctl_ingestion_runs` | `bronze_camara`: `nb-util-010-bronze-camara-cliente`, `nb-util-020-bronze-camara-gravacao`, `nb-full-030-bronze-camara-cadastros`, `nb-incr-040-bronze-camara-despesas`, pipeline `pl-010-bronze-camara-gastos`. `bronze_transparencia`: `nb-util-010-bronze-transparencia-cliente`, `nb-util-020-bronze-transparencia-gravacao`, `nb-incr-030-bronze-transparencia-emendas`, `nb-incr-040-bronze-transparencia-fornecedores`, pipeline `pl-010-bronze-transparencia-gastos` |
| Silver | Tipagem, nomes em português, deduplicação por chave e carga incremental (`MERGE`), com verificações de qualidade registradas em `ctl_quality_checks`; despesas só pelo arquivo anual ([ADR-004](docs/adr-004-silver-despesas-arquivo-e-chave-hash.md)) | `silver_camara` (`legislaturas`, `partidos`, `deputados`, `despesas`): `nb-util-010-silver-camara-comum`, `nb-full-020-silver-camara-cadastros`, `nb-incr-030-silver-camara-despesas`. `silver_transparencia` (`emendas`, `pessoa_juridica`): `nb-util-010-silver-transparencia-comum`, `nb-incr-020-silver-transparencia-emendas`, `nb-incr-030-silver-transparencia-fornecedores` |
| Orquestração | Rotina diária às 04:00, só em produção: Bronze da Câmara, Bronze do Portal, Silver das duas fontes e Gold, em sequência | `pl-010-orq-gastos-diario` (os pipelines por fonte ficam sem agenda, para disparo manual) |
| Gold | Star schema do case, reconstruído a cada noite com verificações antes de gravar (unicidade, obrigatórias, integridade, conciliação com a Silver, privacidade); CPF de fornecedor mascarado ([ADR-005](docs/adr-005-gold-reconstruida-e-direct-lake.md)) | `gold_gastos`: `fat_despesas` (uma linha por despesa), `fat_emendas` (uma linha por emenda, tipo e localidade) e as dimensões `dim_data`, `dim_deputado`, `dim_partido`, `dim_uf`, `dim_tipo_despesa`, `dim_fornecedor`, `dim_autor_emenda`, `dim_tipo_emenda`, `dim_funcao`, `dim_localidade`; `nb-util-010-gold-gastos-comum`, `nb-full-020-gold-gastos-modelo` |
| Consumo | Modelo semântico Direct Lake sobre o SQL endpoint da Gold, com medidas de cota e emendas e o deputado comum aos dois fatos; relatório na próxima feature | `sm-gastos` (relatório: `rpt-gastos-parlamentares`) |

Bronze e Silver são organizadas por fonte e compartilhadas entre os cases. Cada case tem a sua
Gold, o seu modelo semântico e os seus relatórios. Especificações: ingestão em
[specs/003-gastos-bronze-ingestion](specs/003-gastos-bronze-ingestion/spec.md), Silver em
[specs/004-gastos-silver](specs/004-gastos-silver/spec.md) e Gold e modelo semântico em
[specs/005-gastos-gold](specs/005-gastos-gold/spec.md).

## Ambientes e branches

| Branch | Workspace | Como recebe mudanças |
|---|---|---|
| `dev` | `ws-dev-dpacademy` | Git integration do Fabric, pasta `workspace/` |
| `main` | `ws-prd-dpacademy` | Publicado pelo pipeline `deploy-prd`; sem Git integration |

## Fluxo de CI/CD

1. Desenvolver no `ws-dev-dpacademy` e fazer commit pelo controle de código do Fabric em `dev`.
2. Abrir um pull request de `dev` para `main`. O workflow `pr-validation` confere os nomes, roda
   os testes e procura segredos em todo o histórico. Qualquer falha bloqueia o PR.
3. Concluir o PR (squash). O ruleset de `main` bloqueia push direto, inclusive de administradores.
4. O workflow `deploy-prd` publica em `ws-prd-dpacademy` com o `fabric-cicd`. Ele troca os IDs de ambiente,
   remove itens órfãos e aplica os agendamentos de `ci/schedules.json`.

Decisões e riscos: [docs/adr-002-cicd-fabric-cicd.md](docs/adr-002-cicd-fabric-cicd.md).

## Convenção de nomes

O padrão completo, com exemplos por tipo de item e camada, está em
[docs/padrao-nomenclatura.md](docs/padrao-nomenclatura.md). Para validar localmente:

```powershell
python ci/validate_names.py workspace/
python -m pytest tests/unit -q
```

## Estrutura do repositório

```
dpacademy/
├── workspace/        # itens do Fabric, gravados pela Git integration (não editar à mão)
├── .github/          # workflows pr-validation e deploy-prd, template de PR
├── ci/               # validador de nomes, deploy e configuração por ambiente
├── tests/            # testes unitários (pytest)
├── docs/             # padrão de nomenclatura e decisões de arquitetura
├── specs/            # especificações do Spec Kit, uma pasta por feature
├── backlog/          # backlog para importar como Issues do GitHub
└── README.md
```
