# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "466bbb20-4164-40b5-8210-8df07d586791",
# META       "default_lakehouse_name": "gold_gastos",
# META       "default_lakehouse_workspace_id": "559ab4d8-8abd-4b75-9bdc-fd68895d93bf",
# META       "known_lakehouses": [
# META         {
# META           "id": "466bbb20-4164-40b5-8210-8df07d586791"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb-full-020-gold-gastos-modelo
# Star schema do case gastos no `gold_gastos`, reconstruído a partir da Silver: dez dimensões, `fat_despesas` e `fat_emendas` (feature 005).
# - Monta tudo, roda todas as verificações e só então grava; se alguma falhar, nada é gravado (research R1, R7).
# - Grãos: `fat_despesas`, uma linha por despesa da Silver; `fat_emendas`, uma linha por emenda × tipo × localidade.
# - CPF de fornecedor mascarado; CPF completo não entra na Gold, nem como hash (research R5).
# - Contratos: `specs/005-gastos-gold/contracts/gold-tables.md` e `data-model.md`

# PARAMETERS CELL ********************

injetar_orfao_para_teste = "false"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb-util-010-gold-gastos-comum

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql import Window

run_id = novo_run_id()
carregado_em = agora()
resultados = []
tabelas = {}  # nome -> DataFrame preparado, na ordem de gravação

sil_deputados = spark.table("silver_camara.deputados")
sil_partidos = spark.table("silver_camara.partidos")
sil_despesas = spark.table("silver_camara.despesas").cache()
sil_emendas = spark.table("silver_transparencia.emendas").cache()
sil_pj = spark.table("silver_transparencia.pessoa_juridica")

ano_final = max(carregado_em.year, sil_despesas.agg(F.max("ano")).first()[0] or carregado_em.year)
print(f"run_id={run_id} ambiente={ambiente()} despesas={sil_despesas.count()} emendas={sil_emendas.count()}")


def mapa_normalizado(df, coluna, alias):
    """Tabela pequena {valor publicado -> nome normalizado}, para não normalizar linha a linha."""
    return (df.select(coluna).where(F.col(coluna).isNotNull()).distinct()
            .withColumn(alias, normalizar_nome_udf(coluna)))


def finalizar(df, nome, coluna_sk, unicas, obrigatorias):
    """Acrescenta _carregado_em, guarda em cache e roda unicidade e obrigatórias."""
    df = df.withColumn("_carregado_em", F.lit(carregado_em)).cache()
    n = df.count()
    resultados.extend(verificar_unicidade(df, nome, unicas, n))
    resultados.extend(verificar_obrigatorias(df, nome, obrigatorias, n))
    tabelas[nome] = df
    print(f"{nome}: {n} linhas")
    return df

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Calendário (research R3)

# CELL ********************

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
DIAS = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"]


def nome_da_lista(lista, coluna):
    return F.element_at(F.array(*[F.lit(x) for x in lista]), F.col(coluna))


dim_data = (
    spark.sql(f"SELECT explode(sequence(DATE'2019-01-01', DATE'{ano_final}-12-31', INTERVAL 1 DAY)) AS data")
    .withColumn("sk_data", F.date_format("data", "yyyyMMdd").cast("int"))
    .withColumn("ano", F.year("data"))
    .withColumn("trimestre", F.quarter("data"))
    .withColumn("nome_trimestre", F.concat(F.lit("T"), F.col("trimestre")))
    .withColumn("mes", F.month("data"))
    .withColumn("nome_mes", nome_da_lista(MESES, "mes"))
    .withColumn("mes_abreviado", F.substring("nome_mes", 1, 3))
    .withColumn("mes_ano", F.concat("mes_abreviado", F.lit("/"), F.col("ano")))
    .withColumn("ordem_mes_ano", F.col("ano") * 100 + F.col("mes"))
    .withColumn("dia", F.dayofmonth("data"))
    .withColumn("dia_semana", F.dayofweek("data"))
    .withColumn("nome_dia_semana", nome_da_lista(DIAS, "dia_semana"))
    .select("sk_data", "data", "ano", "trimestre", "nome_trimestre", "mes", "nome_mes", "mes_abreviado",
            "mes_ano", "ordem_mes_ano", "dia", "dia_semana", "nome_dia_semana")
)
dim_data = finalizar(dim_data, "dim_data", "sk_data", ["sk_data"], ["sk_data", "data", "ano", "mes"])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Deputado, partido, UF e tipo de despesa (US1, research R4)

# CELL ********************

nomes_parlamentares = mapa_normalizado(sil_despesas, "nome_parlamentar", "nome_norm")

# Deputados do cadastro
cadastro = sil_deputados.select(
    "codigo_deputado", "nome_parlamentar", "nome_civil",
    F.col("sigla_partido").alias("sigla_partido_atual"), F.col("sigla_uf").alias("sigla_uf_atual"),
    "sexo", "data_nascimento", "escolaridade", "situacao", "url_foto",
    F.lit(True).alias("no_cadastro"),
)

# Deputados que só aparecem nas despesas: atributos da linha mais recente
recente = Window.partitionBy("codigo_deputado").orderBy(F.col("ano").desc(), F.col("mes").desc(), F.col("chave_despesa"))
so_despesas = (
    sil_despesas.where(F.col("codigo_deputado").isNotNull())
    .join(cadastro.select("codigo_deputado"), "codigo_deputado", "left_anti")
    .withColumn("_n", F.row_number().over(recente)).where("_n = 1")
    .select(
        "codigo_deputado", "nome_parlamentar", F.lit(None).cast("string").alias("nome_civil"),
        F.col("sigla_partido").alias("sigla_partido_atual"), F.col("sigla_uf").alias("sigla_uf_atual"),
        F.lit(None).cast("string").alias("sexo"), F.lit(None).cast("date").alias("data_nascimento"),
        F.lit(None).cast("string").alias("escolaridade"), F.lit(None).cast("string").alias("situacao"),
        F.lit(None).cast("string").alias("url_foto"), F.lit(False).alias("no_cadastro"),
    )
)

deputados = (
    cadastro.unionByName(so_despesas)
    .withColumn("e_lideranca", F.lit(False))
    .withColumn("tipo_membro", F.lit("Deputado"))
    .withColumn("chave_natural", F.concat(F.lit("D:"), F.col("codigo_deputado").cast("string")))
)

# Lideranças (despesas sem deputado): um membro por nome normalizado
liderancas = (
    sil_despesas.where(F.col("codigo_deputado").isNull() & F.col("nome_parlamentar").isNotNull())
    .join(nomes_parlamentares, "nome_parlamentar")
    .groupBy("nome_norm").agg(F.max("nome_parlamentar").alias("nome_parlamentar"))
    .select(
        F.lit(None).cast("int").alias("codigo_deputado"), "nome_parlamentar",
        F.lit(None).cast("string").alias("nome_civil"), F.lit(None).cast("string").alias("sigla_partido_atual"),
        F.lit(None).cast("string").alias("sigla_uf_atual"), F.lit(None).cast("string").alias("sexo"),
        F.lit(None).cast("date").alias("data_nascimento"), F.lit(None).cast("string").alias("escolaridade"),
        F.lit(None).cast("string").alias("situacao"), F.lit(None).cast("string").alias("url_foto"),
        F.lit(False).alias("no_cadastro"), F.lit(True).alias("e_lideranca"), F.lit("Liderança").alias("tipo_membro"),
        F.concat(F.lit("L:"), F.col("nome_norm")).alias("chave_natural"),
    )
)

dim_deputado = deputados.unionByName(liderancas).withColumn("sk_deputado", sk(F.col("chave_natural")))
dim_deputado = com_reservados(
    dim_deputado.select("sk_deputado", "codigo_deputado", "nome_parlamentar", "nome_civil", "sigla_partido_atual",
                        "sigla_uf_atual", "sexo", "data_nascimento", "escolaridade", "situacao", "url_foto",
                        "e_lideranca", "no_cadastro", "tipo_membro", "chave_natural"),
    "sk_deputado", ["nome_parlamentar", "tipo_membro", "chave_natural"],
    {"e_lideranca": False, "no_cadastro": False},
)
dim_deputado = finalizar(dim_deputado, "dim_deputado", "sk_deputado", ["sk_deputado", "chave_natural"],
                         ["sk_deputado", "nome_parlamentar", "tipo_membro", "chave_natural"])

# Partido: siglas das despesas (partido da linha, FR-006), do cadastro de deputados e do de partidos
siglas = (
    sil_despesas.select("sigla_partido")
    .union(sil_deputados.select("sigla_partido"))
    .union(sil_partidos.select("sigla_partido"))
    .where(F.col("sigla_partido").isNotNull()).distinct()
)
dim_partido = (
    siglas.join(sil_partidos.select("sigla_partido", "codigo_partido", "nome_partido"), "sigla_partido", "left")
    .withColumn("nome_partido", F.coalesce("nome_partido", "sigla_partido"))
    .withColumn("sk_partido", sk(F.concat(F.lit("P:"), F.col("sigla_partido"))))
    .select("sk_partido", "codigo_partido", "sigla_partido", "nome_partido")
)
dim_partido = com_reservados(dim_partido, "sk_partido", ["sigla_partido", "nome_partido"])
dim_partido = finalizar(dim_partido, "dim_partido", "sk_partido", ["sk_partido", "sigla_partido"],
                        ["sk_partido", "sigla_partido", "nome_partido"])

# UF: lista fixa
dim_uf = (
    spark.createDataFrame(UFS, "sigla_uf string, nome_uf string, regiao string")
    .withColumn("sk_uf", sk(F.concat(F.lit("U:"), F.col("sigla_uf"))))
    .select("sk_uf", "sigla_uf", "nome_uf", "regiao")
)
dim_uf = com_reservados(dim_uf, "sk_uf", ["sigla_uf", "nome_uf", "regiao"])
dim_uf = finalizar(dim_uf, "dim_uf", "sk_uf", ["sk_uf", "sigla_uf"], ["sk_uf", "sigla_uf", "nome_uf", "regiao"])

# Tipo de despesa: descrição mais recente de cada subcota e especificação
competencia = F.col("ano") * 100 + F.col("mes")
chave_tipo = F.concat(F.lit("T:"), F.col("codigo_subcota").cast("string"), F.lit(":"),
                      F.coalesce(F.col("codigo_especificacao_subcota").cast("string"), F.lit("")))
dim_tipo_despesa = (
    sil_despesas.where(F.col("codigo_subcota").isNotNull())
    .groupBy("codigo_subcota", "codigo_especificacao_subcota")
    .agg(F.max_by("tipo_despesa", competencia).alias("tipo_despesa"),
         F.max_by("especificacao_despesa", competencia).alias("especificacao_despesa"))
    .withColumn("chave_natural", chave_tipo)
    .withColumn("sk_tipo_despesa", sk(F.col("chave_natural")))
    .select("sk_tipo_despesa", "codigo_subcota", "tipo_despesa", "codigo_especificacao_subcota",
            "especificacao_despesa", "chave_natural")
)
dim_tipo_despesa = com_reservados(dim_tipo_despesa, "sk_tipo_despesa", ["tipo_despesa", "chave_natural"])
dim_tipo_despesa = finalizar(dim_tipo_despesa, "dim_tipo_despesa", "sk_tipo_despesa",
                             ["sk_tipo_despesa", "chave_natural"], ["sk_tipo_despesa", "tipo_despesa"])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Fornecedor (US2, research R5)

# CELL ********************

# Nome publicado sem CPF embutido (alguns nomes de pessoa física trazem o documento)
despesas_f = sil_despesas.withColumn("nome_fornecedor", mascarar_cpf_em_coluna("nome_fornecedor"))
nomes_fornecedores = mapa_normalizado(despesas_f, "nome_fornecedor", "nome_fornecedor_norm")
despesas_f = (
    despesas_f.join(nomes_fornecedores, "nome_fornecedor", "left")
    .withColumn("chave_fornecedor", F.when(
        F.col("tipo_documento_fornecedor") == "CNPJ", F.concat(F.lit("J:"), F.col("documento_fornecedor"))
    ).when(
        F.col("tipo_documento_fornecedor") == "CPF",
        F.concat(F.lit("F:"), mascarar_cpf_udf("documento_fornecedor"), F.lit("|"),
                 F.coalesce("nome_fornecedor_norm", F.lit("")))
    ).when(
        F.col("nome_fornecedor_norm").isNotNull(), F.concat(F.lit("S:"), F.col("nome_fornecedor_norm"))
    ))
)

# Nome mais frequente por fornecedor; empate: o mais recente, depois a ordem alfabética
contagem_nomes = (
    despesas_f.where(F.col("chave_fornecedor").isNotNull())
    .groupBy("chave_fornecedor", "tipo_documento_fornecedor", "documento_fornecedor", "nome_fornecedor")
    .agg(F.count(F.lit(1)).alias("_vezes"), F.max(competencia).alias("_recente"))
)
ordem_nome = Window.partitionBy("chave_fornecedor").orderBy(
    F.col("_vezes").desc(), F.col("_recente").desc(), F.col("nome_fornecedor").asc_nulls_last())
fornecedores = contagem_nomes.withColumn("_n", F.row_number().over(ordem_nome)).where("_n = 1")

pj = sil_pj.select(
    "cnpj", "encontrado", "razao_social", "nome_fantasia", "sancionado_ceis", "sancionado_cnep",
    "sancionado_cepim", "sancionado_ceaf", "possui_contratacao", "possui_convenios", "participante_licitacao",
    "favorecido_transferencias", "beneficiado_renuncia_fiscal",
).withColumn("razao_social", mascarar_cpf_em_coluna("razao_social")) \
 .withColumn("nome_fantasia", mascarar_cpf_em_coluna("nome_fantasia"))  # MEI traz o CPF do dono na razão social
e_cnpj = F.col("tipo_documento_fornecedor") == "CNPJ"
dim_fornecedor = (
    fornecedores
    .withColumn("cnpj", F.when(e_cnpj, F.col("documento_fornecedor")))
    .join(pj, "cnpj", "left")
    .withColumn("tipo_documento", F.when(e_cnpj, "CNPJ")
                .when(F.col("tipo_documento_fornecedor") == "CPF", "CPF").otherwise("Sem documento"))
    .withColumn("documento_exibicao", F.when(e_cnpj, formatar_cnpj_udf("documento_fornecedor"))
                .when(F.col("tipo_documento_fornecedor") == "CPF", mascarar_cpf_udf("documento_fornecedor")))
    .withColumn("situacao_portal", F.when(~e_cnpj, "Não se aplica")
                .when(F.col("encontrado") == True, "Encontrado")  # noqa: E712
                .when(F.col("encontrado") == False, "Não encontrado")  # noqa: E712
                .otherwise("Não consultado"))
    .withColumn("possui_sancao", F.when(F.col("encontrado") == True, F.coalesce(  # noqa: E712
        F.col("sancionado_ceis") | F.col("sancionado_cnep") | F.col("sancionado_cepim") | F.col("sancionado_ceaf"),
        F.lit(False))))
    # Fornecedor sem nome publicado: razão social do Portal, senão o documento exibido
    .withColumn("nome_fornecedor", F.coalesce("nome_fornecedor", "razao_social", "documento_exibicao"))
    .withColumn("chave_natural", F.col("chave_fornecedor"))
    .withColumn("sk_fornecedor", sk(F.col("chave_natural")))
    .select("sk_fornecedor", "tipo_documento", "documento_exibicao", "cnpj", "nome_fornecedor", "situacao_portal",
            "razao_social", "nome_fantasia", "possui_sancao", "sancionado_ceis", "sancionado_cnep",
            "sancionado_cepim", "sancionado_ceaf", "possui_contratacao", "possui_convenios",
            "participante_licitacao", "favorecido_transferencias", "beneficiado_renuncia_fiscal", "chave_natural")
)
dim_fornecedor = com_reservados(dim_fornecedor, "sk_fornecedor",
                                ["nome_fornecedor", "tipo_documento", "situacao_portal", "chave_natural"])
dim_fornecedor = finalizar(dim_fornecedor, "dim_fornecedor", "sk_fornecedor", ["sk_fornecedor", "chave_natural"],
                           ["sk_fornecedor", "tipo_documento", "nome_fornecedor", "situacao_portal"])
resultados.extend(verificar_privacidade(
    dim_fornecedor, "dim_fornecedor", ["documento_exibicao", "nome_fornecedor", "razao_social", "nome_fantasia",
                                       "chave_natural"]))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## `fat_despesas` (US1, US2)

# CELL ********************

def sk_ou(condicao_nula, chave):
    """sk da chave natural, ou -1 quando a chave da fonte está vazia (FR-004)."""
    return F.when(condicao_nula, F.lit(SK_NAO_INFORMADO).cast("bigint")).otherwise(sk(chave))


siglas_uf = [s for s, _, _ in UFS]
fat_despesas = (
    despesas_f.join(nomes_parlamentares, "nome_parlamentar", "left")
    .select(
        "chave_despesa",
        (F.col("ano") * 10000 + F.col("mes") * 100 + 1).alias("sk_data_competencia"),
        F.when(F.col("codigo_deputado").isNotNull(),
               sk(F.concat(F.lit("D:"), F.col("codigo_deputado").cast("string"))))
         .when(F.col("nome_norm").isNotNull(), sk(F.concat(F.lit("L:"), F.col("nome_norm"))))
         .otherwise(F.lit(SK_NAO_INFORMADO).cast("bigint")).alias("sk_deputado"),
        sk_ou(F.col("sigla_partido").isNull(), F.concat(F.lit("P:"), F.col("sigla_partido"))).alias("sk_partido"),
        sk_ou(~F.coalesce(F.col("sigla_uf").isin(siglas_uf), F.lit(False)),
              F.concat(F.lit("U:"), F.col("sigla_uf"))).alias("sk_uf"),
        sk_ou(F.col("codigo_subcota").isNull(), chave_tipo).alias("sk_tipo_despesa"),
        sk_ou(F.col("chave_fornecedor").isNull(), F.col("chave_fornecedor")).alias("sk_fornecedor"),
        "ano", "mes", F.col("data_emissao"), "numero_documento", "codigo_documento", "url_documento",
        "passageiro", "trecho", "valor_documento", "valor_glosa", "valor_liquido", "valor_restituicao", "_batch_id",
    )
)
if injetar_orfao_para_teste.strip().lower() == "true":
    # Teste de falha (US5, SC-008): uma linha com fornecedor inexistente
    orfa = fat_despesas.limit(1).withColumn("chave_despesa", F.concat("chave_despesa", F.lit("-orfao"))) \
        .withColumn("sk_fornecedor", F.lit(123).cast("bigint"))
    fat_despesas = fat_despesas.unionByName(orfa)
    print("ATENÇÃO: linha órfã injetada para teste")

fat_despesas = finalizar(
    fat_despesas, "fat_despesas", None, ["chave_despesa"],
    ["chave_despesa", "sk_data_competencia", "sk_deputado", "sk_partido", "sk_uf", "sk_tipo_despesa",
     "sk_fornecedor", "ano", "mes", "valor_documento", "valor_liquido"])
n_desp = fat_despesas.count()
for coluna, dim, nome_dim, coluna_dim in [
    ("sk_data_competencia", dim_data, "dim_data", "sk_data"),
    ("sk_deputado", dim_deputado, "dim_deputado", None),
    ("sk_partido", dim_partido, "dim_partido", None),
    ("sk_uf", dim_uf, "dim_uf", None),
    ("sk_tipo_despesa", dim_tipo_despesa, "dim_tipo_despesa", None),
    ("sk_fornecedor", dim_fornecedor, "dim_fornecedor", None),
]:
    resultados.extend(verificar_integridade(fat_despesas, "fat_despesas", coluna, dim, nome_dim, coluna_dim, n_desp))
resultados.extend(verificar_conciliacao(fat_despesas, sil_despesas, "fat_despesas", ["ano"], ["valor_liquido"], n_desp))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Emendas (US3, research R6)

# CELL ********************

tipos_emenda = (sil_emendas.select("tipo_emenda").where(F.col("tipo_emenda").isNotNull()).distinct()
                .withColumn("grupo_emenda", grupo_emenda_udf("tipo_emenda")))
emendas = sil_emendas.join(tipos_emenda, "tipo_emenda", "left") \
    .withColumn("grupo_emenda", F.coalesce("grupo_emenda", F.lit("Outro")))

dim_tipo_emenda = (
    tipos_emenda.withColumn("sk_tipo_emenda", sk(F.concat(F.lit("E:"), F.col("tipo_emenda"))))
    .select("sk_tipo_emenda", "tipo_emenda", "grupo_emenda")
)
dim_tipo_emenda = com_reservados(dim_tipo_emenda, "sk_tipo_emenda", ["tipo_emenda", "grupo_emenda"])
dim_tipo_emenda = finalizar(dim_tipo_emenda, "dim_tipo_emenda", "sk_tipo_emenda", ["sk_tipo_emenda", "tipo_emenda"],
                            ["sk_tipo_emenda", "tipo_emenda", "grupo_emenda"])

chave_funcao = F.concat(F.lit("FN:"), F.coalesce("funcao", F.lit("")), F.lit(":"), F.coalesce("subfuncao", F.lit("")))
dim_funcao = (
    sil_emendas.select("funcao", "subfuncao").where(F.col("funcao").isNotNull() | F.col("subfuncao").isNotNull())
    .distinct().withColumn("chave_natural", chave_funcao).withColumn("sk_funcao", sk(F.col("chave_natural")))
    .select("sk_funcao", "funcao", "subfuncao", "chave_natural")
)
dim_funcao = com_reservados(dim_funcao, "sk_funcao", ["funcao", "chave_natural"])
dim_funcao = finalizar(dim_funcao, "dim_funcao", "sk_funcao", ["sk_funcao", "chave_natural"], ["sk_funcao", "funcao"])

dim_localidade = (
    sil_emendas.select("localidade_gasto").where(F.col("localidade_gasto").isNotNull()).distinct()
    .withColumn("_loc", ler_localidade_udf("localidade_gasto"))
    .withColumn("sk_localidade", sk(F.concat(F.lit("LC:"), F.col("localidade_gasto"))))
    .select("sk_localidade", "localidade_gasto", F.col("_loc.nivel").alias("nivel_localidade"),
            F.col("_loc.sigla_uf").alias("sigla_uf_localidade"))
)
dim_localidade = com_reservados(dim_localidade, "sk_localidade", ["localidade_gasto", "nivel_localidade"])
dim_localidade = finalizar(dim_localidade, "dim_localidade", "sk_localidade", ["sk_localidade", "localidade_gasto"],
                           ["sk_localidade", "localidade_gasto", "nivel_localidade"])

# Autor: ligação ao deputado por nome normalizado, só com candidato único (research R6)
nomes_autores = mapa_normalizado(emendas, "nome_autor", "autor_norm")
candidatos = (
    dim_deputado.where(F.col("tipo_membro") == "Deputado")
    .select("sk_deputado", "nome_parlamentar").join(
        mapa_normalizado(dim_deputado.where(F.col("tipo_membro") == "Deputado"), "nome_parlamentar", "autor_norm"),
        "nome_parlamentar")
    .groupBy("autor_norm").agg(F.count(F.lit(1)).alias("_candidatos"), F.min("sk_deputado").alias("_sk_unico"))
)
autores = (
    emendas.select("nome_autor", "grupo_emenda").distinct()
    .join(nomes_autores, "nome_autor", "left")
    .join(candidatos, "autor_norm", "left")
)
individual = F.col("grupo_emenda") == "Individual"
sem_info = F.coalesce(F.col("autor_norm"), F.lit("SEM INFORMACAO")) == "SEM INFORMACAO"
ligado = individual & ~sem_info & (F.col("_candidatos") == 1)
dim_autor_emenda = (
    autores
    .withColumn("ligado_a_deputado", F.coalesce(ligado, F.lit(False)))
    .withColumn("sk_deputado_ligado", F.when(F.col("ligado_a_deputado"), F.col("_sk_unico")))
    .withColumn("tipo_autor", F.when(sem_info, "Sem informação")
                .when(F.col("ligado_a_deputado"), "Deputado")
                .when(individual, "Parlamentar não identificado")
                .when(F.col("grupo_emenda") == "Outro", "Sem informação")
                .otherwise(F.col("grupo_emenda")))
    .withColumn("motivo_sem_ligacao", F.when(F.col("ligado_a_deputado"), F.lit(None).cast("string"))
                .when(~individual | sem_info, "não se aplica")
                .when(F.col("_candidatos") > 1, "ambíguo")
                .otherwise("não casou"))
    .withColumn("nome_autor", F.coalesce("nome_autor", F.lit("Sem informação")))
    .withColumn("chave_natural", F.concat(F.lit("A:"), F.col("grupo_emenda"), F.lit(":"),
                                          F.coalesce("autor_norm", F.lit(""))))
    .withColumn("sk_autor_emenda", sk(F.col("chave_natural")))
)
mapa_autor = dim_autor_emenda.select("chave_natural", "sk_autor_emenda", "sk_deputado_ligado").cache()
dim_autor_emenda = dim_autor_emenda.select(
    "sk_autor_emenda", "nome_autor", "grupo_emenda", "tipo_autor", "ligado_a_deputado", "motivo_sem_ligacao",
    "chave_natural").dropDuplicates(["chave_natural"])
dim_autor_emenda = com_reservados(dim_autor_emenda, "sk_autor_emenda", ["nome_autor", "tipo_autor", "chave_natural"],
                                  {"ligado_a_deputado": False})
dim_autor_emenda = finalizar(dim_autor_emenda, "dim_autor_emenda", "sk_autor_emenda",
                             ["sk_autor_emenda", "chave_natural"], ["sk_autor_emenda", "nome_autor", "tipo_autor"])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## `fat_emendas` (US3)

# CELL ********************

fat_emendas = (
    emendas.join(nomes_autores, "nome_autor", "left")
    .withColumn("chave_natural", F.concat(F.lit("A:"), F.col("grupo_emenda"), F.lit(":"),
                                          F.coalesce("autor_norm", F.lit(""))))
    .join(mapa_autor.dropDuplicates(["chave_natural"]), "chave_natural", "left")
    .select(
        "chave_emenda",
        (F.col("ano") * 10000 + 101).alias("sk_data_ano"),
        F.coalesce("sk_deputado_ligado", F.lit(SK_NAO_SE_APLICA).cast("bigint")).alias("sk_deputado"),
        F.coalesce("sk_autor_emenda", F.lit(SK_NAO_INFORMADO).cast("bigint")).alias("sk_autor_emenda"),
        sk_ou(F.col("tipo_emenda").isNull(), F.concat(F.lit("E:"), F.col("tipo_emenda"))).alias("sk_tipo_emenda"),
        sk_ou(F.col("funcao").isNull() & F.col("subfuncao").isNull(), chave_funcao).alias("sk_funcao"),
        sk_ou(F.col("localidade_gasto").isNull(), F.concat(F.lit("LC:"), F.col("localidade_gasto"))).alias("sk_localidade"),
        "ano", "codigo_emenda", "numero_emenda", "valor_empenhado", "valor_liquidado", "valor_pago",
        "valor_resto_inscrito", "valor_resto_cancelado", "valor_resto_pago", "_batch_id",
    )
)
fat_emendas = finalizar(
    fat_emendas, "fat_emendas", None, ["chave_emenda"],
    ["chave_emenda", "sk_data_ano", "sk_deputado", "sk_autor_emenda", "sk_tipo_emenda", "sk_funcao", "sk_localidade",
     "ano", "valor_empenhado", "valor_liquidado", "valor_pago"])
n_em = fat_emendas.count()
for coluna, dim, nome_dim, coluna_dim in [
    ("sk_data_ano", dim_data, "dim_data", "sk_data"),
    ("sk_deputado", dim_deputado, "dim_deputado", None),
    ("sk_autor_emenda", dim_autor_emenda, "dim_autor_emenda", None),
    ("sk_tipo_emenda", dim_tipo_emenda, "dim_tipo_emenda", None),
    ("sk_funcao", dim_funcao, "dim_funcao", None),
    ("sk_localidade", dim_localidade, "dim_localidade", None),
]:
    resultados.extend(verificar_integridade(fat_emendas, "fat_emendas", coluna, dim, nome_dim, coluna_dim, n_em))

medidas_emenda = ["valor_empenhado", "valor_liquidado", "valor_pago"]
fato_com_tipo = fat_emendas.join(dim_tipo_emenda.select("sk_tipo_emenda", "tipo_emenda"), "sk_tipo_emenda", "left")
resultados.extend(verificar_conciliacao(fato_com_tipo, sil_emendas, "fat_emendas", ["ano", "tipo_emenda"],
                                        medidas_emenda, n_em))

# Parcela do valor pago das emendas individuais ligada a deputado (informativa; SC-004)
lig = (fat_emendas.join(dim_autor_emenda.select("sk_autor_emenda", "grupo_emenda", "ligado_a_deputado"), "sk_autor_emenda")
       .where(F.col("grupo_emenda") == "Individual")
       .agg(F.sum("valor_pago").alias("total"),
            F.sum(F.when(F.col("ligado_a_deputado"), F.col("valor_pago"))).alias("ligado"),
            F.countDistinct(F.when(F.col("ligado_a_deputado"), F.col("sk_autor_emenda"))).alias("autores_ligados"))
       .first())
amb = dim_autor_emenda.where(F.col("motivo_sem_ligacao") == "ambíguo").count()
pct = float(lig["ligado"] or 0) / float(lig["total"]) * 100 if lig["total"] else 0.0
resultados.extend(informativa("fat_emendas", "ligacao_autor", n_em,
                              f"pct_pago_individual_ligado={pct:.1f}; autores_ligados={lig['autores_ligados']}; "
                              f"autores_ambiguos={amb}"))
print(f"ligação de autor: {pct:.1f}% do valor pago individual; ambíguos={amb}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Registro, gravação e encerramento (research R1, R7)

# CELL ********************

registrar(run_id, resultados)
contagens = {}
if not falhas(resultados):
    ordem = sorted(tabelas, key=lambda nome: nome.startswith("fat_"))  # dimensões antes dos fatos
    for nome in ordem:
        gravar(tabelas[nome], nome)
    finais = [contagem(nome) for nome in ordem]
    registrar(run_id, finais)
    contagens = {r["tabela"]: r["linhas_tabela"] for r in finais}
encerrar(run_id, resultados, contagens)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
