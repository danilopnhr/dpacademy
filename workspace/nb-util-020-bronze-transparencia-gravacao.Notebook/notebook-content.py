# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # nb-util-020-bronze-transparencia-gravacao
# Gravação na `bronze_transparencia`: append atômico por lote, registro em `ctl_ingestion_runs` e trava de concorrência.
# - Contrato: `specs/003-gastos-bronze-ingestion/contracts/bronze-tables.md`
# - Decisões: research R4, R8 e R9 da feature 003
# - Uso: `%run nb-util-020-bronze-transparencia-gravacao` depois do cliente, com `bronze_transparencia` como lakehouse padrão

# CELL ********************

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql import types as T

FONTE = "transparencia"
TABELAS_DADOS = ["emendas", "pessoa_juridica"]
# pessoa_juridica guarda o CNPJ consultado e o resultado, porque o "não encontrado" não tem payload
COLUNAS_EXTRAS = {"pessoa_juridica": "_cnpj STRING, _resultado STRING"}
LIMITE_LOTE_ANTIGO_H = 6
TAMANHO_MAX_MENSAGEM = 1000

ESQUEMA_LINHA = T.StructType([
    T.StructField("payload", T.StringType()),
    T.StructField("_source_endpoint", T.StringType()),
    T.StructField("_recorte", T.StringType()),
])

ESQUEMA_CTL = T.StructType([
    T.StructField("run_id", T.StringType()),
    T.StructField("batch_id", T.StringType()),
    T.StructField("fonte", T.StringType()),
    T.StructField("recurso", T.StringType()),
    T.StructField("origem", T.StringType()),
    T.StructField("recorte", T.StringType()),
    T.StructField("status", T.StringType()),
    T.StructField("started_at", T.TimestampType()),
    T.StructField("ended_at", T.TimestampType()),
    T.StructField("records_collected", T.LongType()),
    T.StructField("records_written", T.LongType()),
    T.StructField("requests_made", T.IntegerType()),
    T.StructField("retries", T.IntegerType()),
    T.StructField("expected_total", T.LongType()),
    T.StructField("message", T.StringType()),
    T.StructField("environment", T.StringType()),
])


def ambiente():
    """dev ou prd, a partir do nome do workspace ws-<ambiente>-dpacademy (research R9 da 002)."""
    try:
        nome = notebookutils.runtime.context.get("currentWorkspaceName", "")
    except NameError:  # fora de um notebook (ex.: sessão Livy de diagnóstico)
        nome = ""
    m = re.match(r"^ws-([a-z0-9]+)-dpacademy$", nome or "")
    return m.group(1) if m else "desconhecido"


def sanitizar(mensagem, segredos=()):
    texto = str(mensagem or "")
    for s in segredos:
        if s:
            texto = texto.replace(s, "***")
    return texto[:TAMANHO_MAX_MENSAGEM]


def garantir_tabelas(tabelas=TABELAS_DADOS, extras=COLUNAS_EXTRAS):
    """Cria as tabelas da Bronze e a de controle, se não existirem. `extras` = colunas a mais por tabela."""
    extras = extras or {}
    for t in tabelas:
        colunas = (
            "payload STRING, _ingested_at TIMESTAMP, _source_endpoint STRING, _batch_id STRING, "
            "_origem STRING, _recorte STRING"
        )
        if t in extras:
            colunas += ", " + extras[t]
        spark.sql(f"CREATE TABLE IF NOT EXISTS {t} ({colunas}) USING DELTA")
    ddl_ctl = ", ".join(f"{c.name} {c.dataType.simpleString().upper()}" for c in ESQUEMA_CTL.fields)
    spark.sql(f"CREATE TABLE IF NOT EXISTS ctl_ingestion_runs ({ddl_ctl}) USING DELTA")


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _inserir_ctl(linha):
    spark.createDataFrame([linha], ESQUEMA_CTL).write.mode("append").saveAsTable("ctl_ingestion_runs")


def _ctl():
    return DeltaTable.forName(spark, "ctl_ingestion_runs")


def iniciar_lote(run_id, recurso, origem, recorte):
    """Abre um lote. Devolve (batch_id, status), com status 'running' ou 'skipped' (research R9).

    Usa a API do Delta e do DataFrame: neste runtime, parâmetros nomeados em spark.sql não chegam ao SQL.
    """
    agora = _agora()
    limite = agora - timedelta(hours=LIMITE_LOTE_ANTIGO_H)
    do_recurso_rodando = (F.col("recurso") == recurso) & (F.col("status") == "running")
    _ctl().update(
        condition=do_recurso_rodando & (F.col("started_at") < F.lit(limite)),
        set={"status": F.lit("failed"), "ended_at": F.lit(agora), "message": F.lit("stale")},
    )
    em_andamento = (
        spark.table("ctl_ingestion_runs").filter(do_recurso_rodando & (F.col("started_at") >= F.lit(limite))).count()
    )
    batch_id = str(uuid.uuid4())
    recorte_json = json.dumps(recorte, ensure_ascii=False, sort_keys=True)
    status = "skipped" if em_andamento else "running"
    _inserir_ctl((
        run_id, batch_id, FONTE, recurso, origem, recorte_json, status, agora,
        agora if status == "skipped" else None, 0, 0, 0, 0, None,
        "outro lote do mesmo recurso em andamento" if status == "skipped" else None, ambiente(),
    ))
    return batch_id, status


def finalizar_lote(batch_id, status, coletados=0, gravados=0, requisicoes=0, retentativas=0,
                   total_esperado=None, mensagem=None):
    _ctl().update(
        condition=F.col("batch_id") == batch_id,
        set={
            "status": F.lit(status),
            "ended_at": F.lit(_agora()),
            "records_collected": F.lit(int(coletados)).cast("bigint"),
            "records_written": F.lit(int(gravados)).cast("bigint"),
            "requests_made": F.lit(int(requisicoes)).cast("int"),
            "retries": F.lit(int(retentativas)).cast("int"),
            "expected_total": F.lit(None if total_esperado is None else int(total_esperado)).cast("bigint"),
            "message": F.lit(mensagem).cast("string"),
        },
    )


def linha(payload, endpoint, recorte, *extras):
    """Uma linha da Bronze: payload (dict, texto JSON ou None), endpoint, recorte (dict) e, se a
    tabela tiver, os valores das colunas extras (ex.: _cnpj, _resultado)."""
    if payload is None or isinstance(payload, str):
        texto = payload
    else:
        texto = json.dumps(payload, ensure_ascii=False)
    return (texto, endpoint, json.dumps(recorte, ensure_ascii=False, sort_keys=True), *extras)


def gravar_lote(tabela, dados, batch_id, origem, colunas_extras=None):
    """Grava o lote inteiro com um único append. `dados` = lista de linha(...) ou DataFrame com
    payload, _source_endpoint e _recorte. Devolve a quantidade gravada."""
    if hasattr(dados, "columns"):
        df = dados
    else:
        esquema = T.StructType(ESQUEMA_LINHA.fields + [T.StructField(c, T.StringType()) for c in (colunas_extras or [])])
        df = spark.createDataFrame(dados, esquema)
    df = (
        df.withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_batch_id", F.lit(batch_id))
        .withColumn("_origem", F.lit(origem))
    )
    colunas = ["payload", "_ingested_at", "_source_endpoint", "_batch_id", "_origem", "_recorte"]
    colunas += list(colunas_extras or [])
    df = df.select(*colunas).cache()
    n = df.count()
    if n:
        df.write.mode("append").saveAsTable(tabela)
    df.unpersist()
    return n


def executar_lote(run_id, recurso, origem, recorte, tabela, coletar, cliente, segredos=(), colunas_extras=None):
    """Roda um lote completo. `coletar()` devolve um dict com:
    dados (lista de linha(...) ou DataFrame), total_esperado (opcional) e aviso (opcional)."""
    batch_id, status = iniciar_lote(run_id, recurso, origem, recorte)
    resultado = {"batch_id": batch_id, "recurso": recurso, "recorte": recorte, "status": status, "registros": 0}
    if status == "skipped":
        return resultado
    req0, ret0 = cliente.requests_made, cliente.retries
    try:
        saida = coletar()
        dados = saida["dados"]
        gravados = gravar_lote(tabela, dados, batch_id, origem, colunas_extras)
        coletados = saida.get("coletados", gravados)
        if coletados != gravados:
            raise RuntimeError(f"coletados ({coletados}) diferente de gravados ({gravados})")
        finalizar_lote(batch_id, "succeeded", coletados, gravados, cliente.requests_made - req0,
                       cliente.retries - ret0, saida.get("total_esperado"), sanitizar(saida.get("aviso"), segredos) or None)
        resultado.update(status="succeeded", registros=gravados)
    except Exception as erro:
        finalizar_lote(batch_id, "failed", 0, 0, cliente.requests_made - req0, cliente.retries - ret0,
                       None, sanitizar(f"{type(erro).__name__}: {erro}", segredos))
        resultado.update(status="failed", erro=sanitizar(str(erro), segredos))
    return resultado


def lote_falho(run_id, recurso, origem, recorte, mensagem):
    """Registra um lote que falhou antes de qualquer coleta (ex.: chave ausente), para que toda
    execução apareça em ctl_ingestion_runs (SC-007)."""
    batch_id, status = iniciar_lote(run_id, recurso, origem, recorte)
    if status == "skipped":
        return {"batch_id": batch_id, "recurso": recurso, "recorte": recorte, "status": "skipped", "registros": 0}
    finalizar_lote(batch_id, "failed", mensagem=sanitizar(mensagem))
    return {"batch_id": batch_id, "recurso": recurso, "recorte": recorte, "status": "failed", "registros": 0,
            "erro": sanitizar(mensagem)}


def exigir_chave(registros, chave, recurso):
    """Falha o lote se algum registro da API não trouxer a chave natural (data-model.md)."""
    faltando = sum(1 for r in registros if r.get(chave) in (None, ""))
    if faltando:
        raise ValueError(f"{faltando} registro(s) de {recurso} sem a chave natural '{chave}'")


def mostrar_execucao(run_id):
    display(
        spark.table("ctl_ingestion_runs").filter(F.col("run_id") == run_id)
        .select("recurso", "origem", "recorte", "status", "records_collected", "records_written", "expected_total",
                "requests_made", "retries", "message", "started_at", "ended_at")
        .orderBy("started_at")
    )


def encerrar(run_id, resultados):
    """Mostra o resumo, devolve o JSON do contrato e falha a execução se algum lote falhou."""
    mostrar_execucao(run_id)
    contagem = {s: sum(1 for r in resultados if r["status"] == s) for s in ("succeeded", "failed", "skipped")}
    saida = {"run_id": run_id, "lotes": len(resultados), **contagem,
             "registros": sum(r["registros"] for r in resultados)}
    if contagem["failed"]:
        falhas = "; ".join(f"{r['recurso']} {r['recorte']}: {r.get('erro', '')}" for r in resultados if r["status"] == "failed")
        raise RuntimeError(f"{contagem['failed']} lote(s) falharam: {falhas[:2000]}")
    notebookutils.notebook.exit(json.dumps(saida))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
