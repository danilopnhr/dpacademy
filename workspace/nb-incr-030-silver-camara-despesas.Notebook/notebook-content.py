# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "f416c847-1a37-4fc8-8a78-4d85a7c439f4",
# META       "default_lakehouse_name": "silver_camara",
# META       "default_lakehouse_workspace_id": "559ab4d8-8abd-4b75-9bdc-fd68895d93bf",
# META       "known_lakehouses": [
# META         {
# META           "id": "f416c847-1a37-4fc8-8a78-4d85a7c439f4"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb-incr-030-silver-camara-despesas
# Despesas da cota parlamentar para a `silver_camara.despesas`, só a partir do arquivo anual (research R1 da feature 004).
# - Cada ano é uma foto completa do último lote `succeeded` do arquivo: `MERGE` por `chave_despesa` (SHA-256 da linha) que apaga o que sumiu do ano (R4, R6).
# - `anos` vazio: só os anos com lote novo na Bronze. `anos=2025,2026`: esses anos, mesmo sem lote novo.
# - Contrato: `specs/004-gastos-silver/contracts/silver-tables.md`

# PARAMETERS CELL ********************

anos = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb-util-010-silver-camara-comum

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

TABELA = "despesas"
CHAVE = "chave_despesa"
OBRIGATORIAS = ["chave_despesa", "ano", "mes", "nome_parlamentar", "tipo_despesa", "valor_documento", "valor_liquido"]

run_id = novo_run_id()
garantir_ctl()


def preparar(ano, batch_id):
    b = ler_lote("despesas", batch_id).filter(F.col("_origem") == "arquivo")
    doc = so_digitos(campo("txtCNPJCPF"))
    # cpf e nuCarteiraParlamentar do arquivo não são lidos (FR-008)
    return b.select(
        chave_hash().alias("chave_despesa"),
        inteiro(campo("numAno")).alias("ano"),
        inteiro(campo("numMes")).alias("mes"),
        inteiro(campo("ideCadastro")).alias("codigo_deputado"),
        inteiro(campo("nuDeputadoId")).alias("numero_deputado_cota"),
        campo("txNomeParlamentar").alias("nome_parlamentar"),
        campo("sgUF").alias("sigla_uf"),
        campo("sgPartido").alias("sigla_partido"),
        inteiro(campo("codLegislatura")).alias("codigo_legislatura"),
        inteiro(campo("numSubCota")).alias("codigo_subcota"),
        campo("txtDescricao").alias("tipo_despesa"),
        inteiro(campo("numEspecificacaoSubCota")).alias("codigo_especificacao_subcota"),
        campo("txtDescricaoEspecificacao").alias("especificacao_despesa"),
        campo("txtFornecedor").alias("nome_fornecedor"),
        doc.alias("documento_fornecedor"),
        F.when(F.length(doc) == 14, "CNPJ").when(F.length(doc) == 11, "CPF").alias("tipo_documento_fornecedor"),
        campo("txtNumero").alias("numero_documento"),
        inteiro(campo("indTipoDocumento")).alias("codigo_tipo_documento"),
        data(campo("datEmissao")).alias("data_emissao"),
        valor_ponto(campo("vlrDocumento")).alias("valor_documento"),
        valor_ponto(campo("vlrGlosa")).alias("valor_glosa"),
        valor_ponto(campo("vlrLiquido")).alias("valor_liquido"),
        valor_ponto(campo("vlrRestituicao")).alias("valor_restituicao"),
        inteiro(campo("numParcela")).alias("numero_parcela"),
        campo("txtPassageiro").alias("passageiro"),
        campo("txtTrecho").alias("trecho"),
        inteiro(campo("numLote"), "bigint").alias("numero_lote"),
        campo("numRessarcimento").alias("numero_ressarcimento"),
        data(campo("datPagamentoRestituicao")).alias("data_pagamento_restituicao"),
        inteiro(campo("ideDocumento"), "bigint").alias("codigo_documento"),
        campo("urlDocumento").alias("url_documento"),
        *linhagem(),
    )


pendentes = anos_a_processar("despesas", TABELA, anos, origem="arquivo")
resultado = {"particoes": [a for a, _ in pendentes], "linhas_preparadas": 0, "status": "passed"}
print(f"anos a processar: {resultado['particoes'] or 'nenhum (Silver já reflete o último lote de cada ano)'}")

for ano, batch_id in pendentes:
    df = preparar(ano, batch_id).cache()
    # Uma linha cujo ano difere do arquivo apagaria dados de outro ano no MERGE: tratada como violação.
    obrig = OBRIGATORIAS + [("ano_igual_ao_arquivo", F.coalesce(F.col("ano") != F.lit(ano), F.lit(True)))]
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
