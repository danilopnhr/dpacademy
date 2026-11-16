"""Testes de ci/validate_names.py (contrato: specs/002-naming-standard-cicd/contracts/naming-rules.md)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "validate_names", Path(__file__).resolve().parents[2] / "ci" / "validate_names.py"
)
vn = importlib.util.module_from_spec(_SPEC)
sys.modules["validate_names"] = vn  # dataclasses resolve o módulo por sys.modules
_SPEC.loader.exec_module(vn)


def _item(root: Path, item_type: str, name: str, folder: str | None = None) -> Path:
    """Cria um .platform falso como a Git integration grava."""
    item_dir = root / f"{folder or name}.{item_type}"
    item_dir.mkdir(parents=True)
    platform = item_dir / ".platform"
    platform.write_text(
        json.dumps({"metadata": {"type": item_type, "displayName": name}, "config": {}}),
        encoding="utf-8",
    )
    return platform


VALIDOS = [
    ("Lakehouse", "bronze_balldontlie"),
    ("Lakehouse", "silver_balldontlie"),
    ("Lakehouse", "gold_nba"),
    ("Notebook", "nb-incr-030-bronze-balldontlie-jogos"),
    ("Notebook", "nb-util-010-bronze-balldontlie-cliente"),
    ("Dataflow", "df-full-010-silver-balldontlie-cadastros"),
    ("DataPipeline", "pl-010-orq-nba-diario"),
    ("DataPipeline", "pl-010-bronze-balldontlie-nba"),
    ("SemanticModel", "sm-nba"),
    ("Report", "rpt-nba-temporadas"),
]

INVALIDOS = [
    ("Notebook", "nb_teste"),
    ("Lakehouse", "lh_bronze"),
    ("DataPipeline", "pl-inc-010-bronze-balldontlie-nba"),
    ("Notebook", "nb-full-000-bronze-balldontlie-x"),
    ("Notebook", "nb-full-015-bronze-balldontlie-x"),
    ("Notebook", "nb-full-010-Bronze-balldontlie-x"),
    ("Notebook", "nb-full-010-bronze-balldontlie-açao"),
]


@pytest.mark.parametrize("item_type,name", VALIDOS)
def test_nome_valido_por_tipo(tmp_path, item_type, name):
    _item(tmp_path, item_type, name)
    assert vn.validate_items(tmp_path) == []


@pytest.mark.parametrize("item_type,name", INVALIDOS)
def test_nome_invalido(tmp_path, item_type, name):
    _item(tmp_path, item_type, name)
    violacoes = vn.validate_items(tmp_path)
    assert len(violacoes) == 1
    assert violacoes[0].display_name == name


def test_motivo_aponta_maiuscula_e_acento(tmp_path):
    _item(tmp_path, "Notebook", "nb-full-010-Bronze-balldontlie-x")
    _item(tmp_path, "Notebook", "nb-full-020-bronze-balldontlie-açao")
    motivos = sorted(v.motivo for v in vn.validate_items(tmp_path))
    assert any("maiúscula" in m for m in motivos)
    assert any("acento" in m for m in motivos)


def test_sequencial_repetido_na_mesma_camada_e_escopo(tmp_path):
    _item(tmp_path, "Notebook", "nb-full-010-gold-nba-dimensoes")
    _item(tmp_path, "Notebook", "nb-incr-010-gold-nba-fatos")
    violacoes = vn.validate_items(tmp_path)
    assert len(violacoes) == 1
    assert "sequencial 010" in violacoes[0].motivo


def test_mesmo_sequencial_em_escopos_diferentes_e_permitido(tmp_path):
    _item(tmp_path, "Notebook", "nb-full-010-gold-nba-dimensoes")
    _item(tmp_path, "Notebook", "nb-full-010-gold-nfl-dimensoes")
    _item(tmp_path, "DataPipeline", "pl-010-orq-nba-diario")
    assert vn.validate_items(tmp_path) == []


def test_tipo_sem_regra_bloqueia(tmp_path):
    _item(tmp_path, "VariableLibrary", "vl-dpacademy")
    violacoes = vn.validate_items(tmp_path)
    assert len(violacoes) == 1
    assert "tipo sem regra" in violacoes[0].motivo


def test_saida_e_codigo_com_violacao(tmp_path, capsys):
    platform = _item(tmp_path, "Notebook", "nb_teste")
    assert vn.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert f'ERRO {platform}: Notebook "nb_teste" viola ' in out
    assert f"::error file={platform.as_posix()}::" in out


def test_saida_e_codigo_sem_violacao(tmp_path, capsys):
    _item(tmp_path, "Lakehouse", "bronze_balldontlie")
    assert vn.main([str(tmp_path)]) == 0
    assert "ERRO" not in capsys.readouterr().out


def test_pasta_inexistente_nao_falha(tmp_path, capsys):
    assert vn.main([str(tmp_path / "workspace")]) == 0


@pytest.mark.parametrize(
    "lakehouse,table,valida",
    [
        ("bronze_balldontlie", "nba_games", True),
        ("bronze_balldontlie", "ctl_ingestion_runs", True),
        ("bronze_balldontlie", "games", False),
        ("bronze_balldontlie", "ingestion_runs", False),
        ("bronze_balldontlie", "nfl_games", False),
        ("silver_balldontlie", "nba_jogos", True),
        ("gold_nba", "dim_time", True),
        ("gold_nba", "fat_jogo", True),
        ("gold_nba", "agg_desempenho_temporada", True),
        ("gold_nba", "jogos", False),
    ],
)
def test_nome_de_tabela(lakehouse, table, valida):
    assert (vn.validate_table_name(lakehouse, table) is None) is valida
