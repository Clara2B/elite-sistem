"""Limites de mês (Fase 4) — usado por várias seções pra filtrar "dentro
do mês" ou "até o fim do mês"; um só lugar pra não repetir a conta em
cada módulo de `secoes/`."""
from __future__ import annotations

from calendar import monthrange
from datetime import date


def primeiro_dia_do_mes(mes: int, ano: int) -> date:
    return date(ano, mes, 1)


def ultimo_dia_do_mes(mes: int, ano: int) -> date:
    return date(ano, mes, monthrange(ano, mes)[1])


def dentro_do_mes(valor: date | None, mes: int, ano: int) -> bool:
    return valor is not None and valor.month == mes and valor.year == ano
