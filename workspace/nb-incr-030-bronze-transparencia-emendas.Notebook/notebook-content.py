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
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # nb-incr-030-bronze-transparencia-emendas
# Emendas parlamentares do Portal da Transparência para a `bronze_transparencia.emendas`, um lote por ano, todos os autores.
# - Parâmetros: `specs/003-gastos-bronze-ingestion/contracts/notebook-parameters.md`
# - Chave: `Files/_secrets/transparencia_api_key` (ADR-003); nunca é impressa

# PARAMETERS CELL ********************

anos = ""

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

if (anos or "").strip():
    lista_anos = sorted({int(a) for a in anos.split(",") if a.strip()})
else:
    ano_atual = datetime.now(fuso_sao_paulo()).year
    lista_anos = [ano_atual - 1, ano_atual]

run_id = str(uuid.uuid4())
garantir_tabelas()
try:
    cliente = ClienteTransparencia()
    erro_chave = None
except ErroChave as erro:
    cliente, erro_chave = None, f"ErroChave: {erro}"


def coletar_ano(ano):
    regs = list(cliente.paginar("/emendas", {"ano": ano}))
    exigir_chave(regs, "codigoEmenda", "emendas")
    dados = [linha(r, "/emendas", {"ano": ano}) for r in regs]
    return {"dados": dados, "aviso": f"{cliente.paginas_lidas} página(s) lida(s)"}


if cliente is None:
    resultados = [lote_falho(run_id, "emendas", "api", {"ano": ano}, erro_chave) for ano in lista_anos]
else:
    resultados = [
        executar_lote(run_id, "emendas", "api", {"ano": ano}, "emendas", lambda ano=ano: coletar_ano(ano),
                      cliente, segredos=cliente.segredos())
        for ano in lista_anos
    ]
encerrar(run_id, resultados)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
