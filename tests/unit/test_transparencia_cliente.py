"""Testes do cliente da API do Portal da Transparência
(contrato: specs/003-gastos-bronze-ingestion/contracts/transparencia-api.md)."""

import json
from datetime import datetime, timedelta, timezone

import pytest
import requests
from requests.structures import CaseInsensitiveDict

NOTEBOOK = "nb-util-010-bronze-transparencia-cliente"
CHAVE = "chave-de-teste-0123456789abcdef"
BRT = timezone(timedelta(hours=-3))


class RespostaFalsa:
    def __init__(self, status=200, corpo=None, headers=None, texto=None):
        self.status_code = status
        self._corpo = corpo
        self.headers = CaseInsensitiveDict(headers or {})
        self.text = texto if texto is not None else (json.dumps(corpo) if corpo is not None else "")
        self.content = self.text.encode()

    def json(self):
        if self._corpo is None:
            raise ValueError("sem JSON")
        return self._corpo


class SessaoFalsa:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.chamadas.append({"url": url, "params": dict(params) if params else None, "headers": dict(headers or {})})
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Relogio:
    """Relógio controlável: `agora` em horário de Brasília; `monotonic` avança com `dormir`."""

    def __init__(self, hora=10):
        self.inicio = datetime(2026, 11, 13, hora, 0, tzinfo=BRT)
        self.t = 0.0
        self.esperas = []

    def agora(self):
        return self.inicio + timedelta(seconds=self.t)

    def monotonic(self):
        return self.t

    def dormir(self, s):
        self.esperas.append(s)
        self.t += s


@pytest.fixture
def mod(carregar_notebook):
    return carregar_notebook(NOTEBOOK)


@pytest.fixture
def arquivo_chave(tmp_path):
    p = tmp_path / "transparencia_api_key"
    p.write_text(CHAVE, encoding="utf-8")
    return p


def _cliente(mod, arquivo_chave, respostas, relogio=None):
    relogio = relogio or Relogio()
    sessao = SessaoFalsa(respostas)
    c = mod.ClienteTransparencia(arquivo_chave, sessao=sessao, dormir=relogio.dormir,
                                 relogio=relogio.monotonic, agora=relogio.agora)
    return c, sessao, relogio


def test_envia_chave_no_header(mod, arquivo_chave):
    c, sessao, _ = _cliente(mod, arquivo_chave, [RespostaFalsa(200, [])])
    list(c.paginar("/emendas", {"ano": 2024}))
    assert sessao.chamadas[0]["headers"]["chave-api-dados"] == CHAVE
    assert sessao.chamadas[0]["url"] == "https://api.portaldatransparencia.gov.br/api-de-dados/emendas"


def test_chave_com_quebra_de_linha_e_bom_e_limpa(mod, tmp_path):
    p = tmp_path / "k"
    p.write_text("﻿" + CHAVE + "\r\n", encoding="utf-8")
    c, sessao, _ = _cliente(mod, p, [RespostaFalsa(200, [])])
    list(c.paginar("/emendas", {"ano": 2024}))
    assert sessao.chamadas[0]["headers"]["chave-api-dados"] == CHAVE


def test_chave_nao_aparece_em_repr(mod, arquivo_chave):
    c, _, _ = _cliente(mod, arquivo_chave, [])
    assert CHAVE not in repr(c)
    assert CHAVE not in str(vars(c).get("chave_mascarada", ""))


@pytest.mark.parametrize("conteudo", [None, "", "   \n"])
def test_arquivo_de_chave_ausente_ou_vazio(mod, tmp_path, conteudo):
    p = tmp_path / "k"
    if conteudo is not None:
        p.write_text(conteudo, encoding="utf-8")
    with pytest.raises(mod.ErroChave) as e:
        mod.ClienteTransparencia(p)
    assert "chave da API ausente ou inválida" in str(e.value)


@pytest.mark.parametrize("status", [401, 403])
def test_401_403_falham_na_hora_sem_retentativa_e_sem_vazar_chave(mod, arquivo_chave, status):
    corpo = f"chave {CHAVE} recusada"
    c, _, relogio = _cliente(mod, arquivo_chave, [RespostaFalsa(status, texto=corpo)])
    with pytest.raises(mod.ErroChave) as e:
        list(c.paginar("/emendas", {"ano": 2024}))
    assert "chave da API ausente ou inválida" in str(e.value)
    assert CHAVE not in str(e.value)
    assert c.retries == 0
    assert not [s for s in relogio.esperas if s >= 15]


def test_paginar_por_pagina_ate_lista_vazia(mod, arquivo_chave):
    respostas = [RespostaFalsa(200, [{"codigoEmenda": "1"}, {"codigoEmenda": "2"}]),
                 RespostaFalsa(200, [{"codigoEmenda": "3"}]),
                 RespostaFalsa(200, [])]
    c, sessao, _ = _cliente(mod, arquivo_chave, respostas)
    regs = list(c.paginar("/emendas", {"ano": 2024}))
    assert [r["codigoEmenda"] for r in regs] == ["1", "2", "3"]
    assert [ch["params"] for ch in sessao.chamadas] == [
        {"ano": 2024, "pagina": 1}, {"ano": 2024, "pagina": 2}, {"ano": 2024, "pagina": 3}]
    assert c.paginas_lidas == 3


@pytest.mark.parametrize("hora,intervalo", [(10, 0.7), (23, 0.7), (0, 0.25), (5, 0.25), (6, 0.7)])
def test_ritmo_por_faixa_de_horario(mod, arquivo_chave, hora, intervalo):
    relogio = Relogio(hora)
    c, _, _ = _cliente(mod, arquivo_chave, [RespostaFalsa(200, [{"a": 1}]), RespostaFalsa(200, [])], relogio)
    list(c.paginar("/emendas", {"ano": 2024}))
    assert relogio.esperas == [pytest.approx(intervalo)]


def test_429_respeita_retry_after(mod, arquivo_chave):
    c, _, relogio = _cliente(mod, arquivo_chave, [RespostaFalsa(429, headers={"Retry-After": "9"}), RespostaFalsa(200, [])])
    list(c.paginar("/emendas", {"ano": 2024}))
    assert 9 in relogio.esperas
    assert c.retries == 1


def test_5xx_e_conexao_com_espera_exponencial(mod, arquivo_chave):
    respostas = [RespostaFalsa(502), requests.Timeout("lento")] + [RespostaFalsa(500)] * 4
    c, _, relogio = _cliente(mod, arquivo_chave, respostas)
    with pytest.raises(mod.ErroFonte) as e:
        list(c.paginar("/emendas", {"ano": 2024}))
    assert [s for s in relogio.esperas if s >= 15] == [15, 30, 60, 120, 240]
    assert c.requests_made == 6
    assert CHAVE not in str(e.value)


def test_outro_4xx_falha_com_corpo_truncado_e_sanitizado(mod, arquivo_chave):
    corpo = CHAVE + ("y" * 1000)
    c, _, _ = _cliente(mod, arquivo_chave, [RespostaFalsa(400, texto=corpo)])
    with pytest.raises(mod.ErroFonte) as e:
        list(c.paginar("/emendas", {"ano": 2024}))
    msg = str(e.value)
    assert "HTTP 400" in msg and CHAVE not in msg and "y" * 301 not in msg


@pytest.mark.parametrize(
    "resposta",
    [
        RespostaFalsa(404, texto="não encontrado"),
        RespostaFalsa(200, texto=""),
        RespostaFalsa(200, {}),
        RespostaFalsa(200, {"razaoSocial": "X"}),
        RespostaFalsa(200, {"cnpj": None, "razaoSocial": None, "nomeFantasia": None}),
    ],
)
def test_pessoa_juridica_nao_encontrada(mod, arquivo_chave, resposta):
    c, sessao, _ = _cliente(mod, arquivo_chave, [resposta])
    assert c.pessoa_juridica("00000000000191") == ("nao_encontrado", None)
    assert sessao.chamadas[0]["params"] == {"cnpj": "00000000000191"}


def test_pessoa_juridica_encontrada(mod, arquivo_chave):
    obj = {"cnpj": "00.000.000/0001-91", "razaoSocial": "BANCO DO BRASIL SA"}
    c, sessao, _ = _cliente(mod, arquivo_chave, [RespostaFalsa(200, obj)])
    assert c.pessoa_juridica("00000000000191") == ("encontrado", obj)
    assert sessao.chamadas[0]["url"].endswith("/pessoa-juridica")
