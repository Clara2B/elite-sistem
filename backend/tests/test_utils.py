import pandas as pd
import pytest

from app.utils import parse_date_cell, parse_valor_monetario


def test_parse_date_cell_nat_vira_none():
    # pd.NaT (célula de data vazia lida por openpyxl/pandas) passa em
    # isinstance(value, datetime) — sem tratamento explícito, isso devolveria
    # o próprio NaT em vez de None (bug real encontrado na validação de
    # paridade da Fase 3 com dados reais, ver DECISIONS.md).
    assert parse_date_cell(pd.NaT) is None


def test_parse_date_cell_none():
    assert parse_date_cell(None) is None


def test_parse_date_cell_string_dd_mm_yyyy():
    assert parse_date_cell("21/06/2026").isoformat() == "2026-06-21"


# --- parse_valor_monetario ------------------------------------------------
# Compartilhada por Correspondências e Pendências (extraída em 2026-11-24).

@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("R$ 180,00", 180.0),
        ("R$160,00", 160.0),  # sem espaço depois do "R$"
        ("R$ 1.234,56", 1234.56),
        ("R$ 280,00.", 280.0),  # ponto final sobrando (digitação)
        ("90,00", 90.0),  # sem "R$" na frente
        ("1.234", 1234.0),  # formato BR de milhar, sem vírgula decimal
        ("280.50", 280.5),  # texto simples, ponto decimal — bug real: virava 28050.0
        ("280.5", 280.5),
        ("280", 280.0),
        ("-50.5", -50.5),
    ],
)
def test_parse_valor_monetario_reconhece_formatos_validos(texto, esperado):
    assert parse_valor_monetario(texto) == esperado


@pytest.mark.parametrize("texto", ["a combinar", "", "   ", "R$ --", "grátis", None])
def test_parse_valor_monetario_devolve_none_pra_texto_nao_numerico(texto):
    assert parse_valor_monetario(texto) is None
