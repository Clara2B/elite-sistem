"""Normalização de texto livre — nomes de pessoas e UF (Fase 3).

Nomes de pessoas (especificação): tabs e espaços no início, caixa alta e
baixa misturadas. Tratamento: remove espaços extras; mantém a grafia
original (sem mudar caixa) — diferente da normalização ESTRUTURAL usada
pra comparar nome de coluna/aba/assessoria (`app.utils.normalize`, usada
direto por `leitores/base.py` e `normalizacao/assessoria.py`), que ignora
acento e caixa pra fins de COMPARAÇÃO, não de exibição.

UF (especificação): vazia, minúscula. Tratamento: maiúscula; valida contra
as 27 UFs; inválida vira aviso e fica fora do mapa (Fase 6)."""
from __future__ import annotations

from dataclasses import dataclass

UFS = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
})  # pública — reaproveitada por mapas.py (Fase 6) pra garantir as 27 UFs na tabela


@dataclass
class NomeNormalizado:
    valor: str
    aviso: str | None = None


@dataclass
class UfNormalizada:
    valor: str | None
    aviso: str | None = None


def normalizar_nome(bruto: object) -> NomeNormalizado:
    if bruto is None:
        return NomeNormalizado("", "nome vazio")
    texto = " ".join(str(bruto).split())
    if not texto:
        return NomeNormalizado("", "nome vazio")
    return NomeNormalizado(texto)


def normalizar_uf(bruto: object) -> UfNormalizada:
    if bruto is None:
        return UfNormalizada(None, "UF vazia")
    texto = str(bruto).strip().upper()
    if not texto:
        return UfNormalizada(None, "UF vazia")
    if texto not in UFS:
        return UfNormalizada(None, f"UF inválida: '{texto}'")
    return UfNormalizada(texto)
