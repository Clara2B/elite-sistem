"""Cartas-convite em PDF (Fase Cartas, 2026-09-25) — Carta Convite Cliente e
Carta Convite Banco. Sem persistência: cada geração é validada e montada
aqui, e vira PDF direto em app/pdf_export.py — nada é salvo no banco."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_RE_MEET = re.compile(r"^(https?://)?meet\.google\.com/", re.IGNORECASE)
_RE_TEAMS = re.compile(r"^(https?://)?teams\.microsoft\.com/", re.IGNORECASE)
_RE_CPF_DIGITOS = re.compile(r"\D")


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


def cpf_valido(cpf: str) -> bool:
    """Valida os dígitos verificadores do CPF (Clara, 2026-09-25: CPF
    inválido bloqueia a geração da Carta Banco, com aviso do motivo)."""
    digitos = _RE_CPF_DIGITOS.sub("", cpf or "")
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False

    def _digito_verificador(parcial: str) -> str:
        soma = sum(int(d) * peso for d, peso in zip(parcial, range(len(parcial) + 1, 1, -1), strict=True))
        resto = (soma * 10) % 11
        return str(resto if resto < 10 else 0)

    d1 = _digito_verificador(digitos[:9])
    d2 = _digito_verificador(digitos[:9] + d1)
    return digitos[-2:] == d1 + d2


def formatar_cpf(cpf: str) -> str:
    """Normaliza pro formato "000.000.000-00" no PDF, não importa como foi
    digitado — só é chamada depois de `cpf_valido` confirmar 11 dígitos."""
    d = _RE_CPF_DIGITOS.sub("", cpf)
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


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


@dataclass
class ConviteBanco:
    banco_nome: str
    banco_cnpj: str
    nome: str
    cpf: str
    contrato: str
    data: date
    hora: str
    link: str
    plataforma: str


def montar_convite_banco(
    banco_nome: str, banco_cnpj: str, nome: str, cpf: str, contrato: str,
    data: date, hora: str, link: str,
) -> ConviteBanco:
    if not cpf_valido(cpf):
        raise ValueError(f'CPF inválido: "{cpf.strip()}" — confira os dígitos e tente novamente.')
    plataforma = detectar_plataforma(link)
    return ConviteBanco(
        banco_nome=banco_nome.strip().upper(),
        banco_cnpj=banco_cnpj.strip(),
        nome=nome.strip().upper(),
        cpf=formatar_cpf(cpf),
        contrato=contrato.strip(),
        data=data,
        hora=formatar_hora(hora),
        link=link.strip(),
        plataforma=plataforma,
    )
