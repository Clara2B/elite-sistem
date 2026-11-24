"""Normalização do número de processo, padrão CNJ (Fase 3) — usada por
Contrárias, cujo "Nº DO PROCESSO" é sempre um processo judicial de
verdade.

Problemas reais encontrados (especificação): pontos no lugar de hífens,
espaços e tabs no início, dígito faltando.

Tratamento: chave de comparação = só os dígitos (usada pela deduplicação
dentro de Contrárias — ver secoes/contrarias.py, Fase 4). Com 20 dígitos,
reformata no padrão CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO — 7+2+4+1+2+4).
Diferente de 20 dígitos: mantém o texto original e gera aviso (não tenta
adivinhar o que falta).

Procons usa `normalizar_protocolo_administrativo` abaixo, não esta função
— o "Nº DO PROCESSO" de Procon/MP/Extrajudicial é um protocolo
administrativo (formatos variados, ex. "0470905/2025", ou até texto livre
como "XERIFE DO CONSUMIDOR"), não um processo judicial CNJ: aplicar a
validação de 20 dígitos aqui gerava um aviso falso pra praticamente toda
linha de Procon (bug real encontrado em planilha de produção, 2026-10-27)."""
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


def normalizar_protocolo_administrativo(bruto: object) -> ProcessoNormalizado:
    """Protocolo administrativo (Procon/MP/Extrajudicial): formato livre,
    sem quantidade fixa de dígitos — só avisa quando está vazio, nunca por
    "tamanho errado". `chave_comparacao` continua só os dígitos, pra
    deduplicação (ex.: "0470905/2025" e "0470905 / 2025" contam como o
    mesmo protocolo)."""
    if bruto is None:
        return ProcessoNormalizado("", "", "número de processo vazio")

    texto_original = str(bruto).strip()
    if not texto_original:
        return ProcessoNormalizado("", texto_original, "número de processo vazio")

    digitos = _NAO_DIGITO.sub("", texto_original)
    return ProcessoNormalizado(digitos, texto_original)
