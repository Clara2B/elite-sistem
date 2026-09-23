"""Funções auxiliares de normalização de texto e datas.

Portado de core/utils.py do sistema atual (leitor-relatorio) sem mudança de
comportamento — mesmas regras já validadas em produção.
"""
from __future__ import annotations

import unicodedata
from datetime import date, datetime

import pandas as pd


def normalize(text) -> str:
    """Remove acentos, espaços extras e diferenças de maiúsculas/minúsculas."""
    if text is None:
        return ""
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.split())
    return text.upper()


def parse_date_cell(value) -> date | None:
    """Converte um valor de célula (datetime, string dd/mm/aaaa, etc.) em date.

    Nota: `pd.isna(value)` (não só `value is None`) é necessário porque
    `pd.NaT` (célula de data vazia) passa em `isinstance(value, datetime)` —
    sem essa checagem primeiro, `.date()` devolveria o próprio `NaT` em vez
    de `None`, e esse valor acabaria sendo gravado no banco mais adiante.
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # value não é "isna-ável" (ex.: alguns tipos exóticos) — segue o fluxo normal
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 — só a data importa, sem timezone
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="raise")
        return parsed.date()
    except Exception:  # noqa: BLE001 — fallback genérico: formato não reconhecido = sem data
        return None


def cell_text(value) -> str:
    """Converte uma célula em texto, tratando None/NaN como string vazia.

    Sem isso, uma célula vazia lida pelo pandas (`float('nan')`) vira o
    texto literal `"nan"` ao passar por `str(value)` — bug real encontrado
    na validação de paridade da Fase 3 (coluna PAGO vazia sendo tratada
    como um status "NAN", entrando como pendência por engano; ver
    DECISIONS.md). Use `cell_text(v) or None` onde o campo deve ficar
    `None` (não string vazia) quando a célula estiver em branco.
    """
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def format_brl(value: float) -> str:
    """Formata um número como moeda brasileira: R$ 1.234,56"""
    text = f"{value:,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def nome_arquivo_pdf(*partes: str) -> str:
    """Monta um nome de arquivo seguro para o cabeçalho `Content-Disposition`
    (Fase 6) a partir de textos livres (ex.: nome de empresa-cliente) — troca
    espaços por "_" e remove caracteres que poderiam quebrar o cabeçalho ou
    virar um nome de arquivo estranho."""
    limpas = []
    for parte in partes:
        texto = normalize(parte).replace(" ", "_")
        texto = "".join(c for c in texto if c.isalnum() or c in "_-")
        if texto:
            limpas.append(texto)
    return "_".join(limpas) + ".pdf"
