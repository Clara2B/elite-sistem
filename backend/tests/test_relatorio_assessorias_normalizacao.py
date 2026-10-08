"""Fase 3 (Gerador de Relatórios Mensais das Assessorias) — normalização.

Um teste por função, usando os valores problemáticos listados na
especificação (seção "Normalização e validação dos dados") e os
confirmados contra dados reais (ver DECISIONS.md 2026-10-08, Fase 3)."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models import EmpresaCliente
from app.relatorio_assessorias.normalizacao import (
    assessoria,
    datas,
    processo,
    texto,
    valores,
)

# --- datas.py ---------------------------------------------------------

def test_data_datetime_e_date_passam_direto():
    assert datas.normalizar(datetime(2026, 8, 15, 14, 0)).valor == date(2026, 8, 15)  # noqa: DTZ001
    assert datas.normalizar(date(2026, 8, 15)).valor == date(2026, 8, 15)


def test_data_texto_com_hora_descarta_hora():
    resultado = datas.normalizar("30/06/2026 - 14:00")
    assert resultado.valor == date(2026, 6, 30)
    assert resultado.aviso is None


def test_data_texto_ano_com_duas_casas():
    resultado = datas.normalizar("30/06/26")
    assert resultado.valor == date(2026, 6, 30)


def test_data_serial_excel_valido():
    # 2026-08-15 = serial 46249 (1899-12-30 + 46249 dias)
    resultado = datas.normalizar(46249)
    assert resultado.valor == date(2026, 8, 15)
    assert resultado.aviso is None


def test_data_texto_nao_numerico_tipo_2026_ponto_zero():
    resultado = datas.normalizar("2026.0")
    assert resultado.valor is None
    assert resultado.aviso is not None


def test_data_vazia_variantes():
    for bruto in ("", "-", "--", "---", None):
        resultado = datas.normalizar(bruto)
        assert resultado.valor is None
        assert resultado.aviso == "data vazia"


def test_data_erro_value_do_excel_vira_aviso_nao_bloqueia():
    resultado = datas.normalizar("#VALUE!")
    assert resultado.valor is None
    assert resultado.aviso is not None


def test_data_fora_do_intervalo_fica_com_aviso_mas_mantem_valor():
    resultado = datas.normalizar("15/03/2099")
    assert resultado.valor == date(2099, 3, 15)
    assert resultado.aviso is not None


# --- valores.py -------------------------------------------------------

@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("R$ 53.128,60\t", 53128.60),
        ("$64,000.00", 64000.00),
        ("21800.0", 21800.0),
        ("R$15.295,68.", 15295.68),
        (21800, 21800.0),
        (21800.5, 21800.5),
    ],
)
def test_valor_formatos_reais(bruto, esperado):
    resultado = valores.normalizar(bruto)
    assert resultado.nao_informado is False
    assert resultado.valor == pytest.approx(esperado)


@pytest.mark.parametrize("bruto", ["NÃO INFORMADO", "TRABALHISTA", "", None, "   "])
def test_valor_nao_numerico_vira_nao_informado_sem_aviso(bruto):
    resultado = valores.normalizar(bruto)
    assert resultado.valor is None
    assert resultado.nao_informado is True


# --- processo.py ------------------------------------------------------

def test_processo_cnj_completo_bate_padrao_cnj():
    resultado = processo.normalizar("0813055-21.2026.8.10.0001")
    assert resultado.valor == "0813055-21.2026.8.10.0001"
    assert resultado.chave_comparacao == "08130552120268100001"
    assert resultado.aviso is None


def test_processo_com_pontos_no_lugar_de_hifen_reformata():
    resultado = processo.normalizar("0813055.21.2026.8.10.0001")
    assert resultado.valor == "0813055-21.2026.8.10.0001"
    assert resultado.aviso is None


def test_processo_com_espacos_e_tabs_no_inicio():
    resultado = processo.normalizar("\t  0813055-21.2026.8.10.0001")
    assert resultado.valor == "0813055-21.2026.8.10.0001"


def test_processo_com_digito_faltando_mantem_original_e_avisa():
    resultado = processo.normalizar("813055-21.2026.8.10.0001")  # 19 dígitos
    assert resultado.valor == "813055-21.2026.8.10.0001"
    assert resultado.chave_comparacao == "8130552120268100001"
    assert "19" in resultado.aviso


def test_processo_vazio():
    for bruto in ("", None):
        resultado = processo.normalizar(bruto)
        assert resultado.chave_comparacao == ""
        assert resultado.aviso == "número de processo vazio"


def test_processo_mesma_chave_comparacao_para_formatos_diferentes():
    a = processo.normalizar("0813055-21.2026.8.10.0001")
    b = processo.normalizar("0813055.21.2026.8.10.0001")
    assert a.chave_comparacao == b.chave_comparacao


# --- texto.py -----------------------------------------------------------

def test_normalizar_nome_remove_espacos_extras_mantem_grafia():
    resultado = texto.normalizar_nome("\t  João da Silva  ")
    assert resultado.valor == "João da Silva"
    assert resultado.aviso is None


def test_normalizar_nome_vazio():
    for bruto in ("", "   ", None):
        resultado = texto.normalizar_nome(bruto)
        assert resultado.valor == ""
        assert resultado.aviso == "nome vazio"


@pytest.mark.parametrize("bruto", ["rj", "RJ", " rj "])
def test_normalizar_uf_maiuscula_valida(bruto):
    resultado = texto.normalizar_uf(bruto)
    assert resultado.valor == "RJ"
    assert resultado.aviso is None


@pytest.mark.parametrize("bruto", ["", None, "XX", "RIO DE JANEIRO"])
def test_normalizar_uf_invalida_ou_vazia(bruto):
    resultado = texto.normalizar_uf(bruto)
    assert resultado.valor is None
    assert resultado.aviso is not None


# --- assessoria.py --------------------------------------------------------

def test_construir_nomes_por_apelido_combina_empresa_cliente_e_yaml(db):
    db.add(EmpresaCliente(nome="EWS"))
    db.add(EmpresaCliente(nome="WNR"))
    db.commit()

    mapa = assessoria.construir_nomes_por_apelido(db)

    assert mapa["EWS"] == "EWS"
    assert mapa["SW"] == "EWS"  # apelido do YAML
    assert mapa["WNR CONSULTORIA"] == "WNR"


def test_construir_nomes_por_apelido_ignora_apelido_orfao(db):
    # Nenhuma EmpresaCliente "EWS" cadastrada — apelidos do YAML pra essa
    # chave não devem aparecer no mapa (ver docstring da função).
    db.add(EmpresaCliente(nome="OUTRA EMPRESA"))
    db.commit()

    mapa = assessoria.construir_nomes_por_apelido(db)

    assert "SW" not in mapa
    assert mapa["OUTRA EMPRESA"] == "OUTRA EMPRESA"


def test_resolver_celula_com_uma_empresa():
    mapa = {"RETRIX": "Retrix Assessoria"}
    resultado = assessoria.resolver("Retrix", mapa)
    assert resultado.nomes == ["Retrix Assessoria"]
    assert resultado.nao_reconhecidos == []


def test_resolver_celula_com_multiplas_empresas_separadas_por_barra():
    mapa = {"RETRIX": "Retrix Assessoria", "REVISION": "Revision Assessoria"}
    resultado = assessoria.resolver("RETRIX/ REVISION", mapa)
    assert resultado.nomes == ["Retrix Assessoria", "Revision Assessoria"]


@pytest.mark.parametrize("bruto", ["Retrix, Revision", "Retrix E Revision"])
def test_resolver_celula_com_multiplas_empresas_outros_separadores(bruto):
    mapa = {"RETRIX": "Retrix Assessoria", "REVISION": "Revision Assessoria"}
    resultado = assessoria.resolver(bruto, mapa)
    assert resultado.nomes == ["Retrix Assessoria", "Revision Assessoria"]


def test_resolver_nome_desconhecido_vai_para_nao_reconhecidos():
    resultado = assessoria.resolver("ANGITU", {})
    assert resultado.nomes == []
    assert resultado.nao_reconhecidos == ["ANGITU"]


def test_resolver_vazio():
    for bruto in ("", None, "   "):
        resultado = assessoria.resolver(bruto, {})
        assert resultado.nomes == []
        assert resultado.nao_reconhecidos == []
