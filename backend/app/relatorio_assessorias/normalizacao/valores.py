"""Normalização de valores monetários (Fase 3) — coluna VALOR DA CAUSA.

Problemas reais encontrados (especificação): "R$ 53.128,60\\t", "$64,000.00",
"21800.0", "R$15.295,68.", "NÃO INFORMADO", "TRABALHISTA" (texto de outra
coluna que vazou pra essa, visto em dado real).

Tratamento: converte pra `float` (mesmo tipo usado em todo o resto do
sistema pra valor monetário — `app.utils.format_brl` já formata "R$
1.234,56" a partir de float, reaproveitado na renderização, Fase 7 — não
duplicado aqui). Formato brasileiro (1.234,56) e americano (1,234.56)
detectados pela posição do ÚLTIMO separador (vírgula vs ponto). Texto não
numérico vira "Não informado" (`valor=None`, `nao_informado=True`) — não é
erro, não gera aviso; é um caso de negócio esperado e documentado na
especificação."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_PADRAO_NUMERICO = re.compile(r"^-?\d[\d.,]*$")


@dataclass
class ValorNormalizado:
    valor: float | None
    nao_informado: bool = False


def normalizar(bruto: object) -> ValorNormalizado:
    if bruto is None:
        return ValorNormalizado(None, nao_informado=True)

    if isinstance(bruto, (int, float, Decimal)):
        return ValorNormalizado(float(bruto))

    texto = re.sub(r"\s+", "", str(bruto))
    if not texto:
        return ValorNormalizado(None, nao_informado=True)

    texto = re.sub(r"^R?\$", "", texto, flags=re.IGNORECASE)
    texto = texto.rstrip(".")  # ponto final solto, ex.: "R$15.295,68."

    if not _PADRAO_NUMERICO.match(texto):
        return ValorNormalizado(None, nao_informado=True)

    indice_virgula = texto.rfind(",")
    indice_ponto = texto.rfind(".")
    if indice_virgula > indice_ponto:
        # formato brasileiro: ponto = milhar, vírgula = decimal
        texto_decimal = texto.replace(".", "").replace(",", ".")
    else:
        # formato americano (ou só um separador, ou nenhum): vírgula = milhar
        texto_decimal = texto.replace(",", "")

    try:
        return ValorNormalizado(float(Decimal(texto_decimal)))
    except InvalidOperation:
        return ValorNormalizado(None, nao_informado=True)
