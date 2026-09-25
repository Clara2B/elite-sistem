"""Cartas-convite em PDF (Fase Cartas, 2026-09-25) — Carta Convite Cliente
primeiro; Carta Convite Banco entra depois de aprovação (ver DECISIONS.md).
Sem persistência: cada geração é validada e montada aqui, e vira PDF direto
em app/pdf_export.py — nada é salvo no banco."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_RE_MEET = re.compile(r"^(https?://)?meet\.google\.com/", re.IGNORECASE)
_RE_TEAMS = re.compile(r"^(https?://)?teams\.microsoft\.com/", re.IGNORECASE)


def detectar_plataforma(link: str) -> str:
    """"Google Meet" ou "Teams" a partir do link informado (com ou sem
    "https://"); ValueError com mensagem clara se não for nenhum dos dois
    (Clara, 2026-09-25 — a carta não tem o que escrever em "pela plataforma
    ___" sem reconhecer o link)."""
    link_limpo = (link or "").strip()
    if _RE_MEET.match(link_limpo):
        return "Google Meet"
    if _RE_TEAMS.match(link_limpo):
        return "Teams"
    raise ValueError(
        "Link da audiência inválido — informe um link do Google Meet "
        "(meet.google.com/...) ou do Microsoft Teams (teams.microsoft.com/...)."
    )


def formatar_hora(hora: str) -> str:
    """"14:05" -> "14H05" (Clara, 2026-09-25: sem "m" no final)."""
    h, m = hora.split(":")
    return f"{h}H{m}"


def href_absoluto(link: str) -> str:
    """Garante um link clicável no PDF mesmo quando digitado sem "https://"."""
    link_limpo = link.strip()
    return link_limpo if link_limpo.startswith(("http://", "https://")) else f"https://{link_limpo}"


@dataclass
class ConviteCliente:
    autor: str
    reu: str
    dia: date
    hora: str
    link: str
    plataforma: str


def montar_convite_cliente(autor: str, reu: str, dia: date, hora: str, link: str) -> ConviteCliente:
    plataforma = detectar_plataforma(link)
    return ConviteCliente(
        autor=autor.strip().upper(),
        reu=reu.strip().upper(),
        dia=dia,
        hora=formatar_hora(hora),
        link=link.strip(),
        plataforma=plataforma,
    )
