import pandas as pd

from app.utils import parse_date_cell


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
