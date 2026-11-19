"""Testes das funções puras da Gold (contrato: specs/005-gastos-gold/contracts/notebooks-e-orquestracao.md)."""

import pytest

NOTEBOOK = "nb-util-010-gold-gastos-comum"


@pytest.fixture(scope="module")
def gold():
    from conftest import carregar_notebook_por_nome

    return carregar_notebook_por_nome(NOTEBOOK)


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("  José  da Silva ", "JOSE DA SILVA"),
        ("JANDIRA FEGHALI", "JANDIRA FEGHALI"),
        ("Coronel Chrisóstomo", "CORONEL CHRISOSTOMO"),
        ("Dr. Luiz\tOvando", "DR. LUIZ OVANDO"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_normalizar_nome(gold, entrada, esperado):
    assert gold.normalizar_nome(entrada) == esperado


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("12345678901", "***.456.789-**"),
        ("00011122233", "***.111.222-**"),
        ("1234567890", None),
        ("12345678000190", None),
        ("123.456.789-01", None),
        (None, None),
    ],
)
def test_mascarar_cpf(gold, entrada, esperado):
    assert gold.mascarar_cpf(entrada) == esperado


def test_mascara_nao_contem_onze_digitos(gold):
    mascara = gold.mascarar_cpf("98765432100")
    assert sum(c.isdigit() for c in mascara) == 6


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("12345678000190", "12.345.678/0001-90"),
        ("1234567800019", None),
        ("12345678901", None),
        (None, None),
    ],
)
def test_formatar_cnpj(gold, entrada, esperado):
    assert gold.formatar_cnpj(entrada) == esperado


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("Emenda Individual - Transferências com Finalidade Definida", "Individual"),
        ("Emenda Individual - Transferências Especiais", "Individual"),
        ("Emenda de Bancada", "Bancada"),
        ("Emenda de Comissão", "Comissão"),
        ("Emenda de Relator", "Relator"),
        ("Emenda de Bancada de Senado", "Bancada"),
        ("Outro tipo", "Outro"),
        (None, "Outro"),
    ],
)
def test_grupo_emenda(gold, entrada, esperado):
    assert gold.grupo_emenda(entrada) == esperado


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("SÃO PAULO (UF)", ("Estado", "SP")),
        ("DISTRITO FEDERAL (UF)", ("Estado", "DF")),
        ("Paraná (UF)", ("Estado", "PR")),
        ("CAMPINAS - SP", ("Município", "SP")),
        ("SANTA RITA D'OESTE - SP", ("Município", "SP")),
        ("MÚLTIPLO", ("Múltiplo", None)),
        ("Nacional", ("Nacional", None)),
        ("NACIONAL", ("Nacional", None)),
        ("ATLÂNTIDA (UF)", ("Outro", None)),
        ("CIDADE - XX", ("Outro", None)),
        ("Exterior", ("Outro", None)),
        (None, ("Outro", None)),
    ],
)
def test_ler_localidade(gold, entrada, esperado):
    assert gold.ler_localidade(entrada) == esperado


def test_ufs(gold):
    siglas = [s for s, _, _ in gold.UFS]
    assert len(gold.UFS) == 27
    assert len(set(siglas)) == 27
    assert {r for _, _, r in gold.UFS} == {"Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"}
    assert ("DF", "Distrito Federal", "Centro-Oeste") in gold.UFS


@pytest.mark.parametrize(
    "texto,acusa",
    [
        ("12345678901", True),
        ("FULANO 123.456.789-01", True),
        ("FULANO CPF 12345678901 ME", True),
        ("12345678000190", False),
        ("J:12345678000190", False),
        ("***.456.789-**", False),
        ("12.345.678/0001-90", False),
        ("1234567890", False),
    ],
)
def test_cpf_sem_mascara(gold, texto, acusa):
    import re

    assert (re.search(gold.CPF_SEM_MASCARA, texto) is not None) is acusa


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("FULANO DE TAL 12345678901", "FULANO DE TAL ***.456.789-**"),
        ("12345678901 FULANO", "***.456.789-** FULANO"),
        ("FULANO 123.456.789-01 ME", "FULANO ***.456.789-** ME"),
        ("EMPRESA 12345678000190", "EMPRESA 12345678000190"),
        ("LOJA 2024 LTDA", "LOJA 2024 LTDA"),
        (None, None),
    ],
)
def test_mascarar_cpf_em_texto(gold, texto, esperado):
    resultado = gold.mascarar_cpf_em_texto(texto)
    assert resultado == esperado
    if resultado:
        import re

        assert re.search(gold.CPF_SEM_MASCARA, resultado) is None


@pytest.mark.parametrize(
    "resposta,ok,texto",
    [
        # primeira carga em prd: tabelas novas descobertas pelo endpoint
        ({"value": [{"tableName": "fat_despesas", "status": "Success"},
                    {"tableName": "dim_data", "status": "Success"}]}, True, "Success=2"),
        # endpoint já sincronizado: NotRun não é falha
        ({"value": [{"tableName": "fat_despesas", "status": "NotRun"},
                    {"tableName": "dim_uf", "status": "NotRun"},
                    {"tableName": "dim_data", "status": "Success"}]}, True, "NotRun=2, Success=1"),
        ({"value": [{"tableName": "fat_emendas", "status": "Failure", "error": {"errorCode": "X"}},
                    {"tableName": "dim_data", "status": "Success"}]}, False,
         "falha em fat_emendas (Failure=1, Success=1)"),
        ({"value": []}, True, "nenhuma tabela"),
        (None, True, "nenhuma tabela"),
    ],
)
def test_resumir_sincronizacao(gold, resposta, ok, texto):
    assert gold.resumir_sincronizacao(resposta) == (ok, texto)
