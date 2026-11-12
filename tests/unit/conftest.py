"""Fixtures comuns dos testes unitários.

Os clientes HTTP vivem em notebooks do Fabric. A Git integration grava cada notebook como
`workspace/<nome>.Notebook/notebook-content.py`; aqui esse arquivo é executado num módulo novo
para testar o Python puro sem o Fabric (research R7 da feature 003).
"""

import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _codigo_executavel(texto: str) -> str:
    """Remove o que não é Python: comandos mágicos (%run, %%configure) e de shell (!pip).

    Os marcadores do Fabric (`# METADATA`, `# CELL`, `# META ...`) são comentários e ficam.
    """
    linhas = []
    for linha in texto.splitlines():
        if linha.lstrip().startswith(("%", "!")):
            continue
        linhas.append(linha)
    return "\n".join(linhas) + "\n"


def carregar_notebook_por_nome(nome: str) -> types.ModuleType:
    caminho = RAIZ / "workspace" / f"{nome}.Notebook" / "notebook-content.py"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe. Crie o notebook {nome} no ws-dev-dpacademy, faça o commit "
            "pela Git integration e traga a branch dev para a branch da feature."
        )
    modulo = types.ModuleType(nome.replace("-", "_"))
    modulo.__file__ = str(caminho)
    exec(compile(_codigo_executavel(caminho.read_text(encoding="utf-8")), str(caminho), "exec"), modulo.__dict__)
    return modulo


@pytest.fixture
def carregar_notebook():
    """Devolve a função que carrega um notebook do workspace como módulo."""
    return carregar_notebook_por_nome
