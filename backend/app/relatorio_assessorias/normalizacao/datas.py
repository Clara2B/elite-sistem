"""Normalização de datas (Fase 3).

Problemas reais encontrados nas planilhas (especificação, "Normalização e
validação dos dados"; confirmado validando contra os dados reais — ver
DECISIONS.md 2026-10-08): texto "30/06/2026 - 14:00", "2026.0", "--",
~40 células com ano digitado errado (serial fora do limite) — essas
últimas, conferido diretamente, chegam do openpyxl como a string
`"#VALUE!"` (erro do próprio Excel, não um número), não como um serial
fora do intervalo — então o parser trata texto não reconhecido e serial
numérico como dois casos sempre, cobrindo os dois jeitos de dar errado.

Tratamento: aceita datetime, serial do Excel válido e texto dd/mm/aaaa
(com ou sem hora — a hora é descartada, só a data importa pro relatório).
Fora disso, vazio + aviso. Datas fora de 2020-2030 viram aviso mas o valor
é mantido (sinaliza pra conferência, não bloqueia nem zera)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_ANO_MIN, _ANO_MAX = 2020, 2030

# Excel conta dias a partir de 1899-12-30 (não 1900-01-01: a planilha
# original do Lotus 1-2-3 tinha um bug de ano bissexto em 1900 que o Excel
# manteve por compatibilidade — por isso o "dia 1" do Excel é 1899-12-31,
# e a base pra somar dias é 1899-12-30).
_BASE_SERIAL_EXCEL = date(1899, 12, 30)

_PADRAO_TEXTO = re.compile(r"^(?P<dia>\d{1,2})/(?P<mes>\d{1,2})/(?P<ano>\d{2,4})(\s*-\s*\d{1,2}:\d{2})?$")

_VAZIOS = {"", "-", "--", "---"}


@dataclass
class DataNormalizada:
    valor: date | None
    aviso: str | None = None


def normalizar(bruto: object) -> DataNormalizada:
    if bruto is None:
        return DataNormalizada(None, "data vazia")

    if isinstance(bruto, datetime):
        return _validar_intervalo(bruto.date())
    if isinstance(bruto, date):
        return _validar_intervalo(bruto)

    if isinstance(bruto, (int, float)):
        try:
            convertida = _BASE_SERIAL_EXCEL + timedelta(days=bruto)
        except (OverflowError, OSError, ValueError):
            return DataNormalizada(None, f"data inválida: serial '{bruto}' fora do limite")
        return _validar_intervalo(convertida)

    texto = str(bruto).strip()
    if texto in _VAZIOS:
        return DataNormalizada(None, "data vazia")

    casado = _PADRAO_TEXTO.match(texto)
    if not casado:
        return DataNormalizada(None, f"data não reconhecida: '{texto}'")

    dia, mes, ano = int(casado["dia"]), int(casado["mes"]), int(casado["ano"])
    if ano < 100:
        ano += 2000
    try:
        convertida = date(ano, mes, dia)
    except ValueError:
        return DataNormalizada(None, f"data inválida: '{texto}'")
    return _validar_intervalo(convertida)


def _validar_intervalo(convertida: date) -> DataNormalizada:
    if not (_ANO_MIN <= convertida.year <= _ANO_MAX):
        return DataNormalizada(
            convertida, f"data fora do intervalo esperado ({_ANO_MIN}-{_ANO_MAX}): {convertida.isoformat()}"
        )
    return DataNormalizada(convertida)
