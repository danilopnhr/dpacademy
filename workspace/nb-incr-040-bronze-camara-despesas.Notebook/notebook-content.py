# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "dd959c99-5fae-41c3-a6fe-56b114d845b5",
# META       "default_lakehouse_name": "bronze_camara",
# META       "default_lakehouse_workspace_id": "559ab4d8-8abd-4b75-9bdc-fd68895d93bf",
# META       "known_lakehouses": [
# META         {
# META           "id": "dd959c99-5fae-41c3-a6fe-56b114d845b5"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb-incr-040-bronze-camara-despesas
# Despesas da cota parlamentar para a `bronze_camara.despesas`, em dois modos que gravam na mesma tabela:
# - `origem=arquivo`: um lote por ano, a partir do arquivo anual publicado pela Câmara (histórico).
# - `origem=api`: um lote por mês, consultando cada deputado (carga recorrente).
# - Parâmetros: `specs/003-gastos-bronze-ingestion/contracts/notebook-parameters.md`

# PARAMETERS CELL ********************

origem = "api"
anos = ""
meses = ""
legislatura = "57"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb-util-010-bronze-camara-cliente

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb-util-020-bronze-camara-gravacao

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import zipfile

LANDING_LOCAL = "/lakehouse/default/Files/_landing/cotas"
LANDING_SPARK = "Files/_landing/cotas"

modo = (origem or "api").strip().lower()
if modo not in ("api", "arquivo"):
    raise ValueError(f"origem inválida: {origem!r}; use 'api' ou 'arquivo'")

run_id = str(uuid.uuid4())
cliente = ClienteCamara()
garantir_tabelas()


def coletar_arquivo(ano):
    zip_path = cliente.baixar_cotas(ano, LANDING_LOCAL)
    if zip_path is None:
        return {"dados": spark.createDataFrame([], ESQUEMA_LINHA), "total_esperado": 0,
                "aviso": f"a fonte não tem arquivo para {ano}"}
    with zipfile.ZipFile(zip_path) as z:
        nome_csv = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        z.extract(nome_csv, LANDING_LOCAL)
    df = (
        spark.read.option("header", True).option("sep", ";").option("encoding", "UTF-8")
        .option("multiLine", True).option("quote", '"').option("escape", '"')
        .option("nullValue", "\u0000").option("inferSchema", False)
        .csv(f"{LANDING_SPARK}/{nome_csv}")
    )
    df = df.toDF(*[normalizar_cabecalho(c) for c in df.columns])
    df = df.cache()
    total = df.count()
    sem_documento = df.filter(F.col("ideDocumento").isNull() | (F.col("ideDocumento") == "")).count()
    payload = F.to_json(F.struct(*[F.col(f"`{c}`") for c in df.columns]), {"ignoreNullFields": "false"})
    dados = (
        df.select(payload.alias("payload"))
        .withColumn("_source_endpoint", F.lit(URL_COTAS.format(ano=ano)))
        .withColumn("_recorte", F.lit(json.dumps({"ano": ano}, sort_keys=True)))
    )
    aviso = f"{sem_documento} linha(s) sem ideDocumento (despesas de liderança)" if sem_documento else None
    return {"dados": dados, "total_esperado": total, "coletados": total, "aviso": aviso}


resultados = []
if modo == "arquivo":
    lista_anos = [int(a) for a in (anos or "").split(",") if a.strip()]
    if not lista_anos:
        raise ValueError("o parâmetro anos é obrigatório com origem=arquivo (ex.: 2019,2020)")
    for ano in lista_anos:
        resultados.append(executar_lote(run_id, "despesas", "arquivo", {"ano": ano}, "despesas",
                                        lambda ano=ano: coletar_arquivo(ano), cliente))
else:
    raise NotImplementedError("origem=api entra na T019 da feature 003")

encerrar(run_id, resultados)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
