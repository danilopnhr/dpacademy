# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # nb-util-010-silver-camara-comum
# Biblioteca da `silver_camara`: lotes válidos da Bronze, conversões, verificações de qualidade (Princípio V) e `MERGE` por partição.
# - Contratos: `specs/004-gastos-silver/contracts/silver-tables.md` e `contracts/notebooks-e-orquestracao.md`
# - Decisões: research R4, R5 e R6 da feature 004
# - Uso: `%run nb-util-010-silver-camara-comum`, com `silver_camara` como lakehouse padrão

# CELL ********************

import json
import re
import uuid
from datetime import datetime, timezone
from functools import reduce

from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql import types as T

FONTE = "camara"
BRONZE = "bronze_camara"
MAX_EXEMPLOS = 5

ESQUEMA_QUALIDADE = T.StructType([
    T.StructField("run_id", T.StringType()),
    T.StructField("checked_at", T.TimestampType()),
    T.StructField("tabela", T.StringType()),
    T.StructField("verificacao", T.StringType()),
    T.StructField("status", T.StringType()),
    T.StructField("linhas_com_problema", T.LongType()),
    T.StructField("linhas_tabela", T.LongType()),
    T.StructField("detalhe", T.StringType()),
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


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def novo_run_id():
    return str(uuid.uuid4())


# --- Lotes da Bronze (só succeeded, FR-012) ---

def lotes_validos(recurso, origem=None):
    c = spark.table(f"{BRONZE}.ctl_ingestion_runs").filter(
        (F.col("recurso") == recurso) & (F.col("status") == "succeeded"))
    if origem:
        c = c.filter(F.col("origem") == origem)
    return c


def ultimo_lote(recurso, origem=None):
    """batch_id do último lote succeeded do recurso, ou None."""
    r = lotes_validos(recurso, origem).orderBy(F.col("started_at").desc()).select("batch_id").first()
    return r[0] if r else None


def ultimos_lotes_por_ano(recurso, origem=None):
    """{ano: batch_id} do último lote succeeded de cada ano (recorte com a chave 'ano')."""
    linhas = (
        lotes_validos(recurso, origem)
        .withColumn("ano", F.get_json_object("recorte", "$.ano").cast("int"))
        .filter(F.col("ano").isNotNull())
        .groupBy("ano").agg(F.max_by("batch_id", "started_at").alias("batch_id"))
        .collect()
    )
    return {r["ano"]: r["batch_id"] for r in linhas}


def lote_atual_na_silver(tabela, por_ano=False):
    """batch_id já carregado na Silver: {ano: batch_id} se por_ano, senão um único batch_id."""
    if not spark.catalog.tableExists(tabela):
        return {} if por_ano else None
    df = spark.table(tabela)
    if por_ano:
        return {r["ano"]: r["b"] for r in df.groupBy("ano").agg(F.max("_batch_id").alias("b")).collect()}
    r = df.select(F.max("_batch_id")).first()
    return r[0] if r else None


def anos_a_processar(recurso, tabela, anos_param="", origem=None):
    """[(ano, batch_id)] dos anos com lote novo na Bronze; com anos_param, só esses, sempre (R6)."""
    bronze = ultimos_lotes_por_ano(recurso, origem)
    pedidos = [int(a) for a in (anos_param or "").split(",") if a.strip()]
    if pedidos:
        faltando = [a for a in pedidos if a not in bronze]
        if faltando:
            raise ValueError(f"sem lote succeeded na Bronze para os anos {faltando}")
        return [(a, bronze[a]) for a in sorted(pedidos)]
    silver = lote_atual_na_silver(tabela, por_ano=True)
    return [(a, b) for a, b in sorted(bronze.items()) if silver.get(a) != b]


def ler_lote(tabela_bronze, batch_ids):
    ids = batch_ids if isinstance(batch_ids, (list, tuple, set)) else [batch_ids]
    return spark.table(f"{BRONZE}.{tabela_bronze}").filter(F.col("_batch_id").isin(list(ids)))


# --- Conversões (research R5) ---

def campo(nome, coluna="payload"):
    """Campo do JSON da Bronze como texto, com texto vazio virando nulo. Aceita caminho com ponto."""
    return vazio_nulo(F.get_json_object(coluna, f"$.{nome}"))


def vazio_nulo(c):
    return F.when(F.trim(c) == "", F.lit(None)).otherwise(c)


def inteiro(c, tipo="int"):
    return F.when(F.trim(c).rlike(r"^-?\d+$"), F.trim(c).cast(tipo))


def valor_ponto(c):
    """'1467', '-108.18' -> DECIMAL(15,2); o que não converte vira nulo (pego por obrigatórias)."""
    return F.when(F.trim(c).rlike(r"^-?\d+(\.\d+)?$"), F.trim(c).cast("decimal(15,2)"))


def valor_br(c):
    """'1.200.000,00' -> DECIMAL(15,2)."""
    return valor_ponto(F.regexp_replace(F.regexp_replace(F.trim(c), r"\.", ""), ",", "."))


def data(c):
    """'AAAA-MM-DD' ou 'AAAA-MM-DDTHH:MM:SS' -> DATE; outro formato vira nulo."""
    return F.when(F.trim(c).rlike(r"^\d{4}-\d{2}-\d{2}"), F.to_date(F.substring(F.trim(c), 1, 10)))


def booleano(c):
    return F.when(F.lower(F.trim(c)) == "true", F.lit(True)).when(F.lower(F.trim(c)) == "false", F.lit(False))


def so_digitos(c):
    return vazio_nulo(F.regexp_replace(c, r"[^0-9]", ""))


def chave_hash(coluna="payload"):
    """SHA-256 hex da linha publicada pela fonte (research R4)."""
    return F.sha2(F.col(coluna), 256)


def linhagem():
    return [F.col("_batch_id"), F.col("_ingested_at")]


# --- Qualidade (Princípio V, FR-013) ---

def garantir_ctl():
    ddl = ", ".join(f"{c.name} {c.dataType.simpleString().upper()}" for c in ESQUEMA_QUALIDADE.fields)
    spark.sql(f"CREATE TABLE IF NOT EXISTS ctl_quality_checks ({ddl}) USING DELTA")


def _registrar(run_id, tabela, verificacao, status, problemas, linhas, detalhe):
    spark.createDataFrame(
        [(run_id, _agora(), tabela, verificacao, status, int(problemas), int(linhas), (detalhe or "")[:1000], ambiente())],
        ESQUEMA_QUALIDADE,
    ).write.mode("append").saveAsTable("ctl_quality_checks")


def verificar(df, tabela, chave, obrigatorias, run_id, detalhe=""):
    """Unicidade da chave e obrigatórias no conjunto preparado, antes do MERGE (R6).

    `obrigatorias`: nomes de coluna (violação = nulo) ou pares (rótulo, coluna booleana de violação).
    Grava as duas verificações e devolve True se ambas passaram.
    """
    linhas = df.count()
    repetidas = df.groupBy(chave).count().filter(F.col("count") > 1)
    n_rep = repetidas.agg(F.sum("count")).first()[0] or 0
    det_u = detalhe
    if n_rep:
        exemplos = [str(r[0]) for r in repetidas.select(chave).limit(MAX_EXEMPLOS).collect()]
        det_u = f"{detalhe}; chaves repetidas (exemplos): {', '.join(exemplos)}"
    _registrar(run_id, tabela, "unicidade", "failed" if n_rep else "passed", n_rep, linhas, det_u)

    condicoes, rotulos = [], []
    for o in obrigatorias:
        if isinstance(o, tuple):
            rotulos.append(o[0]); condicoes.append(o[1])
        else:
            rotulos.append(o); condicoes.append(F.col(o).isNull())
    viola = reduce(lambda a, b: a | b, condicoes)
    n_nulos = df.filter(viola).count()
    det_o = detalhe
    if n_nulos:
        por_coluna = df.select([F.sum(F.when(c, 1).otherwise(0)).alias(r) for r, c in zip(rotulos, condicoes)]).first()
        det_o = f"{detalhe}; " + ", ".join(f"{r}={por_coluna[r]}" for r in rotulos if por_coluna[r])
    _registrar(run_id, tabela, "obrigatorias", "failed" if n_nulos else "passed", n_nulos, linhas, det_o)
    return n_rep == 0 and n_nulos == 0


def registrar_contagem(tabela, run_id, detalhe=""):
    n = spark.table(tabela).count()
    _registrar(run_id, tabela, "contagem", "passed", 0, n, detalhe)
    return n


# --- Gravação (R6) ---

def mesclar_particao(df, tabela, chave, condicao_particao=None, remover=True):
    """MERGE por chave: insere as novas, atualiza as que vieram de outro lote e, com `remover`,
    apaga as que sumiram dentro da partição (`condicao_particao` sobre a tabela alvo, ex.
    't.ano = 2026'; None = tabela toda). Cria a tabela na primeira execução."""
    if not spark.catalog.tableExists(tabela):
        df.write.format("delta").saveAsTable(tabela)
        return
    alvo = DeltaTable.forName(spark, tabela)
    colunas = [c for c in df.columns if c != chave]
    m = (
        alvo.alias("t").merge(df.alias("s"), f"t.{chave} = s.{chave}")
        .whenMatchedUpdate(condition="t._batch_id <> s._batch_id", set={c: f"s.{c}" for c in colunas})
        .whenNotMatchedInsertAll()
    )
    if remover:
        m = m.whenNotMatchedBySourceDelete(condition=condicao_particao) if condicao_particao \
            else m.whenNotMatchedBySourceDelete()
    m.execute()


# --- Encerramento ---

def encerrar(run_id, resultados):
    """Mostra as verificações da execução, devolve o JSON do contrato e falha se alguma verificação falhou."""
    display(
        spark.table("ctl_quality_checks").filter(F.col("run_id") == run_id)
        .select("tabela", "verificacao", "status", "linhas_com_problema", "linhas_tabela", "detalhe", "checked_at")
        .orderBy("checked_at")
    )
    falhas = [t for t, r in resultados.items() if r.get("status") == "failed"]
    if falhas:
        raise RuntimeError(f"verificação de qualidade falhou em: {', '.join(falhas)}; veja ctl_quality_checks (run_id {run_id})")
    notebookutils.notebook.exit(json.dumps({"run_id": run_id, "tabelas": resultados}, default=str))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
