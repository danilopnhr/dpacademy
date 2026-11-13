# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "14751a47-c567-4109-a7ba-191dd4855d7a",
# META       "default_lakehouse_name": "bronze_transparencia",
# META       "default_lakehouse_workspace_id": "559ab4d8-8abd-4b75-9bdc-fd68895d93bf",
# META       "known_lakehouses": [
# META         {
# META           "id": "14751a47-c567-4109-a7ba-191dd4855d7a"
# META         },
# META         {
# META           "id": "dd959c99-5fae-41c3-a6fe-56b114d845b5"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb-incr-040-bronze-transparencia-fornecedores
# Cadastro de pessoa jurídica, no Portal da Transparência, dos fornecedores que aparecem nas despesas da Câmara. Grava em `bronze_transparencia.pessoa_juridica`, em blocos de CNPJs (um lote por bloco).
# - **Desvio do Princípio I, justificado no Complexity Tracking do plano da feature 003:** a fila lê os CNPJs de `bronze_camara.despesas`. Nenhum dado da Câmara é gravado aqui; quando a `silver_camara.despesas` existir, a fila passa a ler dela (research R10).
# - CNPJ que o Portal não encontra fica com `_resultado = 'nao_encontrado'` e não é consultado de novo.
# - Parâmetros: `specs/003-gastos-bronze-ingestion/contracts/notebook-parameters.md`

# PARAMETERS CELL ********************

limite = "15000"
tamanho_bloco = "500"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb-util-010-bronze-transparencia-cliente

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb-util-020-bronze-transparencia-gravacao

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

COLUNAS_PJ = ["_cnpj", "_resultado"]
n_limite = int(limite or "15000")
n_bloco = int(tamanho_bloco or "500")
if n_limite < 1 or n_bloco < 1:
    raise ValueError("limite e tamanho_bloco precisam ser positivos")

run_id = str(uuid.uuid4())
garantir_tabelas()


def montar_fila(n):
    """CNPJs (14 dígitos) das despesas da Câmara ainda sem registro em pessoa_juridica (research R10)."""
    bruto = F.coalesce(F.get_json_object("payload", "$.txtCNPJCPF"), F.get_json_object("payload", "$.cnpjCpfFornecedor"))
    cnpjs = (
        spark.table("bronze_camara.despesas")
        .select(F.regexp_replace(bruto, "[^0-9]", "").alias("c"))
        .filter(F.length("c") == 14)
        .distinct()
    )
    feitos = spark.table("pessoa_juridica").select(F.col("_cnpj").alias("c")).distinct()
    restantes = cnpjs.join(feitos, "c", "left_anti").cache()
    total = restantes.count()
    fila = [r.c for r in restantes.orderBy("c").limit(n).collect()]
    restantes.unpersist()
    return fila, total


fila, pendentes = montar_fila(n_limite)
print(f"CNPJs pendentes: {pendentes}; nesta execução: {len(fila)}")

try:
    cliente = ClienteTransparencia()
    erro_chave = None
except ErroChave as erro:
    cliente, erro_chave = None, f"ErroChave: {erro}"


def coletar_bloco(bloco, recorte):
    dados, nao_encontrados = [], 0
    for cnpj in bloco:
        resultado, obj = cliente.pessoa_juridica(cnpj)
        nao_encontrados += resultado == "nao_encontrado"
        dados.append(linha(obj, "/pessoa-juridica", recorte, cnpj, resultado))
    return {"dados": dados, "total_esperado": len(bloco),
            "aviso": f"{nao_encontrados} não encontrado(s)" if nao_encontrados else None}


resultados = []
for i in range(0, len(fila), n_bloco):
    bloco = fila[i:i + n_bloco]
    recorte = {"cnpjs": len(bloco), "primeiro": bloco[0], "ultimo": bloco[-1]}
    if cliente is None:
        resultados.append(lote_falho(run_id, "pessoa_juridica", "api", recorte, erro_chave))
        break
    r = executar_lote(run_id, "pessoa_juridica", "api", recorte, "pessoa_juridica",
                      lambda bloco=bloco, recorte=recorte: coletar_bloco(bloco, recorte),
                      cliente, segredos=cliente.segredos(), colunas_extras=COLUNAS_PJ)
    resultados.append(r)
    if r["status"] != "succeeded":
        break  # um bloco que falhou interrompe a execução; a próxima recomeça pela fila

encerrar(run_id, resultados)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
