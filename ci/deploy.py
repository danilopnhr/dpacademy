"""Publica o conteúdo de main em ws-prd-dpacademy.

Contratos: specs/002-naming-standard-cicd/contracts/ci-pipelines.md e deploy-config.md
Decisão: docs/adr-002-cicd-fabric-cicd.md

Etapas:
1. publica os itens de workspace/ com fabric-cicd, trocando os IDs por ci/parameter.yml, e remove
   os órfãos;
2. aplica os agendamentos de ci/schedules.json (o fabric-cicd não publica agendamentos);
3. confere os nomes das tabelas dos lakehouses de produção (só avisos).

Credencial: FABRIC_TENANT_ID, SP_CLIENT_ID e SP_CLIENT_SECRET nas variáveis de ambiente.
Uso: python ci/deploy.py --environment prd
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from azure.identity import ClientSecretCredential
from fabric_cicd import FabricWorkspace, publish_all_items, unpublish_all_orphan_items

from validate_names import validate_table_name

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / "ci"
REPOSITORY = ROOT / "workspace"
PARAMETER_FILE = CI / "parameter.yml"

API = "https://api.fabric.microsoft.com/v1"
SCOPE = "https://api.fabric.microsoft.com/.default"

TIPOS_BASE = ["Lakehouse", "Notebook", "DataPipeline"]
TIPOS_OPCIONAIS = ["SemanticModel", "Report"]
# Tipos agendáveis cujos agendamentos fora de ci/schedules.json são desativados.
JOB_TYPES = {"DataPipeline": "Pipeline", "Notebook": "RunNotebook"}
SCHEDULE_END = "2099-12-31T23:59:00"


def _erro(msg: str) -> None:
    print(f"ERRO {msg}")
    print(f"::error::{msg}")


def _aviso(msg: str) -> None:
    print(f"AVISO {msg}")
    print(f"::warning::{msg}")


class FabricApi:
    """Cliente mínimo da API REST do Fabric, com retentativa em 429 e 5xx."""

    def __init__(self, credential: ClientSecretCredential) -> None:
        self._credential = credential
        self._session = requests.Session()

    def request(self, method: str, url: str, body: dict | None = None) -> dict:
        if not url.startswith("http"):
            url = f"{API}{url}"
        for tentativa in range(5):
            token = self._credential.get_token(SCOPE).token
            resp = self._session.request(
                method, url, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=60
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(int(resp.headers.get("Retry-After", 2 ** (tentativa + 2))))
                continue
            if not resp.ok:
                raise RuntimeError(f"{method} {url} → HTTP {resp.status_code}: {resp.text[:500]}")
            return resp.json() if resp.content else {}
        raise RuntimeError(f"{method} {url} → sem sucesso após 5 tentativas")

    def list(self, url: str) -> list[dict]:
        """GET paginado pelo continuationUri das APIs de listagem do Fabric."""
        itens: list[dict] = []
        while url:
            page = self.request("GET", url)
            itens.extend(page.get("value", page.get("data", [])))
            url = page.get("continuationUri")
        return itens


def carregar_ambiente(nome: str) -> dict:
    env = json.loads((CI / "environments.json").read_text(encoding="utf-8"))[nome]
    pendentes = [f for f in (CI / "environments.json", PARAMETER_FILE) if "<GUID" in f.read_text(encoding="utf-8")]
    if pendentes:
        raise SystemExit(
            "configuração incompleta: substitua os marcadores <GUID ...> em "
            + ", ".join(str(p.relative_to(ROOT)) for p in pendentes)
        )
    return env


def credencial() -> ClientSecretCredential:
    faltando = [v for v in ("FABRIC_TENANT_ID", "SP_CLIENT_ID", "SP_CLIENT_SECRET") if not os.environ.get(v)]
    if faltando:
        raise SystemExit(f"variáveis ausentes: {', '.join(faltando)} (secrets do Environment ws-prd-dpacademy no GitHub)")
    return ClientSecretCredential(
        tenant_id=os.environ["FABRIC_TENANT_ID"],
        client_id=os.environ["SP_CLIENT_ID"],
        client_secret=os.environ["SP_CLIENT_SECRET"],
    )


def conferir_workspace(api: FabricApi, env: dict) -> None:
    nome = api.request("GET", f"/workspaces/{env['workspace_id']}")["displayName"]
    if nome != env["workspace_name"]:
        raise SystemExit(f"o ID configurado aponta para '{nome}', não para '{env['workspace_name']}'")


def tipos_no_escopo() -> list[str]:
    presentes = {
        json.loads(p.read_text(encoding="utf-8-sig"))["metadata"]["type"]
        for p in REPOSITORY.rglob(".platform")
    }
    return TIPOS_BASE + [t for t in TIPOS_OPCIONAIS if t in presentes]


def publicar(env: dict, cred: ClientSecretCredential) -> None:
    tipos = tipos_no_escopo()
    print(f"Publicando {REPOSITORY.relative_to(ROOT)}/ em {env['workspace_name']} (tipos: {', '.join(tipos)})")
    workspace = FabricWorkspace(
        workspace_id=env["workspace_id"],
        repository_directory=str(REPOSITORY),
        item_type_in_scope=tipos,
        environment="prd",
        token_credential=cred,
        parameter_file_path=str(PARAMETER_FILE),
    )
    publish_all_items(workspace)
    unpublish_all_orphan_items(workspace)


def _config_agendamento(entrada: dict) -> dict:
    return {
        "type": "Daily",
        "startDateTime": time.strftime("%Y-%m-%dT00:00:00"),
        "endDateTime": SCHEDULE_END,
        "localTimeZoneId": entrada["time_zone"],
        "times": entrada["times"],
    }


def _igual(atual: dict, entrada: dict) -> bool:
    cfg = atual.get("configuration", {})
    return (
        atual.get("enabled") == entrada["enabled"]
        and cfg.get("type") == "Daily"
        and cfg.get("times") == entrada["times"]
        and cfg.get("localTimeZoneId") == entrada["time_zone"]
    )


def aplicar_agendamentos(api: FabricApi, env: dict) -> None:
    entradas = json.loads((CI / "schedules.json").read_text(encoding="utf-8"))
    ws = env["workspace_id"]
    itens = {(i["type"], i["displayName"]): i["id"] for i in api.list(f"/workspaces/{ws}/items")}

    agendados: set[tuple[str, str]] = set()
    for entrada in entradas:
        chave = (entrada["type"], entrada["item"])
        if chave not in itens:
            raise SystemExit(f"agendamento para {entrada['type']} '{entrada['item']}', que não existe em produção")
        agendados.add(chave)
        base = f"/workspaces/{ws}/items/{itens[chave]}/jobs/{entrada['job_type']}/schedules"
        existentes = api.list(base)
        corpo = {"enabled": entrada["enabled"], "configuration": _config_agendamento(entrada)}
        if not existentes:
            api.request("POST", base, corpo)
        elif not _igual(existentes[0], entrada):
            api.request("PATCH", f"{base}/{existentes[0]['id']}", corpo)
        for extra in existentes[1:]:
            if extra.get("enabled"):
                api.request("PATCH", f"{base}/{extra['id']}", {"enabled": False, "configuration": extra["configuration"]})
        print(f"agendamento {entrada['item']} ok ({', '.join(entrada['times'])} {entrada['time_zone']})")

    # Agendamentos fora do arquivo são desativados: o arquivo é a única fonte de agendamento.
    for (tipo, nome), item_id in itens.items():
        if tipo not in JOB_TYPES or (tipo, nome) in agendados:
            continue
        base = f"/workspaces/{ws}/items/{item_id}/jobs/{JOB_TYPES[tipo]}/schedules"
        for sched in api.list(base):
            if sched.get("enabled"):
                api.request("PATCH", f"{base}/{sched['id']}", {"enabled": False, "configuration": sched["configuration"]})
                print(f"agendamento de {nome} desativado (fora de ci/schedules.json)")


def conferir_tabelas(api: FabricApi, env: dict) -> int:
    ws = env["workspace_id"]
    divergencias = 0
    for lakehouse in api.list(f"/workspaces/{ws}/lakehouses"):
        try:
            tabelas = api.list(f"/workspaces/{ws}/lakehouses/{lakehouse['id']}/tables")
        except RuntimeError as exc:
            _aviso(f"não foi possível listar as tabelas de {lakehouse['displayName']}: {exc}")
            continue
        for tabela in tabelas:
            motivo = validate_table_name(lakehouse["displayName"], tabela["name"])
            if motivo:
                divergencias += 1
                _aviso(f"tabela {lakehouse['displayName']}.{tabela['name']}: {motivo}")
    print(f"relatório de tabelas: {divergencias} divergência(s)")
    return divergencias


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--environment", required=True, choices=["prd"], help="dev é alimentado pela Git integration")
    args = parser.parse_args(argv)

    env = carregar_ambiente(args.environment)
    cred = credencial()
    api = FabricApi(cred)
    conferir_workspace(api, env)

    try:
        publicar(env, cred)
        aplicar_agendamentos(api, env)
    except Exception as exc:  # noqa: BLE001 - qualquer falha de publicação deixa o run vermelho
        _erro(f"publicação falhou: {exc}")
        return 1
    # Resumo do run no GitHub Actions
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as f:
            f.write(f"Publicado em **{env['workspace_name']}** a partir de `{os.environ.get('GITHUB_SHA', '?')[:7]}`.\n")

    conferir_tabelas(api, env)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
