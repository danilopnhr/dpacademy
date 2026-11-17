# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "ec55a601-16e2-4af1-a923-5d0430d1c576",
# META       "default_lakehouse_name": "silver_transparencia",
# META       "default_lakehouse_workspace_id": "559ab4d8-8abd-4b75-9bdc-fd68895d93bf",
# META       "known_lakehouses": [
# META         {
# META           "id": "ec55a601-16e2-4af1-a923-5d0430d1c576"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb-incr-030-silver-transparencia-fornecedores
# Cadastro de pessoa jurídica dos fornecedores para a `silver_transparencia.pessoa_juridica`, pelo resultado mais recente de cada CNPJ.
# - Incremental: só as linhas da Bronze coletadas depois da mais recente já presente na Silver; `MERGE` por `cnpj`, sem remoção (research R6 da feature 004).
# - Os não encontrados ficam na tabela com `encontrado = false`.
# - `completo=true` reprocessa todos os CNPJs da Bronze.
# - Contrato: `specs/004-gastos-silver/contracts/silver-tables.md`

# PARAMETERS CELL ********************

completo = "false"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb-util-010-silver-transparencia-comum

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql import Window

TABELA = "pessoa_juridica"
CHAVE = "cnpj"
reprocessar = str(completo).strip().lower() in ("true", "1", "sim")

run_id = novo_run_id()
garantir_ctl()

lotes = [r["batch_id"] for r in lotes_validos("pessoa_juridica").select("batch_id").collect()]
bronze = ler_lote("pessoa_juridica", lotes)
desde = None
if not reprocessar and spark.catalog.tableExists(TABELA):
    desde = spark.table(TABELA).agg(F.max("_ingested_at")).first()[0]
if desde is not None:
    bronze = bronze.filter(F.col("_ingested_at") > F.lit(desde))

mais_recente = Window.partitionBy("_cnpj").orderBy(F.col("_ingested_at").desc())
df = (
    bronze.withColumn("_ordem", F.row_number().over(mais_recente)).filter("_ordem = 1")
    .select(
        F.col("_cnpj").alias("cnpj"),
        (F.col("_resultado") == "encontrado").alias("encontrado"),
        campo("razaoSocial").alias("razao_social"),
        campo("nomeFantasia").alias("nome_fantasia"),
        booleano(campo("favorecidoDespesas")).alias("favorecido_despesas"),
        booleano(campo("possuiContratacao")).alias("possui_contratacao"),
        booleano(campo("convenios")).alias("possui_convenios"),
        booleano(campo("favorecidoTransferencias")).alias("favorecido_transferencias"),
        booleano(campo("participanteLicitacao")).alias("participante_licitacao"),
        booleano(campo("emitiuNFe")).alias("emitiu_nfe"),
        booleano(campo("sancionadoCEIS")).alias("sancionado_ceis"),
        booleano(campo("sancionadoCNEP")).alias("sancionado_cnep"),
        booleano(campo("sancionadoCEPIM")).alias("sancionado_cepim"),
        booleano(campo("sancionadoCEAF")).alias("sancionado_ceaf"),
        booleano(campo("beneficiadoRenunciaFiscal")).alias("beneficiado_renuncia_fiscal"),
        booleano(campo("isentoImuneRenunciaFiscal")).alias("isento_imune_renuncia_fiscal"),
        booleano(campo("habilitadoRenunciaFiscal")).alias("habilitado_renuncia_fiscal"),
        *linhagem(),
    )
    .cache()
)

n = df.count()
resultado = {"particoes": [f"desde={desde}" if desde else "todos"], "linhas_preparadas": n, "status": "passed"}
print(f"CNPJs a gravar: {n}")
if n:
    # razao_social não é obrigatória: o Portal devolve alguns CNPJs encontrados com nome vazio e os
    # indicadores preenchidos (89 de 33.967 em dev, 2026-11-17; research R5 da feature 004).
    obrig = ["cnpj", "encontrado",
             ("cnpj_14_digitos", ~F.coalesce(F.col("cnpj").rlike(r"^\d{14}$"), F.lit(False)))]
    if verificar(df, TABELA, CHAVE, obrig, run_id, resultado["particoes"][0]):
        mesclar_particao(df, TABELA, CHAVE, remover=False)
    else:
        resultado["status"] = "failed"
df.unpersist()

if spark.catalog.tableExists(TABELA):
    resultado["linhas_tabela"] = registrar_contagem(TABELA, run_id, resultado["particoes"][0])

encerrar(run_id, {TABELA: resultado})

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
