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

# # nb-full-030-bronze-camara-cadastros
# Recoleta inteira dos cadastros da Câmara para a `bronze_camara`: legislaturas, partidos e o detalhe de cada deputado das legislaturas pedidas. Um lote por recurso.
# - Parâmetros: `specs/003-gastos-bronze-ingestion/contracts/notebook-parameters.md`
# - Tabelas: `specs/003-gastos-bronze-ingestion/contracts/bronze-tables.md`

# PARAMETERS CELL ********************

recursos = ""
legislaturas = ""

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

RECURSOS_VALIDOS = ("legislaturas", "partidos", "deputados")

lista_recursos = [r.strip() for r in (recursos or ",".join(RECURSOS_VALIDOS)).split(",") if r.strip()]
invalidos = [r for r in lista_recursos if r not in RECURSOS_VALIDOS]
if invalidos:
    raise ValueError(f"recursos inválidos: {invalidos}; válidos: {RECURSOS_VALIDOS}")
lista_legislaturas = sorted({int(x) for x in (legislaturas or "56,57").split(",") if x.strip()})

run_id = str(uuid.uuid4())
cliente = ClienteCamara()
garantir_tabelas()


def coletar_legislaturas():
    regs = list(cliente.paginar("/legislaturas"))
    exigir_chave(regs, "id", "legislaturas")
    return {"dados": [linha(r, "/legislaturas", {}) for r in regs], "total_esperado": cliente.ultimo_total}


def coletar_partidos():
    # Partidos de cada legislatura pedida, para incluir siglas extintas ou fundidas desde então.
    por_id, total = {}, 0
    for leg in lista_legislaturas:
        regs = list(cliente.paginar("/partidos", {"idLegislatura": leg}))
        exigir_chave(regs, "id", "partidos")
        total += cliente.ultimo_total or 0
        for r in regs:
            por_id[r["id"]] = r
    recorte = {"legislaturas": lista_legislaturas}
    return {"dados": [linha(r, "/partidos", recorte) for r in por_id.values()],
            "aviso": f"{total} registro(s) nas legislaturas, {len(por_id)} partido(s) distinto(s)"}


def coletar_deputados():
    ids = set()
    for leg in lista_legislaturas:
        regs = list(cliente.paginar("/deputados", {"idLegislatura": leg}))
        exigir_chave(regs, "id", "deputados (fila)")
        ids.update(r["id"] for r in regs)
    recorte = {"legislaturas": lista_legislaturas}
    dados = []
    for i in sorted(ids):
        d = cliente.detalhe(f"/deputados/{i}")
        exigir_chave([d], "id", "deputados")
        dados.append(linha(d, f"/deputados/{i}", recorte))
    return {"dados": dados, "total_esperado": len(ids)}


coletores = {"legislaturas": coletar_legislaturas, "partidos": coletar_partidos, "deputados": coletar_deputados}
recortes = {"legislaturas": {}, "partidos": {"legislaturas": lista_legislaturas},
            "deputados": {"legislaturas": lista_legislaturas}}

resultados = [
    executar_lote(run_id, r, "api", recortes[r], r, coletores[r], cliente)
    for r in lista_recursos
]
encerrar(run_id, resultados)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
