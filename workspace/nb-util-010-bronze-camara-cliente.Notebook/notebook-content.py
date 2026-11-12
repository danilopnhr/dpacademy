# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # nb-util-010-bronze-camara-cliente
# # Cliente HTTP da API de Dados Abertos da Câmara dos Deputados, em Python puro (sem Spark e sem
# `notebookutils`), para ser testado localmente com `pytest`.
# # - Contrato: `specs/003-gastos-bronze-ingestion/contracts/camara-api.md`
# - Decisões: research R1, R7 e R8 da feature 003
# - Uso: `%run nb-util-010-bronze-camara-cliente` nos notebooks de carga da Câmara

# CELL ********************

import time
from datetime import date
from pathlib import Path

import requests

BASE_CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
URL_COTAS = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
ESPERAS_RETENTATIVA = (15, 30, 60, 120, 240)
INTERVALO_MINIMO_S = 0.25
ITENS_POR_PAGINA = 100
CABECALHOS = {"Accept": "application/json", "User-Agent": "dpacademy-ingestao/1.0"}


class ErroFonte(Exception):
    """Falha definitiva ao falar com a fonte (sem novas tentativas)."""


class ClienteCamara:
    """Chamadas à API da Câmara com ritmo mínimo, retentativas e paginação por link `next`."""

    def __init__(self, sessao=None, intervalo=INTERVALO_MINIMO_S, dormir=time.sleep,
                 relogio=time.monotonic, timeout=60):
        self.sessao = sessao or requests.Session()
        self.intervalo = intervalo
        self.dormir = dormir
        self.relogio = relogio
        self.timeout = timeout
        self.requests_made = 0
        self.retries = 0
        self.ultimo_total = None
        self._ultima_chamada = None

    def _aguardar_ritmo(self):
        if self._ultima_chamada is not None:
            falta = self.intervalo - (self.relogio() - self._ultima_chamada)
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

    def _requisitar(self, url, params=None, aceitar_404=False):
        tentativas = len(ESPERAS_RETENTATIVA) + 1
        motivo = ""
        for tentativa in range(tentativas):
            self._aguardar_ritmo()
            self.requests_made += 1
            resposta = None
            try:
                resposta = self.sessao.get(url, params=params, headers=CABECALHOS, timeout=self.timeout)
            except requests.RequestException as erro:
                motivo = f"erro de conexão: {type(erro).__name__}"
            else:
                codigo = resposta.status_code
                if codigo == 404 and aceitar_404:
                    return None
                if codigo == 429 or codigo >= 500:
                    motivo = f"HTTP {codigo}"
                elif codigo >= 400:
                    raise ErroFonte(f"HTTP {codigo} em {url}: {resposta.text[:300]}")
                else:
                    return resposta
            if tentativa == tentativas - 1:
                break
            self.retries += 1
            self.dormir(self._espera_retry_after(resposta, ESPERAS_RETENTATIVA[tentativa]))
        raise ErroFonte(f"{motivo} em {url} após {tentativas} tentativas")

    def paginar(self, caminho, params=None):
        """Gera os registros de todas as páginas; `ultimo_total` recebe o X-Total-Count."""
        url = BASE_CAMARA + caminho
        parametros = dict(params or {})
        parametros["itens"] = ITENS_POR_PAGINA
        parametros["pagina"] = 1
        self.ultimo_total = None
        primeira = True
        while url:
            resposta = self._requisitar(url, parametros)
            corpo = resposta.json()
            if primeira:
                total = resposta.headers.get("X-Total-Count")
                self.ultimo_total = int(total) if total is not None else None
                primeira = False
            yield from corpo.get("dados", [])
            url = next((l["href"] for l in corpo.get("links", []) if l.get("rel") == "next"), None)
            parametros = None  # o link next já traz os parâmetros

    def detalhe(self, caminho):
        return self._requisitar(BASE_CAMARA + caminho).json()["dados"]

    def baixar_cotas(self, ano, destino):
        """Baixa o arquivo anual da cota parlamentar. Devolve o caminho, ou None se não existir."""
        resposta = self._requisitar(URL_COTAS.format(ano=ano), aceitar_404=True)
        if resposta is None:
            return None
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        caminho = destino / f"Ano-{ano}.csv.zip"
        caminho.write_bytes(resposta.content)
        return caminho


def normalizar_cabecalho(nome):
    """Nome de coluna do CSV da cota sem BOM, aspas e espaços."""
    return nome.lstrip("﻿").strip().strip('"').strip()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
