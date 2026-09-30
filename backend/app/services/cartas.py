"""Cartas-convite em PDF (Fase Cartas, 2026-09-25) — Carta Convite Cliente e
Carta Convite Banco. Sem persistência: cada geração é validada e montada
aqui, e vira PDF direto em app/pdf_export.py — nada é salvo no banco."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_RE_MEET = re.compile(r"^(https?://)?meet\.google\.com/", re.IGNORECASE)
_RE_TEAMS = re.compile(r"^(https?://)?teams\.microsoft\.com/", re.IGNORECASE)
_RE_SOMENTE_DIGITOS = re.compile(r"\D")


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
    digitos = _RE_SOMENTE_DIGITOS.sub("", cpf or "")
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
    d = _RE_SOMENTE_DIGITOS.sub("", cpf)
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def cnpj_valido(cnpj: str) -> bool:
    """Valida os dígitos verificadores do CNPJ (2026-09-30, a pedido da
    Clara: o campo "CPF" da Carta Banco precisa aceitar também CNPJ, pro
    titular da unidade poder ser pessoa jurídica)."""
    digitos = _RE_SOMENTE_DIGITOS.sub("", cnpj or "")
    if len(digitos) != 14 or digitos == digitos[0] * 14:
        return False

    def _digito_verificador(parcial: str, pesos: list[int]) -> str:
        soma = sum(int(d) * peso for d, peso in zip(parcial, pesos, strict=True))
        resto = soma % 11
        return str(0 if resto < 2 else 11 - resto)

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _digito_verificador(digitos[:12], pesos1)
    d2 = _digito_verificador(digitos[:12] + d1, pesos2)
    return digitos[-2:] == d1 + d2


def formatar_cnpj(cnpj: str) -> str:
    """Normaliza pro formato "00.000.000/0000-00" — só é chamada depois de
    `cnpj_valido` confirmar 14 dígitos."""
    d = _RE_SOMENTE_DIGITOS.sub("", cnpj)
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def identificar_documento(valor: str) -> tuple[str, str]:
    """Identifica se `valor` é um CPF (11 dígitos) ou CNPJ (14 dígitos) e
    devolve (rótulo, formatado) — ex.: ("CPF", "529.982.247-25") ou
    ("CNPJ", "11.222.333/0001-81"). ValueError com mensagem clara se não for
    nenhum dos dois, ou se os dígitos verificadores não baterem (2026-09-30,
    a pedido da Clara)."""
    digitos = _RE_SOMENTE_DIGITOS.sub("", valor or "")
    if len(digitos) == 11:
        if not cpf_valido(valor):
            raise ValueError(f'CPF inválido: "{valor.strip()}" — confira os dígitos e tente novamente.')
        return "CPF", formatar_cpf(valor)
    if len(digitos) == 14:
        if not cnpj_valido(valor):
            raise ValueError(f'CNPJ inválido: "{valor.strip()}" — confira os dígitos e tente novamente.')
        return "CNPJ", formatar_cnpj(valor)
    raise ValueError(
        f'CPF/CNPJ inválido: "{valor.strip()}" — informe um CPF (11 dígitos) ou um CNPJ '
        "(14 dígitos) válido."
    )


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
    documento: str
    tipo_documento: str
    contrato: str
    data: date
    hora: str
    link: str
    plataforma: str


def formatar_texto_carta_cliente(convite: ConviteCliente) -> str:
    """Mesmo conteúdo da Carta Convite Cliente em PDF (ver
    pdf_export.py::gerar_pdf_carta_cliente), em texto puro pra copiar e
    colar (2026-09-29, a pedido da Clara) — cada parágrafo do PDF vira um
    bloco separado por linha em branco, na mesma ordem."""
    paragrafos = [
        "Pré-Processual",
        "Métodos Consensuais de Solução de Conflitos",
        "Convite para Audiência Extrajudicial Administrativa – Ação Revisional",
        f"AUTOR: {convite.autor}\nREU: {convite.reu},",
        (
            "Pela presente, solicitamos o seu comparecimento a participar de "
            "AUDIÊNCIA EXTRAJUDICIAL ADMINISTRATIVA, a ser realizada com a "
            "finalidade de tentativa de composição amigável"
        ),
        (
            "A audiência de Tentativa de Conciliação está sugerida para o dia "
            f'{convite.dia.strftime("%d/%m/%Y")}, às {convite.hora}, '
            "a ser realizada na modalidade Virtual, podendo haver ajustes, mediante prévio contato."
        ),
        "NÃO ESQUECER DO DOCUMENTO COM FOTO",
        (
            "É OBRIGATÓRIO A PRESENÇA DO TITULAR DO CONTRATO, NÃO SERÁ PERMITIDO A "
            "ENTRADA DE TERCEIROS EM AUDIÊNCIA SEM A PROCURAÇÃO PÚBLICA"
        ),
        "A ENTRADA DE TERCEIROS SEM A PROCURAÇÃO A AUDIÊNCIA SERÁ CANCELADA",
        f"(Segue link abaixo, pela plataforma {convite.plataforma.upper()})\n{convite.link}",
        (
            "Colocamo-nos à disposição por meio dos contatos:\n"
            "E-mail: conciliacao@camaraeximia.com\n"
            "Telefone: 55 11 93234-6989"
        ),
        "Certos da atenção e colaboração, renovamos votos de elevada estima e consideração.",
        "Atenciosamente,",
        "Eximia Câmara de Mediação Conciliação e Arbitragem.",
    ]
    return "\n\n".join(paragrafos)


def montar_convite_banco(
    banco_nome: str, banco_cnpj: str, nome: str, cpf: str, contrato: str,
    data: date, hora: str, link: str,
) -> ConviteBanco:
    tipo_documento, documento = identificar_documento(cpf)
    plataforma = detectar_plataforma(link)
    return ConviteBanco(
        banco_nome=banco_nome.strip().upper(),
        banco_cnpj=banco_cnpj.strip(),
        nome=nome.strip().upper(),
        documento=documento,
        tipo_documento=tipo_documento,
        contrato=contrato.strip(),
        data=data,
        hora=formatar_hora(hora),
        link=link.strip(),
        plataforma=plataforma,
    )


def formatar_texto_carta_banco(convite: ConviteBanco) -> str:
    """Mesmo conteúdo da Carta Convite Banco em PDF (ver
    pdf_export.py::gerar_pdf_carta_banco), em texto puro pra copiar e
    colar (2026-09-29, a pedido da Clara)."""
    paragrafos = [
        "Convite para Audiência Extrajudicial Administrativa – Ação Revisional",
        "Ao",
        f"{convite.banco_nome} – CNPJ: {convite.banco_cnpj},",
        "Prezados Senhores,",
        (
            f"Por meio da presente, o(a) Sr.(a) {convite.nome}, inscrito(a) no "
            f"{convite.tipo_documento}: {convite.documento}, titular da unidade de n° {convite.contrato}, "
            "vem, respeitosamente, CONVIDAR essa instituição financeira para participar de "
            "AUDIÊNCIA EXTRAJUDICIAL ADMINISTRATIVA, a ser realizada com a finalidade "
            "de tentativa de composição amigável."
        ),
        (
            "Esclarece-se que, encontra-se em nosso escritório o contrato de financiamento do "
            "Reclamante, acima citado, cujo objetivo consiste na revisão de cláusulas "
            "contratuais reputadas abusivas, notadamente quanto a juros, encargos, "
            "capitalização, tarifas etc."
        ),
        (
            "Não obstante, antes da judicialização da demanda, a parte Reclamante demonstra "
            "pleno interesse na solução consensual, em consonância com os princípios da "
            "boa-fé objetiva, da cooperação e da autocomposição, motivo pelo qual propõe a "
            "realização da referida audiência extrajudicial."
        ),
        (
            f'A audiência está sugerida para o dia {convite.data.strftime("%d/%m/%Y")}, às '
            f"{convite.hora}, a ser realizada na modalidade Virtual, podendo haver ajustes, "
            "mediante prévio contato."
        ),
        convite.link,
        (
            "A Audiência de Tentativa de Conciliação será realizada de forma virtual, através "
            f"do aplicativo {convite.plataforma.upper()}."
        ),
        (
            "Solicita-se, desde já, que essa Instituição indique representante com poderes "
            "para negociar e transigir, a fim de possibilitar a efetiva resolução do "
            "conflito."
        ),
        "Colocamo-nos à disposição por meio do e-mail: conciliacao@camaraeximia.com.",
        "Certos da atenção e colaboração, renovamos votos de elevada estima e consideração.",
        "Atenciosamente,",
        "EXÍMIA CÂMARA DE CONCILIAÇÃO, MEDIAÇÃO E ARBITRAGEM",
    ]
    return "\n\n".join(paragrafos)
