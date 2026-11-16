# dpacademy

Case de engenharia de dados de ponta a ponta no Microsoft Fabric, da ingestão à camada Gold, com
versionamento no GitHub e CI/CD com GitHub Actions.

## Fonte de dados

[API balldontlie](https://www.balldontlie.io/), plano gratuito. O primeiro case é a **NBA**,
com times, jogadores e jogos desde a temporada 1946-47. A ingestão é genérica por fonte: outras
ligas da mesma API (NFL, UCL) entram por configuração, como novos cases.

## Arquitetura

| Camada | Responsabilidade | Itens no Fabric |
|---|---|---|
| Ingestão e Bronze | Resposta da API em Delta, sem transformação, com colunas de auditoria | `bronze_balldontlie`; notebooks `nb-util-010-bronze-balldontlie-cliente`, `nb-full-020-bronze-balldontlie-cadastros` e `nb-incr-030-bronze-balldontlie-jogos`; pipeline `pl-010-bronze-balldontlie-nba` |
| Silver | Tipagem, limpeza, deduplicação e carga incremental (`MERGE`) | `silver_balldontlie` |
| Gold | Modelo dimensional (star schema) do case | `gold_nba` |
| Consumo | Modelo semântico Direct Lake e relatório | `sm-nba` e `rpt-nba-temporadas` |

Bronze e Silver são compartilhadas entre os cases da mesma fonte. Cada case tem a sua Gold, o seu
modelo semântico e os seus relatórios.

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
