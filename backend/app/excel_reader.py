"""Leitura genérica das planilhas .xlsx, isolando as abas de dados reais das
abas de controle/dashboard, e unificando cabeçalhos equivalentes entre abas
diferentes.

Portado de core/excel_reader.py do sistema atual (leitor-relatorio) sem
mudança de comportamento.
"""
from __future__ import annotations

import openpyxl
import pandas as pd

from app.utils import normalize

HEADER_ALIASES = {
    normalize("ENTRADA DO LAUDO"): normalize("ENTRADA DE LAUDO"),
    normalize("VALOR FALTANTE"): normalize("VALOR"),
    normalize("PAGO (SIM/NÃO)"): normalize("PAGO"),
    # Planilha "ELITE - GESTÃO DE PROCESSOS.xlsx" (Fase 5): mesmo cabeçalho
    # de fato aparece com textos diferentes entre abas (mensais, por
    # advogada, "fatais") — unifica pro parser tratar tudo igual.
    normalize("DIA"): normalize("DATA"),
    normalize("DATA DE LIBERAÇÃO - QUANDO A DRA INSERIIU O CLIENTE NA PLANILHA"): normalize("DATA"),
    normalize("FATALISSIMO"): normalize("PRAZO FATAL"),
    normalize("FATAL"): normalize("PRAZO FATAL"),
    normalize("DRA"): normalize("ADVOGADA"),
    normalize("EVENTO - DRA IQUE INSERI AS INFORMAÇÕES A SEREM FEITAS PARA O CLIENTE"): normalize("EVENTO"),
    normalize(
        "OBSERVAÇÃO - INFORMAR O QUE FOI REALIZADO OU O QUE ESTA EM ABERTP PARA ESSE CLIENTE"
    ): normalize("OBSERVAÇÃO"),
    normalize(
        "OBSERVAÇÃO - INFORMAR O QUE FOI REALIZADO OU O QUE ESTA EM ABERTO PARA ESSE CLIENTE"
    ): normalize("OBSERVAÇÃO"),
}


def _canonical_header(texto: str) -> str:
    chave = normalize(texto)
    return HEADER_ALIASES.get(chave, chave)


def _find_header_row(rows: list[tuple], required_headers: list[str]) -> int | None:
    required_canonicos = [_canonical_header(h) for h in required_headers]
    for i, row in enumerate(rows[:5]):
        values = [_canonical_header(c) for c in row if c is not None]
        if all(h in values for h in required_canonicos):
            return i
    return None


def load_data_sheets(
    path: str,
    required_headers: list[str],
    chave_duplicidade: list[str] | None = None,
) -> pd.DataFrame:
    """Lê todas as abas do arquivo que contenham as colunas exigidas e devolve
    tudo empilhado num único DataFrame, com uma coluna extra '_ABA'.

    `read_only=True`: o modo padrão do openpyxl carrega a planilha inteira
    como objetos Python na memória, o que fica pesado em planilhas com
    dezenas de milhares de linhas (ex.: Gestão de Processos, Fase 5) —
    plausível causa de estourar a memória do plano gratuito do Render. Modo
    somente leitura lê linha a linha, sem esse custo; só leitura de valor
    de célula (`iter_rows(values_only=True)`) é usada aqui, então não perde
    nada."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        frames = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            header_idx = _find_header_row(rows, required_headers)
            if header_idx is None:
                continue
            header = [
                _canonical_header(c) if c is not None else f"col_{i}"
                for i, c in enumerate(rows[header_idx])
            ]
            seen: dict[str, int] = {}
            cols = []
            for h in header:
                seen[h] = seen.get(h, 0) + 1
                cols.append(h if seen[h] == 1 else f"{h}_{seen[h]}")
            data_rows = rows[header_idx + 1:]
            df = pd.DataFrame(data_rows, columns=cols)
            df["_ABA"] = sheet_name
            df = df.dropna(how="all", subset=[c for c in cols if c != "_ABA"])
            frames.append(df)
    finally:
        wb.close()  # modo read_only mantém o arquivo aberto até fechar explicitamente
    if not frames:
        return pd.DataFrame()
    resultado = pd.concat(frames, ignore_index=True)
    if chave_duplicidade:
        colunas_chave = [_canonical_header(h) for h in chave_duplicidade]
        colunas_chave = [c for c in colunas_chave if c in resultado.columns]
    else:
        colunas_chave = []
    if not colunas_chave:
        colunas_chave = [c for c in resultado.columns if c != "_ABA"]
    resultado = resultado.drop_duplicates(subset=colunas_chave, keep="first")
    return resultado.reset_index(drop=True)
