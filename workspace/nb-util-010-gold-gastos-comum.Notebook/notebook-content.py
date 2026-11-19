# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # nb-util-010-gold-gastos-comum
# Biblioteca do `gold_gastos`: funções puras (nomes, documentos, emendas, localidades, UFs), chaves substitutas, verificações de qualidade (Princípio V) e gravação com V-Order.
# - Contratos: `specs/005-gastos-gold/contracts/gold-tables.md` e `contracts/notebooks-e-orquestracao.md`
# - Decisões: research R1, R2, R5, R6 e R7 da feature 005
# - Uso: `%run nb-util-010-gold-gastos-comum`, com `gold_gastos` como lakehouse padrão
# - As funções puras são testadas em `tests/unit/test_gold_comum.py` (fora do Fabric, sem PySpark)

# CELL ********************

import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from functools import reduce

try:  # no Fabric; os testes unitários carregam só as funções puras, sem PySpark
    from pyspark.sql import functions as F
    from pyspark.sql import types as T
except ImportError:  # pragma: no cover
    F = T = None

MAX_EXEMPLOS = 5
SK_NAO_INFORMADO = -1
SK_NAO_SE_APLICA = -2
ROTULO_RESERVADO = {SK_NAO_INFORMADO: "Não informado", SK_NAO_SE_APLICA: "Não se aplica"}

# --- Funções puras (testadas em pytest) ---

UFS = [
    ("AC", "Acre", "Norte"), ("AL", "Alagoas", "Nordeste"), ("AP", "Amapá", "Norte"),
    ("AM", "Amazonas", "Norte"), ("BA", "Bahia", "Nordeste"), ("CE", "Ceará", "Nordeste"),
    ("DF", "Distrito Federal", "Centro-Oeste"), ("ES", "Espírito Santo", "Sudeste"),
    ("GO", "Goiás", "Centro-Oeste"), ("MA", "Maranhão", "Nordeste"), ("MT", "Mato Grosso", "Centro-Oeste"),
    ("MS", "Mato Grosso do Sul", "Centro-Oeste"), ("MG", "Minas Gerais", "Sudeste"), ("PA", "Pará", "Norte"),
    ("PB", "Paraíba", "Nordeste"), ("PR", "Paraná", "Sul"), ("PE", "Pernambuco", "Nordeste"),
    ("PI", "Piauí", "Nordeste"), ("RJ", "Rio de Janeiro", "Sudeste"), ("RN", "Rio Grande do Norte", "Nordeste"),
    ("RS", "Rio Grande do Sul", "Sul"), ("RO", "Rondônia", "Norte"), ("RR", "Roraima", "Norte"),
    ("SC", "Santa Catarina", "Sul"), ("SP", "São Paulo", "Sudeste"), ("SE", "Sergipe", "Nordeste"),
    ("TO", "Tocantins", "Norte"),
]


def normalizar_nome(texto):
    """Maiúsculas, sem acentos, espaços colapsados; vazio vira None (research R6)."""
    if texto is None:
        return None
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", str(texto)) if not unicodedata.combining(c))
    limpo = re.sub(r"\s+", " ", sem_acento).strip().upper()
    return limpo or None


def mascarar_cpf(digitos):
    """'12345678901' -> '***.456.789-**' (dígitos 4 a 9 visíveis; research R5)."""
    if digitos is None or not re.fullmatch(r"\d{11}", digitos):
        return None
    return f"***.{digitos[3:6]}.{digitos[6:9]}-**"


# CPF dentro de texto (ex.: razão social de MEI "FULANO 12345678901"): 11 dígitos isolados ou formatado.
# Os padrões valem no Python (testes) e no Java (Spark); só a sintaxe da substituição muda.
CPF_EM_TEXTO_CRU = r"(?<!\d)\d{3}(\d{3})(\d{3})\d{2}(?!\d)"
CPF_EM_TEXTO_FORMATADO = r"(?<!\d)\d{3}\.(\d{3})\.(\d{3})-\d{2}(?!\d)"


def mascarar_cpf_em_texto(texto):
    """Troca todo CPF completo dentro do texto pela máscara ***.456.789-** (research R5)."""
    if texto is None:
        return None
    t = re.sub(CPF_EM_TEXTO_FORMATADO, r"***.\1.\2-**", texto)
    return re.sub(CPF_EM_TEXTO_CRU, r"***.\1.\2-**", t)


def formatar_cnpj(digitos):
    if digitos is None or not re.fullmatch(r"\d{14}", digitos):
        return None
    d = digitos
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def grupo_emenda(tipo_emenda):
    """Grupo do tipo de emenda publicado pelo Portal."""
    t = normalizar_nome(tipo_emenda) or ""
    if t.startswith("EMENDA INDIVIDUAL"):
        return "Individual"
    if "BANCADA" in t:
        return "Bancada"
    if "COMISSAO" in t:
        return "Comissão"
    if "RELATOR" in t:
        return "Relator"
    return "Outro"


_UF_POR_NOME = {normalizar_nome(nome): sigla for sigla, nome, _ in UFS}
_SIGLAS = {sigla for sigla, _, _ in UFS}


def ler_localidade(texto):
    """(nivel_localidade, sigla_uf_localidade) a partir de localidade_gasto (data-model)."""
    t = normalizar_nome(texto)
    if t is None:
        return ("Outro", None)
    if t == "MULTIPLO":
        return ("Múltiplo", None)
    if t == "NACIONAL":
        return ("Nacional", None)
    m = re.fullmatch(r"(.+) \(UF\)", t)
    if m:
        sigla = _UF_POR_NOME.get(m.group(1))
        return ("Estado", sigla) if sigla else ("Outro", None)
    m = re.fullmatch(r".+ - ([A-Z]{2})", t)
    if m and m.group(1) in _SIGLAS:
        return ("Município", m.group(1))
    return ("Outro", None)


def resumir_sincronizacao(resposta):
    """Resumo do resultado do refreshMetadata do SQL endpoint: (ok, texto) (research R9).

    `resposta` é o JSON devolvido pela API, com `value` = [{tableName, status, error?}].
    `NotRun` quer dizer que a tabela já estava sincronizada; só `Failure` conta como falha.
    """
    tabelas = (resposta or {}).get("value") or []
    por_status = {}
    for t in tabelas:
        por_status.setdefault(t.get("status") or "Desconhecido", []).append(t.get("tableName") or "?")
    contagem = ", ".join(f"{s}={len(n)}" for s, n in sorted(por_status.items()))
    falhas = sorted(por_status.get("Failure", []))
    if falhas:
        return False, f"falha em {', '.join(falhas[:MAX_EXEMPLOS])} ({contagem})"
    return True, contagem or "nenhuma tabela"


# CELL ********************

# --- Execução ---

if T is not None:
    # V-Order nas gravações desta sessão (Direct Lake; research R1)
    spark.conf.set("spark.sql.parquet.vorder.default", "true")

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

    normalizar_nome_udf = F.udf(normalizar_nome, T.StringType())
    mascarar_cpf_udf = F.udf(mascarar_cpf, T.StringType())
    formatar_cnpj_udf = F.udf(formatar_cnpj, T.StringType())
    grupo_emenda_udf = F.udf(grupo_emenda, T.StringType())
    ler_localidade_udf = F.udf(
        ler_localidade,
        T.StructType([T.StructField("nivel", T.StringType()), T.StructField("sigla_uf", T.StringType())]),
    )


def ambiente():
    """dev ou prd, a partir do nome do workspace ws-<ambiente>-dpacademy."""
    try:
        nome = notebookutils.runtime.context.get("currentWorkspaceName", "")
    except NameError:
        nome = ""
    m = re.match(r"^ws-([a-z0-9]+)-dpacademy$", nome or "")
    return m.group(1) if m else "desconhecido"


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def novo_run_id():
    return str(uuid.uuid4())


# --- Chaves substitutas (research R2) ---

def sk(chave_natural):
    """BIGINT determinístico a partir da chave natural (coluna ou expressão de texto)."""
    return F.xxhash64(chave_natural)


def com_reservados(df, coluna_sk, rotulos, valores=None):
    """Acrescenta os membros -1 (Não informado) e -2 (Não se aplica).

    `rotulos`: colunas de texto que recebem o rótulo do membro; `valores`: {coluna: valor fixo}
    para os dois membros (ex.: tipo_membro). As demais colunas ficam nulas.
    """
    valores = valores or {}
    linhas = []
    for s, rotulo in ROTULO_RESERVADO.items():
        linha = {c: None for c in df.columns}
        linha[coluna_sk] = s
        for c in rotulos:
            linha[c] = rotulo
        for c, v in valores.items():
            linha[c] = v(rotulo) if callable(v) else v
        linhas.append(linha)
    anulavel = T.StructType([T.StructField(f.name, f.dataType, True) for f in df.schema.fields])
    reservados = spark.createDataFrame([tuple(l[c] for c in df.columns) for l in linhas], anulavel)
    return df.unionByName(reservados)


# --- Verificações (research R7): devolvem um resultado; nada é gravado antes de registrar() ---

def _resultado(tabela, verificacao, problemas, linhas, detalhe="", informativa=False):
    status = "passed" if informativa or problemas == 0 else "failed"
    return {"tabela": tabela, "verificacao": verificacao, "status": status,
            "linhas_com_problema": int(problemas), "linhas_tabela": int(linhas), "detalhe": (detalhe or "")[:1000]}


def verificar_unicidade(df, tabela, colunas, linhas=None):
    """Uma verificação por coluna-chave (sk e chave natural)."""
    linhas = df.count() if linhas is None else linhas
    saida = []
    for c in colunas:
        rep = df.groupBy(c).count().filter(F.col("count") > 1)
        n = rep.agg(F.sum("count")).first()[0] or 0
        det = f"coluna={c}"
        if n:
            det += "; exemplos: " + ", ".join(str(r[0]) for r in rep.select(c).limit(MAX_EXEMPLOS).collect())
        saida.append(_resultado(tabela, "unicidade", n, linhas, det))
    return saida


def verificar_obrigatorias(df, tabela, colunas, linhas=None):
    linhas = df.count() if linhas is None else linhas
    viola = reduce(lambda a, b: a | b, [F.col(c).isNull() for c in colunas])
    n = df.filter(viola).count()
    det = ""
    if n:
        por = df.select([F.sum(F.when(F.col(c).isNull(), 1).otherwise(0)).alias(c) for c in colunas]).first()
        det = ", ".join(f"{c}={por[c]}" for c in colunas if por[c])
    return [_resultado(tabela, "obrigatorias", n, linhas, det)]


def verificar_integridade(fato, nome_fato, coluna, dim, nome_dim, coluna_dim=None, linhas=None):
    """Linhas do fato cuja chave estrangeira não existe na dimensão (inclui nulos)."""
    coluna_dim = coluna_dim or coluna
    linhas = fato.count() if linhas is None else linhas
    chaves = dim.select(F.col(coluna_dim).alias("_k")).distinct()
    orfas = fato.join(chaves, fato[coluna] == chaves["_k"], "left_anti")
    n = orfas.count()
    det = f"{nome_fato}.{coluna} -> {nome_dim}.{coluna_dim}"
    if n:
        det += "; exemplos: " + ", ".join(str(r[0]) for r in orfas.select(coluna).distinct().limit(MAX_EXEMPLOS).collect())
    return [_resultado(nome_fato, "integridade", n, linhas, det)]


def verificar_conciliacao(fato, silver, tabela, grupo, medidas, linhas=None):
    """Compara contagem e somas por grupo entre o fato preparado e a Silver; problemas = grupos diferentes."""
    linhas = fato.count() if linhas is None else linhas
    aggs = [F.count(F.lit(1)).alias("linhas")] + [F.sum(m).alias(m) for m in medidas]
    a = fato.groupBy(*grupo).agg(*aggs).alias("g")
    b = silver.groupBy(*grupo).agg(*aggs).alias("s")
    j = a.join(b, grupo, "full_outer")
    difere = reduce(lambda x, y: x | y, [
        ~F.col(f"g.{c}").eqNullSafe(F.col(f"s.{c}")) for c in ["linhas"] + medidas
    ])
    dif = j.filter(difere)
    n = dif.count()
    det = f"grupo={','.join(grupo)}; medidas=linhas,{','.join(medidas)}"
    if n:
        det += "; diferenças: " + "; ".join(
            str({k: r[k] for k in grupo}) for r in dif.select(*grupo).limit(MAX_EXEMPLOS).collect())
    return [_resultado(tabela, "conciliacao", n, linhas, det)]


# 11 dígitos isolados (não parte de um CNPJ de 14) ou CPF formatado
CPF_SEM_MASCARA = r"(?<!\d)(\d{11}|\d{3}\.\d{3}\.\d{3}-\d{2})(?!\d)"


def verificar_privacidade(df, tabela, colunas, linhas=None):
    """Nenhuma coluna de texto com CPF completo (11 dígitos seguidos ou formatado; research R5)."""
    linhas = df.count() if linhas is None else linhas
    viola = reduce(lambda a, b: a | b, [F.coalesce(F.col(c).rlike(CPF_SEM_MASCARA), F.lit(False)) for c in colunas])
    n = df.filter(viola).count()
    return [_resultado(tabela, "privacidade", n, linhas, f"colunas={','.join(colunas)}")]


def mascarar_cpf_em_coluna(coluna):
    """Versão Spark de mascarar_cpf_em_texto (mesmos padrões, substituição no formato Java)."""
    c = F.regexp_replace(F.col(coluna), CPF_EM_TEXTO_FORMATADO, "***.$1.$2-**")
    return F.regexp_replace(c, CPF_EM_TEXTO_CRU, "***.$1.$2-**")


def informativa(tabela, verificacao, linhas, detalhe):
    return [_resultado(tabela, verificacao, 0, linhas, detalhe, informativa=True)]


# --- Registro, gravação e encerramento ---

def garantir_ctl():
    ddl = ", ".join(f"{c.name} {c.dataType.simpleString().upper()}" for c in ESQUEMA_QUALIDADE.fields)
    spark.sql(f"CREATE TABLE IF NOT EXISTS ctl_quality_checks ({ddl}) USING DELTA")


def registrar(run_id, resultados):
    garantir_ctl()
    if not resultados:
        return
    momento, amb = agora(), ambiente()
    linhas = [(run_id, momento, r["tabela"], r["verificacao"], r["status"], r["linhas_com_problema"],
               r["linhas_tabela"], r["detalhe"], amb) for r in resultados]
    spark.createDataFrame(linhas, ESQUEMA_QUALIDADE).write.mode("append").saveAsTable("ctl_quality_checks")


def gravar(df, tabela):
    """Overwrite da tabela inteira (uma versão Delta nova, atômica por tabela) com V-Order (R1)."""
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(tabela)
    # Propriedade só na primeira vez: cada ALTER cria outra versão Delta (e outro reenquadramento do Direct Lake)
    props = {r["key"]: r["value"] for r in spark.sql(f"SHOW TBLPROPERTIES {tabela}").collect()}
    if props.get("delta.parquet.vorder.enabled") != "true":
        spark.sql(f"ALTER TABLE {tabela} SET TBLPROPERTIES ('delta.parquet.vorder.enabled' = 'true')")


def contagem(tabela):
    return _resultado(tabela, "contagem", 0, spark.table(tabela).count(), informativa=True)


def sincronizar_endpoint_sql(timeout_s=300):
    """refreshMetadata do SQL endpoint do lakehouse padrão; devolve um texto para o detalhe (research R9).

    O modelo Direct Lake lê as tabelas pelo SQL endpoint, que descobre tabelas novas de forma
    assíncrona. Na primeira carga em prd (2026-11-19) o refresh do modelo, 6 min depois da gravação,
    falhou com "cannot access the source Delta table fat_despesas". Nunca levanta exceção: a falha
    aqui só fica registrada, e o refresh do modelo decide o resultado.
    """
    import time

    import sempy.fabric as fabric

    try:
        cliente = fabric.FabricRestClient()
        ws, lh = fabric.get_workspace_id(), fabric.get_lakehouse_id()
        props = cliente.get(f"v1/workspaces/{ws}/lakehouses/{lh}").json().get("properties") or {}
        endpoint = (props.get("sqlEndpointProperties") or {}).get("id")
        if not endpoint:
            return "endpoint: sem SQL endpoint no lakehouse padrão"
        r = cliente.post(f"v1/workspaces/{ws}/sqlEndpoints/{endpoint}/refreshMetadata", json={})
        if r.status_code == 202:  # operação longa: acompanha pelo Location até terminar
            local, inicio, estado = r.headers.get("Location"), time.time(), "Running"
            while estado in ("Running", "NotStarted") and time.time() - inicio < timeout_s:
                time.sleep(int(r.headers.get("Retry-After") or 5))
                estado = cliente.get(local).json().get("status")
            if estado != "Succeeded":
                return f"endpoint: operação {estado}"
            r = cliente.get(f"{local}/result")
        ok, texto = resumir_sincronizacao(r.json())
        return f"endpoint: {texto}" if ok else f"endpoint com falha: {texto}"
    except Exception as exc:  # noqa: BLE001 - registrada no detalhe, sem derrubar a execução
        return f"endpoint não sincronizado: {exc}"[:300]


def reenquadrar_modelo(nome="sm-gastos", desde=None, timeout_s=900, pedidos_max=2):
    """Refresh (reenquadramento Direct Lake) do modelo do case depois de gravar a Gold (research R9).

    Antes de pedir o refresh, sincroniza o SQL endpoint (`sincronizar_endpoint_sql`), para o modelo
    enxergar tabelas recém-criadas. A atualização automática do Direct Lake também pode disparar
    logo depois da gravação, e as duas operações disputam o mesmo bloqueio (visto em dev em
    2026-11-18: a automática falhou por "locking conflicts" e a pedida aqui levou 5,5 min). Por isso
    conta como sucesso qualquer reenquadramento `Completed` iniciado depois de `desde` (UTC), pedido
    aqui ou automático. Se o pedido daqui falhar, sincroniza de novo e pede outra vez, até
    `pedidos_max` pedidos. Modelo ausente no workspace (ex.: antes da primeira publicação) não é falha.
    """
    import time

    import pandas as pd
    import sempy.fabric as fabric

    if nome not in set(fabric.list_datasets()["Dataset Name"]):
        return _resultado(nome, "reenquadramento", 0, 0, "modelo ausente no workspace; nada a fazer", informativa=True)
    desde = pd.Timestamp(desde or agora()).tz_localize(None)
    sincronizacao = sincronizar_endpoint_sql()

    def concluidos_depois():
        r = fabric.list_refresh_requests(dataset=nome, top_n=10)
        inicio_col = pd.to_datetime(r["Start Time"], utc=True).dt.tz_localize(None)
        return r[(r["Status"] == "Completed") & (inicio_col >= desde)]

    def pedir():
        try:
            return fabric.refresh_dataset(dataset=nome, refresh_type="full"), "Unknown"
        except Exception as exc:  # noqa: BLE001 - ex.: conflito com o reenquadramento automático em curso
            return None, f"pedido recusado: {exc}"[:300]

    req, status = pedir()
    pedidos = 1
    inicio = time.time()
    while time.time() - inicio < timeout_s:
        time.sleep(15)
        try:
            r = fabric.list_refresh_requests(dataset=nome, top_n=10)
            if req is not None:
                linha = r[r["Request Id"] == req]
                status = linha["Status"].iloc[0] if len(linha) else "Unknown"
            ok = concluidos_depois()
        except Exception as exc:  # noqa: BLE001
            status, ok = f"consulta falhou: {exc}"[:300], []
        if len(ok):
            tipos = ",".join(sorted(set(ok["Refresh Type"].astype(str))))
            return _resultado(nome, "reenquadramento", 0, 0, f"request={req}; status={status}; concluido_por={tipos}; "
                                                             f"pedidos={pedidos}; {sincronizacao}")
        if req is not None and status == "Failed":
            # o pedido daqui falhou (bloqueio perdido para o automático ou endpoint ainda sem as
            # tabelas): sincroniza o endpoint e pede de novo; esgotados os pedidos, espera o automático
            req = None
            if pedidos < pedidos_max:
                sincronizacao = sincronizar_endpoint_sql()
                req, status = pedir()
                pedidos += 1
    return _resultado(nome, "reenquadramento", 1, 0, f"request={req}; status={status}; pedidos={pedidos}; "
                                                     f"sem reenquadramento concluído em {timeout_s} s; {sincronizacao}")


def falhas(resultados):
    return [r for r in resultados if r["status"] == "failed"]


def encerrar(run_id, resultados, contagens=None):
    """Mostra as verificações, falha se alguma falhou; senão devolve o JSON do contrato."""
    display(
        spark.table("ctl_quality_checks").filter(F.col("run_id") == run_id)
        .select("tabela", "verificacao", "status", "linhas_com_problema", "linhas_tabela", "detalhe")
        .orderBy("tabela", "verificacao")
    )
    f = falhas(resultados)
    if f:
        resumo = ", ".join(sorted({f"{r['tabela']}.{r['verificacao']}" for r in f}))
        if contagens:  # a falha veio depois da gravação (ex.: reenquadramento do modelo)
            raise RuntimeError(f"{resumo} falhou depois da gravação: a Gold foi atualizada, o modelo pode estar "
                               f"com a versão anterior; veja ctl_quality_checks (run_id {run_id})")
        raise RuntimeError(f"verificação de qualidade falhou em: {resumo}; nada foi gravado na Gold (run_id {run_id})")
    notebookutils.notebook.exit(json.dumps({"run_id": run_id, "status": "succeeded", "contagens": contagens or {}}))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
