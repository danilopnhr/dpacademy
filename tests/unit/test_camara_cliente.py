"""Testes do cliente da API da Câmara (contrato: specs/003-gastos-bronze-ingestion/contracts/camara-api.md)."""

import json

import pytest
import requests
from requests.structures import CaseInsensitiveDict

NOTEBOOK = "nb-util-010-bronze-camara-cliente"


class RespostaFalsa:
    def __init__(self, status=200, corpo=None, headers=None, conteudo=b""):
        self.status_code = status
        self._corpo = corpo
        self.headers = CaseInsensitiveDict(headers or {})
        self.content = conteudo if conteudo else (json.dumps(corpo).encode() if corpo is not None else b"")
        self.text = self.content.decode("utf-8", errors="replace")

    def json(self):
        return self._corpo


class SessaoFalsa:
    """Devolve as respostas na ordem e registra as chamadas."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.chamadas.append({"url": url, "params": dict(params) if params else None, "headers": headers})
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Relogio:
    def __init__(self):
        self.agora = 1000.0
        self.esperas = []

    def monotonic(self):
        return self.agora

    def dormir(self, s):
        self.esperas.append(s)
        self.agora += s


@pytest.fixture
def mod(carregar_notebook):
    return carregar_notebook(NOTEBOOK)


def _cliente(mod, respostas, relogio=None):
    relogio = relogio or Relogio()
    sessao = SessaoFalsa(respostas)
    c = mod.ClienteCamara(sessao=sessao, dormir=relogio.dormir, relogio=relogio.monotonic)
    return c, sessao, relogio


def _pagina(dados, proxima=None, total=None):
    links = [{"rel": "self", "href": "x"}]
    if proxima:
        links.append({"rel": "next", "href": proxima})
    headers = {"X-Total-Count": str(total)} if total is not None else {}
    return RespostaFalsa(200, {"dados": dados, "links": links}, headers)


def test_paginar_segue_link_next_ate_o_fim(mod):
    p2 = "https://dadosabertos.camara.leg.br/api/v2/partidos?pagina=2&itens=100"
    c, sessao, _ = _cliente(mod, [_pagina([{"id": 1}, {"id": 2}], p2, total=3), _pagina([{"id": 3}])])
    registros = list(c.paginar("/partidos"))
    assert [r["id"] for r in registros] == [1, 2, 3]
    assert c.ultimo_total == 3
    assert sessao.chamadas[0]["url"] == "https://dadosabertos.camara.leg.br/api/v2/partidos"
    assert sessao.chamadas[0]["params"] == {"itens": 100, "pagina": 1}
    assert sessao.chamadas[1]["url"] == p2
    assert sessao.chamadas[1]["params"] is None


def test_paginar_preserva_filtros(mod):
    c, sessao, _ = _cliente(mod, [_pagina([], total=0)])
    assert list(c.paginar("/deputados/1/despesas", {"ano": 2026, "mes": 10})) == []
    assert sessao.chamadas[0]["params"] == {"ano": 2026, "mes": 10, "itens": 100, "pagina": 1}
    assert c.ultimo_total == 0


def test_detalhe_devolve_objeto(mod):
    c, _, _ = _cliente(mod, [RespostaFalsa(200, {"dados": {"id": 204379, "nomeCivil": "X"}})])
    assert c.detalhe("/deputados/204379")["id"] == 204379


def test_envia_accept_json_sem_dado_pessoal(mod):
    c, sessao, _ = _cliente(mod, [_pagina([])])
    list(c.paginar("/partidos"))
    h = sessao.chamadas[0]["headers"]
    assert h["Accept"] == "application/json"
    assert "@" not in h.get("User-Agent", "")


def test_ritmo_minimo_entre_requisicoes(mod):
    relogio = Relogio()
    c, _, _ = _cliente(mod, [RespostaFalsa(200, {"dados": {}}), RespostaFalsa(200, {"dados": {}})], relogio)
    c.detalhe("/a")
    c.detalhe("/b")
    assert relogio.esperas == [pytest.approx(0.25)]


def test_429_respeita_retry_after(mod):
    c, _, relogio = _cliente(mod, [RespostaFalsa(429, headers={"Retry-After": "7"}), RespostaFalsa(200, {"dados": {}})])
    c.detalhe("/a")
    assert 7 in relogio.esperas
    assert c.retries == 1
    assert c.requests_made == 2


def test_5xx_e_conexao_com_espera_exponencial_e_falha_apos_5_retentativas(mod):
    respostas = [RespostaFalsa(503), requests.ConnectionError("caiu")] + [RespostaFalsa(500)] * 4
    c, _, relogio = _cliente(mod, respostas)
    with pytest.raises(mod.ErroFonte) as e:
        c.detalhe("/a")
    assert [s for s in relogio.esperas if s >= 15] == [15, 30, 60, 120, 240]
    assert c.requests_made == 6
    assert c.retries == 5
    assert "6 tentativas" in str(e.value)


def test_outro_4xx_falha_na_hora_com_corpo_truncado(mod):
    c, _, relogio = _cliente(mod, [RespostaFalsa(400, conteudo=("x" * 1000).encode())])
    with pytest.raises(mod.ErroFonte) as e:
        c.detalhe("/a")
    assert "HTTP 400" in str(e.value)
    assert "x" * 300 in str(e.value)
    assert "x" * 301 not in str(e.value)
    assert c.retries == 0
    assert not [s for s in relogio.esperas if s >= 15]


def test_baixar_cotas_grava_zip(mod, tmp_path):
    c, sessao, _ = _cliente(mod, [RespostaFalsa(200, conteudo=b"PK\x03\x04zip")])
    caminho = c.baixar_cotas(2024, tmp_path)
    assert sessao.chamadas[0]["url"] == "https://www.camara.leg.br/cotas/Ano-2024.csv.zip"
    assert caminho == tmp_path / "Ano-2024.csv.zip"
    assert caminho.read_bytes() == b"PK\x03\x04zip"


def test_baixar_cotas_404_devolve_none(mod, tmp_path):
    c, _, _ = _cliente(mod, [RespostaFalsa(404)])
    assert c.baixar_cotas(2030, tmp_path) is None
    assert not (tmp_path / "Ano-2030.csv.zip").exists()


@pytest.mark.parametrize(
    "bruto,esperado",
    [("﻿txNomeParlamentar", "txNomeParlamentar"), ('"cpf"', "cpf"), (" sgUF ", "sgUF"), ("ideDocumento", "ideDocumento")],
)
def test_normalizar_cabecalho(mod, bruto, esperado):
    assert mod.normalizar_cabecalho(bruto) == esperado


# --- US2: janela da carga recorrente (T017) ---

from datetime import date  # noqa: E402


@pytest.mark.parametrize(
    "hoje,esperado",
    [
        (date(2026, 11, 12), [(2026, 9), (2026, 10), (2026, 11)]),
        (date(2026, 1, 15), [(2025, 11), (2025, 12), (2026, 1)]),
        (date(2026, 2, 28), [(2025, 12), (2026, 1), (2026, 2)]),
    ],
)
def test_meses_padrao_corrente_e_dois_anteriores(mod, hoje, esperado):
    assert mod.meses_padrao(hoje) == esperado


def test_meses_padrao_sem_data_usa_hoje_em_sao_paulo(mod):
    meses = mod.meses_padrao()
    assert len(meses) == 3 and meses == sorted(meses)


def test_ler_meses(mod):
    assert mod.ler_meses("2026-08, 2026-09") == [(2026, 8), (2026, 9)]
    assert mod.ler_meses("2026-09,2026-08,2026-09") == [(2026, 8), (2026, 9)]


@pytest.mark.parametrize("texto", ["2026-13", "2026/08", "08-2026", "abc"])
def test_ler_meses_invalido(mod, texto):
    with pytest.raises(ValueError):
        mod.ler_meses(texto)
