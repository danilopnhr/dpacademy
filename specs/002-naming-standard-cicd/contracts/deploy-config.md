# Contrato: arquivos de configuração do deploy

Os três arquivos ficam em `ci/`, fora de `workspace/`, e não contêm segredos.

## `ci/environments.json`

```json
{
  "dev": { "workspace_name": "ws-dev-dpacademy", "workspace_id": "<guid>" },
  "prd": { "workspace_name": "ws-prd-dpacademy", "workspace_id": "<guid>" }
}
```

- `deploy.py` só aceita `--environment prd` (dev é alimentado pela Git integration).
- Antes de publicar, `deploy.py` confere que o nome do workspace retornado pela API é igual a
  `workspace_name`, para não publicar no workspace errado por um ID trocado.

## `ci/parameter.yml` (formato do `fabric-cicd`)

Troca os IDs de dev pelos de produção no conteúdo dos itens:

| O que é trocado | Valor em dev (literal) | Valor em prd |
|---|---|---|
| Workspace nos metadados dos notebooks e nas atividades de pipeline | GUID do `ws-dev-dpacademy` | `$workspace.$id` |
| Lakehouse padrão dos notebooks da Bronze | GUID do `bronze_balldontlie` de dev | `$items.Lakehouse.bronze_balldontlie.$id` |
| Lakehouse padrão das features seguintes | GUID de cada lakehouse em dev | `$items.Lakehouse.<nome>.$id` |

Regra: toda entrada usa `find_value` com o GUID de dev e `replace_value` com `prd` resolvido
dinamicamente; nenhum GUID de produção é escrito à mão. Um notebook novo com lakehouse padrão
diferente exige uma entrada nova no mesmo PR.

## `ci/schedules.json`

```json
[
  {
    "item": "pl-010-bronze-balldontlie-nba",
    "type": "DataPipeline",
    "job_type": "Pipeline",
    "enabled": true,
    "times": ["06:00"],
    "time_zone": "E. South America Standard Time"
  }
]
```

- Aplicado só em produção. Um item listado que não exista em produção falha o deploy.
- Remover uma entrada desativa o agendamento correspondente em produção na publicação seguinte.
