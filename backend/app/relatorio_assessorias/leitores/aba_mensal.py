"""Padrão de leitura "aba por mês" (Fase 2) — fontes Laudos e Iniciais.

Aba do mês reconhecida por padrão flexível: nome por extenso ou abreviado +
ano com 2 ou 4 dígitos, com ou sem espaço entre os dois (ex.: "AGO26",
"ABRIL26", "AGOSTO 2026"). Aba não encontrada vira erro bloqueante pra
aquela seção (especificação, "Regras de leitura comuns").
"""
from __future__ import annotations

from openpyxl.workbook import Workbook

from app.relatorio_assessorias.leitores import base

_MESES = {
    1: ("JAN", "JANEIRO"), 2: ("FEV", "FEVEREIRO"), 3: ("MAR", "MARÇO"),
    4: ("ABR", "ABRIL"), 5: ("MAI", "MAIO"), 6: ("JUN", "JUNHO"),
    7: ("JUL", "JULHO"), 8: ("AGO", "AGOSTO"), 9: ("SET", "SETEMBRO"),
    10: ("OUT", "OUTUBRO"), 11: ("NOV", "NOVEMBRO"), 12: ("DEZ", "DEZEMBRO"),
}


def _candidatos_nome_aba(mes: int, ano: int) -> set[str]:
    abrev, extenso = _MESES[mes]
    ano_2 = f"{ano % 100:02d}"
    ano_4 = str(ano)
    candidatos = set()
    for nome_mes in (abrev, extenso):
        for ano_str in (ano_2, ano_4):
            candidatos.add(base.normalizar_estrutural(f"{nome_mes}{ano_str}"))
            candidatos.add(base.normalizar_estrutural(f"{nome_mes} {ano_str}"))
    return candidatos


def encontrar_aba_do_mes(nomes_abas: list[str], mes: int, ano: int) -> str | None:
    candidatos = _candidatos_nome_aba(mes, ano)
    for nome_aba in nomes_abas:
        if base.normalizar_estrutural(nome_aba) in candidatos:
            return nome_aba
    return None


def encontrar_todas_abas_do_ano(nomes_abas: list[str], ano: int) -> dict[int, str]:
    """{mês: nome da aba} pra todo mês de `ano` que tiver aba no arquivo —
    usado por Iniciais (Fase 4) pra resolver "aguardando distribuição" de
    casos recebidos num mês anterior."""
    resultado = {}
    for mes in range(1, 13):
        nome_aba = encontrar_aba_do_mes(nomes_abas, mes, ano)
        if nome_aba:
            resultado[mes] = nome_aba
    return resultado


def ler(wb: Workbook, nome_planilha: str, config_fonte: dict, mes: int, ano: int) -> list[base.LinhaBruta]:
    """Lê a aba do mês `mes/ano`. Levanta `base.AbaNaoEncontrada` se não
    achar nenhuma aba com esse mês/ano, `base.CabecalhoNaoEncontrado` se a
    aba existir mas não tiver as colunas esperadas nas primeiras 10 linhas."""
    nome_aba = encontrar_aba_do_mes(wb.sheetnames, mes, ano)
    if nome_aba is None:
        raise base.AbaNaoEncontrada(nome_planilha, f"{mes:02d}/{ano}")
    linhas = list(wb[nome_aba].iter_rows(values_only=True))
    return base.ler_aba(linhas, config_fonte, nome_planilha, nome_aba)
