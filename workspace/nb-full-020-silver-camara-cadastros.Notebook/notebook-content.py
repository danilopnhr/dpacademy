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

# # nb-full-020-silver-camara-cadastros
# Legislaturas, partidos e deputados para a `silver_camara`, pelo último lote `succeeded` de cada recurso (research R6 da feature 004).
# - O CPF dos deputados não é lido (FR-008).
# - Contrato: `specs/004-gastos-silver/contracts/silver-tables.md`

# PARAMETERS CELL ********************

recursos = "legislaturas,partidos,deputados"

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

def preparar_legislaturas(b):
    return b.select(
        inteiro(campo("id")).alias("codigo_legislatura"),
        data(campo("dataInicio")).alias("data_inicio"),
        data(campo("dataFim")).alias("data_fim"),
        *linhagem(),
    )


def preparar_partidos(b):
    return b.select(
        inteiro(campo("id")).alias("codigo_partido"),
        campo("sigla").alias("sigla_partido"),
        campo("nome").alias("nome_partido"),
        *linhagem(),
    )


def preparar_deputados(b):
    s = "ultimoStatus."
    return b.select(
        inteiro(campo("id")).alias("codigo_deputado"),
        campo("nomeCivil").alias("nome_civil"),
        campo(s + "nomeEleitoral").alias("nome_parlamentar"),
        campo(s + "siglaPartido").alias("sigla_partido"),
        campo(s + "siglaUf").alias("sigla_uf"),
        inteiro(campo(s + "idLegislatura")).alias("codigo_legislatura"),
        campo(s + "situacao").alias("situacao"),
        campo(s + "condicaoEleitoral").alias("condicao_eleitoral"),
        data(campo(s + "data")).alias("data_status"),
        campo(s + "email").alias("email"),
        campo(s + "urlFoto").alias("url_foto"),
        campo("sexo").alias("sexo"),
        data(campo("dataNascimento")).alias("data_nascimento"),
        data(campo("dataFalecimento")).alias("data_falecimento"),
        campo("ufNascimento").alias("uf_nascimento"),
        campo("municipioNascimento").alias("municipio_nascimento"),
        campo("escolaridade").alias("escolaridade"),
        *linhagem(),
    )


CONFIG = {
    "legislaturas": ("codigo_legislatura", preparar_legislaturas, ["codigo_legislatura", "data_inicio"]),
    "partidos": ("codigo_partido", preparar_partidos, ["codigo_partido", "sigla_partido", "nome_partido"]),
    "deputados": ("codigo_deputado", preparar_deputados, ["codigo_deputado", "nome_civil", "nome_parlamentar"]),
}

lista = [r.strip() for r in (recursos or "").split(",") if r.strip()]
invalidos = [r for r in lista if r not in CONFIG]
if invalidos:
    raise ValueError(f"recursos inválidos: {invalidos}; use {', '.join(CONFIG)}")

run_id = novo_run_id()
garantir_ctl()
resultados = {}
for recurso in lista:
    chave, preparar, obrigatorias = CONFIG[recurso]
    batch_id = ultimo_lote(recurso)
    if batch_id is None:
        raise ValueError(f"sem lote succeeded de {recurso} na Bronze")
    res = {"particoes": [], "linhas_preparadas": 0, "status": "passed"}
    if batch_id != lote_atual_na_silver(recurso):
        df = preparar(ler_lote(recurso, batch_id)).cache()
        if not verificar(df, recurso, chave, obrigatorias, run_id, f"lote={batch_id}"):
            res["status"] = "failed"
            resultados[recurso] = res
            df.unpersist()
            break
        res.update(particoes=[batch_id], linhas_preparadas=df.count())
        mesclar_particao(df, recurso, chave)
        df.unpersist()
    else:
        print(f"{recurso}: Silver já reflete o lote {batch_id}")
    res["linhas_tabela"] = registrar_contagem(recurso, run_id, f"lote={batch_id}")
    resultados[recurso] = res

encerrar(run_id, resultados)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
