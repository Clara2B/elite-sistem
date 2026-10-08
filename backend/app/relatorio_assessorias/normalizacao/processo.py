"""Normalização do número de processo, padrão CNJ (Fase 3).

Problemas reais encontrados (especificação): pontos no lugar de hífens,
espaços e tabs no início, dígito faltando.

Tratamento: chave de comparação = só os dígitos (usada pela deduplicação
por CNJ entre Contrárias e Procon — ver secoes/contrarias.py, Fase 4). Com
20 dígitos, reformata no padrão CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO — 7+2+4+1+2+4).
Diferente de 20 dígitos: mantém o texto original e gera aviso (não tenta
adivinhar o que falta)."""
from __future__ import annotations

import re
from dataclasses import dataclass

_NAO_DIGITO = re.compile(r"\D")


@dataclass
class ProcessoNormalizado:
    chave_comparacao: str  # só dígitos — "" quando não há nenhum
    valor: str  # formatado no padrão CNJ se tiver 20 dígitos, senão o original
    aviso: str | None = None


def normalizar(bruto: object) -> ProcessoNormalizado:
    if bruto is None:
        return ProcessoNormalizado("", "", "número de processo vazio")

    texto_original = str(bruto).strip()
    digitos = _NAO_DIGITO.sub("", texto_original)

    if not digitos:
        return ProcessoNormalizado("", texto_original, "número de processo vazio")

    if len(digitos) == 20:
        formatado = (
            f"{digitos[0:7]}-{digitos[7:9]}.{digitos[9:13]}.{digitos[13:14]}.{digitos[14:16]}.{digitos[16:20]}"
        )
        return ProcessoNormalizado(digitos, formatado)

    return ProcessoNormalizado(
        digitos, texto_original, f"número de processo com {len(digitos)} dígito(s) (esperado 20): '{texto_original}'"
    )
