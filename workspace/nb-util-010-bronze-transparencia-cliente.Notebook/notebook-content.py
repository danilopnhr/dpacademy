# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # nb-util-010-bronze-transparencia-cliente
# Cliente HTTP da API do Portal da Transparência, em Python puro (sem Spark e sem `notebookutils`), testado localmente com `pytest`.
# - Contrato: `specs/003-gastos-bronze-ingestion/contracts/transparencia-api.md`
# - Chave: arquivo `Files/_secrets/transparencia_api_key` do lakehouse (ADR-003); o valor nunca é impresso
# - Uso: `%run nb-util-010-bronze-transparencia-cliente` nos notebooks de carga do Portal

# CELL ********************

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BASE_TRANSPARENCIA = "https://api.portaldatransparencia.gov.br/api-de-dados"
CAMINHO_CHAVE_PADRAO = "/lakehouse/default/Files/_secrets/transparencia_api_key"
ESPERAS_RETENTATIVA = (15, 30, 60, 120, 240)
INTERVALO_DIA_S = 0.7        # ~85/min; limite de ~90/min das 06:00 às 23:59
INTERVALO_MADRUGADA_S = 0.25  # ~240/min; limite maior das 00:00 às 05:59
MSG_CHAVE = "chave da API ausente ou inválida"


def fuso_sao_paulo():
    try:
        return ZoneInfo("America/Sao_Paulo")
    except Exception:
        return timezone(timedelta(hours=-3))


class ErroFonte(Exception):
    """Falha definitiva ao falar com a fonte (sem novas tentativas)."""


class ErroChave(ErroFonte):
    """Chave ausente, vazia ou recusada pela fonte."""


class ClienteTransparencia:
    """Chamadas à API do Portal com chave no header, ritmo por faixa de horário, retentativas e
    paginação por `pagina` até a lista vazia."""

    def __init__(self, caminho_chave=CAMINHO_CHAVE_PADRAO, sessao=None, dormir=time.sleep,
                 relogio=time.monotonic, agora=None, timeout=60):
        try:
            chave = Path(caminho_chave).read_text(encoding="utf-8").lstrip("﻿").strip()
        except OSError:
            chave = ""
        if not chave:
            raise ErroChave(MSG_CHAVE)
        self.__chave = chave
        self.sessao = sessao or requests.Session()
        self.dormir = dormir
        self.relogio = relogio
        self.agora = agora or (lambda: datetime.now(fuso_sao_paulo()))
        self.timeout = timeout
        self.requests_made = 0
        self.retries = 0
        self.paginas_lidas = 0
        self._ultima_chamada = None

    def __repr__(self):
        return f"ClienteTransparencia(requests_made={self.requests_made}, retries={self.retries})"

    def segredos(self):
        """Valores que nunca podem aparecer em mensagens (uso: sanitizar na gravação)."""
        return (self.__chave,)

    def _sanitizar(self, texto):
        return str(texto).replace(self.__chave, "***")

    def intervalo_atual(self):
        return INTERVALO_MADRUGADA_S if self.agora().hour < 6 else INTERVALO_DIA_S

    def _aguardar_ritmo(self):
        if self._ultima_chamada is not None:
            falta = self.intervalo_atual() - (self.relogio() - self._ultima_chamada)
            if falta > 0:
                self.dormir(falta)
        self._ultima_chamada = self.relogio()

    @staticmethod
    def _espera_retry_after(resposta, padrao):
        valor = resposta.headers.get("Retry-After") if resposta is not None else None
        try:
            return max(0, int(valor))
        except (TypeError, ValueError):
            return padrao

    def _requisitar(self, caminho, params, aceitar_404=False):
        url = BASE_TRANSPARENCIA + caminho
        cabecalhos = {"Accept": "application/json", "User-Agent": "dpacademy-ingestao/1.0",
                      "chave-api-dados": self.__chave}
        tentativas = len(ESPERAS_RETENTATIVA) + 1
        motivo = ""
        for tentativa in range(tentativas):
            self._aguardar_ritmo()
            self.requests_made += 1
            resposta = None
            try:
                resposta = self.sessao.get(url, params=params, headers=cabecalhos, timeout=self.timeout)
            except requests.RequestException as erro:
                motivo = f"erro de conexão: {type(erro).__name__}"
            else:
                codigo = resposta.status_code
                if codigo in (401, 403):
                    raise ErroChave(MSG_CHAVE)
                if codigo == 404 and aceitar_404:
                    return None
                if codigo == 429 or codigo >= 500:
                    motivo = f"HTTP {codigo}"
                elif codigo >= 400:
                    raise ErroFonte(self._sanitizar(f"HTTP {codigo} em {url}: {resposta.text[:300]}"))
                else:
                    return resposta
            if tentativa == tentativas - 1:
                break
            self.retries += 1
            self.dormir(self._espera_retry_after(resposta, ESPERAS_RETENTATIVA[tentativa]))
        raise ErroFonte(self._sanitizar(f"{motivo} em {url} após {tentativas} tentativas"))

    def paginar(self, caminho, params=None):
        """Gera os registros de `pagina` 1 em diante até a fonte devolver lista vazia."""
        pagina = 1
        self.paginas_lidas = 0
        while True:
            parametros = dict(params or {})
            parametros["pagina"] = pagina
            resposta = self._requisitar(caminho, parametros)
            self.paginas_lidas += 1
            dados = resposta.json()
            if not dados:
                return
            yield from dados
            pagina += 1

    def pessoa_juridica(self, cnpj):
        """('encontrado', objeto) ou ('nao_encontrado', None) para 404, corpo vazio, objeto sem
        `cnpj` ou com todos os campos nulos."""
        resposta = self._requisitar("/pessoa-juridica", {"cnpj": cnpj}, aceitar_404=True)
        if resposta is None:
            return ("nao_encontrado", None)
        try:
            obj = resposta.json()
        except ValueError:
            return ("nao_encontrado", None)
        if not isinstance(obj, dict) or not obj.get("cnpj") or all(v in (None, "") for v in obj.values()):
            return ("nao_encontrado", None)
        return ("encontrado", obj)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
