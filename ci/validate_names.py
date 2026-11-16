"""Valida os nomes dos itens do Fabric e das tabelas contra o padrão do dpacademy.

Contrato: specs/002-naming-standard-cicd/contracts/naming-rules.md
Padrão: docs/padrao-nomenclatura.md

Uso: python ci/validate_names.py <pasta>   (no CI: python ci/validate_names.py workspace/)
Sai com 0 sem violações e 1 com pelo menos uma.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SEQ = r"(?!000)\d{2}0"
NOME = r"[a-z0-9]+"

# Bronze e Silver: nome da entidade da fonte, sem prefixo, ou ctl_<assunto> para controle
# (constituição v3.0.0, Princípio IV). Basta estar em snake_case sem acentos.

# tipo do Fabric -> (regra legível, expressão). Grupos nomeados alimentam a checagem de sequencial.
ITEM_RULES: dict[str, tuple[str, re.Pattern[str]]] = {
    "Lakehouse": (
        "bronze_<fonte> | silver_<fonte> | gold_<case>",
        re.compile(rf"^(?:bronze|silver|gold)_{NOME}$"),
    ),
    "Notebook": (
        "nb-<full|incr|util>-<999>-<camada>-<fonte|case>-<assunto>",
        re.compile(
            rf"^nb-(?:full|incr|util)-(?P<seq>{SEQ})-(?P<camada>bronze|silver|gold)"
            rf"-(?P<escopo>{NOME})-{NOME}$"
        ),
    ),
    "Dataflow": (
        "df-<full|incr>-<999>-<camada>-<fonte|case>-<assunto>",
        re.compile(
            rf"^df-(?:full|incr)-(?P<seq>{SEQ})-(?P<camada>bronze|silver|gold)"
            rf"-(?P<escopo>{NOME})-{NOME}$"
        ),
    ),
    "DataPipeline": (
        "pl-<999>-<camada|orq>-<fonte|case>-<assunto>",
        re.compile(
            rf"^pl-(?P<seq>{SEQ})-(?P<camada>bronze|silver|gold|orq)-(?P<escopo>{NOME})-{NOME}$"
        ),
    ),
    "SemanticModel": ("sm-<case>", re.compile(rf"^sm-{NOME}$")),
    "Report": ("rpt-<case>-<assunto>", re.compile(rf"^rpt-{NOME}-{NOME}$")),
}

_TABELA = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
_TABELA_GOLD = re.compile(r"^(?:dim|fat|agg)_[a-z0-9_]+$")


@dataclass
class Violacao:
    platform: Path
    item_type: str
    display_name: str
    regra: str
    motivo: str

    def linha(self) -> str:
        return (
            f'ERRO {self.platform}: {self.item_type} "{self.display_name}" '
            f"viola {self.regra}: {self.motivo}"
        )


def _motivo_formato(name: str) -> str:
    if any(c.isupper() for c in name):
        return "contém letra maiúscula"
    if not name.isascii():
        return "contém acento ou caractere especial"
    if " " in name:
        return "contém espaço"
    return "nome fora do formato"


def _read_platform(platform: Path) -> tuple[str, str]:
    metadata = json.loads(platform.read_text(encoding="utf-8-sig"))["metadata"]
    return metadata["type"], metadata["displayName"]


def validate_items(root: Path) -> list[Violacao]:
    """Confere todo `.platform` abaixo de `root`."""
    violacoes: list[Violacao] = []
    sequenciais: dict[tuple[str, str, str, str], str] = {}

    for platform in sorted(root.rglob(".platform")):
        item_type, name = _read_platform(platform)
        if item_type not in ITEM_RULES:
            violacoes.append(
                Violacao(
                    platform,
                    item_type,
                    name,
                    "Princípio IV",
                    "tipo sem regra; defina a regra em docs/padrao-nomenclatura.md e em "
                    "ci/validate_names.py antes de publicar",
                )
            )
            continue

        regra, pattern = ITEM_RULES[item_type]
        match = pattern.match(name)
        if not match:
            violacoes.append(Violacao(platform, item_type, name, regra, _motivo_formato(name)))
            continue

        if "seq" in pattern.groupindex:
            chave = (item_type, match["camada"], match["escopo"], match["seq"])
            if chave in sequenciais:
                violacoes.append(
                    Violacao(
                        platform,
                        item_type,
                        name,
                        "sequencial único por tipo, camada e fonte ou case",
                        f"sequencial {match['seq']} já usado por \"{sequenciais[chave]}\"",
                    )
                )
            else:
                sequenciais[chave] = name

    return violacoes


def validate_table_name(lakehouse: str, table: str) -> str | None:
    """Devolve None se a tabela segue o padrão do seu lakehouse, ou o motivo da divergência."""
    if lakehouse.startswith(("bronze_", "silver_")):
        if not _TABELA.match(table):
            return f"tabela de {lakehouse} precisa estar em snake_case, sem acentos"
        return None
    if lakehouse.startswith("gold_"):
        if not _TABELA_GOLD.match(table):
            return f"tabela de {lakehouse} precisa começar com dim_, fat_ ou agg_"
        return None
    return f"lakehouse {lakehouse} fora do padrão"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("uso: python ci/validate_names.py <pasta>", file=sys.stderr)
        return 2

    root = Path(argv[0])
    if not root.is_dir():
        print(f"{root} não existe; nenhum item a validar")
        return 0

    violacoes = validate_items(root)
    for v in violacoes:
        print(v.linha())
        # anotação do GitHub Actions: aparece no PR, ligada ao arquivo
        print(f"::error file={v.platform.as_posix()}::{v.linha()}")

    total = len(list(root.rglob(".platform")))
    print(f"{total} item(ns) verificado(s), {len(violacoes)} violação(ões)")
    return 1 if violacoes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
