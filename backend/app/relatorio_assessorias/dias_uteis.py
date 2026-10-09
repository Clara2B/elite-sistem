"""Contagem de dias úteis (Fase 4) — exclui sábados, domingos e feriados
nacionais via biblioteca `holidays` (decisão da Clara, 2026-10-08: só
feriados nacionais, já que os processos são de vários estados e a
especificação já define "dias úteis" assim, sem distinguir estado).

Convenção de contagem (sem número do critério de aceite pra testar
diretamente — sinalizado pra confirmação da Clara no resumo da Fase 4):
dias úteis "entre" duas datas = dias úteis estritamente depois de
`inicio` até `fim`, inclusive. `inicio == fim` → 0 dias úteis decorridos;
`fim` no próximo dia útil depois de `inicio` → 1. É a convenção mais
comum pra "prazo cumprido em N dias úteis" (conta dias que se passaram,
não os dois extremos)."""
from __future__ import annotations

from datetime import date, timedelta
from functools import cache

import holidays as _holidays_lib


@cache
def _feriados_do_ano(ano: int) -> _holidays_lib.HolidayBase:
    return _holidays_lib.Brazil(years=ano)


def eh_dia_util(dia: date) -> bool:
    if dia.weekday() >= 5:  # sábado=5, domingo=6
        return False
    return dia not in _feriados_do_ano(dia.year)


def contar_dias_uteis(inicio: date, fim: date) -> int:
    """Dias úteis estritamente entre `inicio` (exclusive) e `fim`
    (inclusive). `fim` anterior a `inicio` conta pra trás e devolve um
    número negativo — quem chama decide se isso é sintoma de dado
    inconsistente (ver conferências cruzadas, Fase 5: "laudo pronto com
    data de pronto anterior à data de entrada")."""
    passo = 1 if fim >= inicio else -1
    total = 0
    cursor = inicio
    while cursor != fim:
        cursor += timedelta(days=passo)
        if eh_dia_util(cursor):
            total += passo
    return total
