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

# # nb-incr-020-silver-transparencia-emendas
# Emendas parlamentares para a `silver_transparencia.emendas`, pelo último lote `succeeded` de cada ano.
# - `MERGE` por `chave_emenda` (SHA-256 da linha) que apaga o que sumiu do ano (research R4 e R6 da feature 004).
# - `anos` vazio: só os anos com lote novo na Bronze. `anos=2025,2026`: esses anos, mesmo sem lote novo.
# - `duplicar_para_teste=true` duplica uma linha antes das verificações, para provar que a falha de qualidade interrompe a carga (T022). Nunca usar em produção.
# - Contrato: `specs/004-gastos-silver/contracts/silver-tables.md`

# PARAMETERS CELL ********************

anos = ""
duplicar_para_teste = "false"

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

TABELA = "emendas"
CHAVE = "chave_emenda"
OBRIGATORIAS = ["chave_emenda", "ano", "tipo_emenda", "autor", "valor_empenhado", "valor_liquidado", "valor_pago"]
duplicar = str(duplicar_para_teste).strip().lower() in ("true", "1", "sim")
if duplicar and ambiente() == "prd":
    raise ValueError("duplicar_para_teste não pode ser usado em produção")

run_id = novo_run_id()
garantir_ctl()


def preparar(batch_id):
    b = ler_lote("emendas", batch_id)
    return b.select(
        chave_hash().alias("chave_emenda"),
        campo("codigoEmenda").alias("codigo_emenda"),
        inteiro(campo("ano")).alias("ano"),
        campo("numeroEmenda").alias("numero_emenda"),
        campo("tipoEmenda").alias("tipo_emenda"),
        campo("autor").alias("autor"),
        campo("nomeAutor").alias("nome_autor"),
        campo("localidadeDoGasto").alias("localidade_gasto"),
        campo("funcao").alias("funcao"),
        campo("subfuncao").alias("subfuncao"),
        valor_br(campo("valorEmpenhado")).alias("valor_empenhado"),
        valor_br(campo("valorLiquidado")).alias("valor_liquidado"),
        valor_br(campo("valorPago")).alias("valor_pago"),
        valor_br(campo("valorRestoInscrito")).alias("valor_resto_inscrito"),
        valor_br(campo("valorRestoCancelado")).alias("valor_resto_cancelado"),
        valor_br(campo("valorRestoPago")).alias("valor_resto_pago"),
        *linhagem(),
    )


pendentes = anos_a_processar("emendas", TABELA, anos)
resultado = {"particoes": [a for a, _ in pendentes], "linhas_preparadas": 0, "status": "passed"}
print(f"anos a processar: {resultado['particoes'] or 'nenhum (Silver já reflete o último lote de cada ano)'}")

for ano, batch_id in pendentes:
    df = preparar(batch_id)
    if duplicar:
        df = df.unionByName(df.limit(1))
    df = df.cache()
    obrig = OBRIGATORIAS + [("ano_igual_ao_lote", F.coalesce(F.col("ano") != F.lit(ano), F.lit(True)))]
    ok = verificar(df, TABELA, CHAVE, obrig, run_id, f"ano={ano} lote={batch_id}")
    if not ok:
        resultado["status"] = "failed"
        df.unpersist()
        break
    resultado["linhas_preparadas"] += df.count()
    mesclar_particao(df, TABELA, CHAVE, f"t.ano = {ano}")
    df.unpersist()
    print(f"{ano}: ok")

if spark.catalog.tableExists(TABELA):
    resultado["linhas_tabela"] = registrar_contagem(TABELA, run_id, f"anos={','.join(map(str, resultado['particoes']))}")

encerrar(run_id, {TABELA: resultado})

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
