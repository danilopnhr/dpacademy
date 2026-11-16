# dpacademy

Case de engenharia de dados de ponta a ponta no Microsoft Fabric, da ingestão à camada Gold, com
versionamento no GitHub e CI/CD com GitHub Actions.

## Fontes de dados

Duas APIs públicas e gratuitas do governo brasileiro:

| Fonte | O que vem | Volume (2019–2026) | Acesso |
|---|---|---|---|
| [Dados Abertos da Câmara dos Deputados](https://dadosabertos.camara.leg.br/swagger/api.html) | deputados, partidos, legislaturas e despesas da cota parlamentar | 1,4 milhão de despesas, 929 deputados | sem chave; arquivo anual para o histórico e API para a carga diária |
| [Portal da Transparência](https://api.portaldatransparencia.gov.br/swagger-ui/index.html) | emendas parlamentares e cadastro dos fornecedores (sanções e vínculos com o governo federal) | 55 mil emendas, cerca de 68 mil CNPJs | chave gratuita via gov.br, guardada fora do Git ([ADR-003](docs/adr-003-segredo-api-em-lakehouse-files.md)) |

O primeiro case é **`gastos`**: quanto cada deputado gasta da cota parlamentar, com quais
fornecedores e quanto destina em emendas. As fontes só se cruzam na Gold.

## Arquitetura

| Camada | Responsabilidade | Itens no Fabric |
|---|---|---|
| Ingestão e Bronze | Resposta da fonte em Delta (JSON em `payload`), sem transformação, com colunas de auditoria e registro de cada lote em `ctl_ingestion_runs` | `bronze_camara`: `nb-util-010-bronze-camara-cliente`, `nb-util-020-bronze-camara-gravacao`, `nb-full-030-bronze-camara-cadastros`, `nb-incr-040-bronze-camara-despesas`, pipeline `pl-010-bronze-camara-gastos`. `bronze_transparencia`: `nb-util-010-bronze-transparencia-cliente`, `nb-util-020-bronze-transparencia-gravacao`, `nb-incr-030-bronze-transparencia-emendas`, `nb-incr-040-bronze-transparencia-fornecedores`, pipeline `pl-010-bronze-transparencia-gastos` |
| Silver | Tipagem, limpeza, deduplicação e carga incremental (`MERGE`) | `silver_camara`, `silver_transparencia` (próxima feature) |
| Gold | Modelo dimensional (star schema) do case | `gold_gastos` |
| Consumo | Modelo semântico Direct Lake e relatório | `sm-gastos` e `rpt-gastos-parlamentares` |

Bronze e Silver são organizadas por fonte e compartilhadas entre os cases. Cada case tem a sua
Gold, o seu modelo semântico e os seus relatórios. A especificação da ingestão está em
[specs/003-gastos-bronze-ingestion](specs/003-gastos-bronze-ingestion/spec.md).

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
