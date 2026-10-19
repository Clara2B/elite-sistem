"""Nova Solicitação de Audiência (Fase 1, 2026-10-16, a pedido da Clara) —
encontra o próximo horário vago na planilha de controle (aba AGENDAMENTO) e
grava a solicitação nela, sem digitar os mesmos dados de novo em três
lugares (planilha, Cartas, e-mails).

Travamento otimista: o próximo horário é só uma PRÉVIA (nada é reservado
nesse momento). A reserva de verdade acontece no instante da confirmação,
em duas camadas — `reservar_horario` grava uma linha nova em
`solicitacoes_audiencia` com `linha_planilha` UNIQUE (SQLite/Postgres
recusam a segunda reserva da mesma linha, não importa a ordem exata de
chegada das requisições concorrentes); só depois disso `confirmar_na_planilha`
relê a linha de verdade na planilha e grava, cobrindo o caso de alguém ter
editado a planilha direto, por fora deste sistema. As duas falhas de
corrida (perdeu a reserva no banco, ou a linha não estava mais vaga na
planilha) viram a mesma `HorarioJaOcupado` — quem chama decide buscar o
próximo horário disponível e mostrar de novo pro usuário."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")

from app.models import Banco, EmpresaCliente, SolicitacaoAudiencia, Usuario
from app.services import google_sheets
from app.services.cartas import cpf_valido, formatar_cpf

ABA_AGENDAMENTO = "AGENDAMENTO"

# Confirmado pela Clara (2026-10-16): só esses 7 campos precisam estar
# vazios pra linha contar como vaga — não inclui BANCO de propósito (uma
# linha com BANCO preenchido mas o resto vazio ainda seria vaga, embora
# isso não apareça nos dados reais). Linhas "EXTRA" (NOME COMPLETO
# literalmente "EXTRA") ficam de fora naturalmente, já que NOME COMPLETO
# não está vazio nessas.
CAMPOS_VAZIOS_PARA_VAGA = [
    "DATA DE RECEBIMENTO", "EMPRESA", "NOME COMPLETO", "LINK", "CPF", "E-MAIL", "TELEFONE",
]

_RE_DATA_AGENDAMENTO = re.compile(
    r"^(?P<dia>\d{2})/(?P<mes>\d{2})/(?P<ano>\d{4})\s*-\s*(?P<hora>\d{2})[:;](?P<minuto>\d{2})$"
)
_RE_SOMENTE_DIGITOS = re.compile(r"\D")
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class HorarioJaOcupado(ValueError):
    """A vaga que a prévia mostrou não está mais livre (alguém reservou
    primeiro, no banco ou direto na planilha) — quem chama deve buscar o
    próximo horário disponível e mostrar de novo."""


def parse_data_agendamento(texto: str) -> tuple[date, str] | None:
    """"30/06/2026 - 14:00" -> (date(2026,6,30), "14:00"). Tolerante ao
    separador de hora vir com ";" em vez de ":" (erro de digitação visto
    na planilha real, pelo menos uma linha) — `None` pra qualquer formato
    não reconhecido, nunca levanta exceção (linha é só ignorada na busca,
    não trava o sistema inteiro)."""
    m = _RE_DATA_AGENDAMENTO.match((texto or "").strip())
    if not m:
        return None
    try:
        dia = date(int(m["ano"]), int(m["mes"]), int(m["dia"]))
    except ValueError:
        return None
    hora, minuto = m["hora"], m["minuto"]
    if not (0 <= int(hora) <= 23 and 0 <= int(minuto) <= 59):
        return None
    return dia, f"{hora}:{minuto}"


def formatar_data_agendamento(dia: date, hora: str) -> str:
    """Sempre nesse formato na escrita (a pedido da Clara), mesmo que a
    leitura tenha aceitado uma variação (ex.: ";" em vez de ":")."""
    return f"{dia.strftime('%d/%m/%Y')} - {hora}"


def telefone_valido(telefone: str) -> bool:
    """Validação frouxa de propósito: a planilha real tem telefones em
    formatos bem variados (com/sem DDD, com/sem separador) — só confere
    10 ou 11 dígitos (DDD + fixo de 8 ou celular de 9)."""
    digitos = _RE_SOMENTE_DIGITOS.sub("", telefone or "")
    return len(digitos) in (10, 11)


def email_valido(email: str) -> bool:
    return bool(_RE_EMAIL.match((email or "").strip()))


def _linha_ainda_vaga(linha: dict[str, str]) -> bool:
    return all(not google_sheets.valor_coluna(linha, campo) for campo in CAMPOS_VAZIOS_PARA_VAGA)


@dataclass
class HorarioVago:
    numero_linha: int
    dia: date
    hora: str


def agora_brasil() -> datetime:
    """"Agora" no horário de Brasília, sem tzinfo (pra comparar direto com
    as datas/horas, sempre naive, lidas da planilha) — não dá pra usar
    `datetime.utcnow()`/`datetime.now()` puro aqui: o servidor (Render)
    roda em UTC, e a planilha é preenchida no horário local de quem
    agenda a audiência. Perto da meia-noite, a diferença de fuso é o
    bastante pra considerar uma vaga de hoje à noite como "passada" por
    engano, ou vice-versa."""
    return datetime.now(_FUSO_BRASIL).replace(tzinfo=None)


def encontrar_proximo_horario_vago(spreadsheet_id: str, agora: datetime) -> HorarioVago | None:
    """Primeira linha, na ordem da planilha, com DATA DE AGENDAMENTO
    preenchida e reconhecível, data/hora futura (sem antecedência mínima —
    confirmado pela Clara) e todos os `CAMPOS_VAZIOS_PARA_VAGA` vazios.
    `None` se não encontrar nenhuma."""
    linhas = google_sheets.ler_aba_com_numero_linha(spreadsheet_id, ABA_AGENDAMENTO)
    for numero_linha, linha in linhas:
        texto_agendamento = google_sheets.valor_coluna(linha, "DATA DE AGENDAMENTO")
        parseado = parse_data_agendamento(texto_agendamento)
        if parseado is None:
            continue
        dia, hora = parseado
        hora_int, minuto_int = (int(p) for p in hora.split(":"))
        if datetime.combine(dia, time(hora_int, minuto_int)) <= agora:
            continue
        if not _linha_ainda_vaga(linha):
            continue
        return HorarioVago(numero_linha=numero_linha, dia=dia, hora=hora)
    return None


def reservar_horario(
    db: Session,
    usuario: Usuario,
    empresa_cliente_id: int,
    nome_cliente: str,
    cpf_cliente: str,
    email_cliente: str,
    telefone_cliente: str,
    data_recebimento: date,
    numero_contrato: str,
    banco_id: int,
    link_audiencia: str,
    horario: HorarioVago,
    usar_cnpj_alternativo: bool = False,
) -> SolicitacaoAudiencia:
    """Primeira camada do travamento otimista: grava a reserva no próprio
    banco, com `linha_planilha` UNIQUE. Se outra requisição já reservou a
    mesma linha entre a busca e esta chamada, o commit falha com
    `IntegrityError` — convertida em `HorarioJaOcupado` pra quem chama
    buscar a próxima vaga.

    `usar_cnpj_alternativo` (2026-10-19, a pedido da Clara) escolhe qual
    CNPJ do banco a Carta Banco vai usar — só faz sentido quando o banco
    tem um `cnpj_alternativo` cadastrado."""
    if not cpf_valido(cpf_cliente):
        raise ValueError(f"CPF '{cpf_cliente}' inválido.")
    if not email_valido(email_cliente):
        raise ValueError(f"E-mail '{email_cliente}' inválido.")
    if not telefone_valido(telefone_cliente):
        raise ValueError(f"Telefone '{telefone_cliente}' inválido.")
    banco = db.get(Banco, banco_id)
    if banco is None:
        raise ValueError("Banco não encontrado.")
    if usar_cnpj_alternativo and not banco.cnpj_alternativo:
        raise ValueError(f"O banco {banco.nome} não tem um 2° CNPJ cadastrado.")

    solicitacao = SolicitacaoAudiencia(
        empresa_cliente_id=empresa_cliente_id,
        nome_cliente=nome_cliente.strip(),
        cpf_cliente=formatar_cpf(cpf_cliente),
        email_cliente=email_cliente.strip(),
        telefone_cliente=telefone_cliente.strip(),
        data_recebimento=data_recebimento,
        numero_contrato=numero_contrato.strip(),
        banco_id=banco_id,
        usar_cnpj_alternativo=usar_cnpj_alternativo,
        link_audiencia=link_audiencia.strip(),
        linha_planilha=horario.numero_linha,
        data_agendamento=horario.dia,
        hora_agendamento=horario.hora,
        status="RESERVADA",
        criado_por=usuario.id,
    )
    db.add(solicitacao)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HorarioJaOcupado(
            f"O horário de {horario.dia.strftime('%d/%m/%Y')} às {horario.hora} acabou de ser "
            "reservado por outra solicitação."
        ) from e
    return solicitacao


def confirmar_na_planilha(db: Session, spreadsheet_id: str, solicitacao: SolicitacaoAudiencia) -> SolicitacaoAudiencia:
    """Segunda camada: relê a linha de verdade na planilha (cobre alguém
    ter editado ela direto, por fora deste sistema) e só então grava —
    nunca toca em nenhuma outra coluna da mesma linha (CONCILIADORA/
    ADVOGADA pré-atribuídas continuam como estavam) nem em nenhuma outra
    linha."""
    linha_atual = google_sheets.ler_linha(spreadsheet_id, ABA_AGENDAMENTO, solicitacao.linha_planilha)
    if not _linha_ainda_vaga(linha_atual):
        solicitacao.status = "FALHOU"
        db.commit()
        raise HorarioJaOcupado(
            f"O horário de {solicitacao.data_agendamento.strftime('%d/%m/%Y')} às "
            f"{solicitacao.hora_agendamento} não está mais vago na planilha."
        )

    empresa = db.get(EmpresaCliente, solicitacao.empresa_cliente_id)
    banco = db.get(Banco, solicitacao.banco_id)
    google_sheets.escrever_valores(
        spreadsheet_id, ABA_AGENDAMENTO, solicitacao.linha_planilha,
        {
            "DATA DE RECEBIMENTO": solicitacao.data_recebimento.strftime("%d/%m/%Y"),
            "EMPRESA": empresa.nome,
            "NOME COMPLETO": solicitacao.nome_cliente,
            "LINK": solicitacao.link_audiencia,
            "CPF": solicitacao.cpf_cliente,
            "E-MAIL": solicitacao.email_cliente,
            "TELEFONE": solicitacao.telefone_cliente,
            "BANCO": banco.nome,
        },
    )
    solicitacao.status = "GRAVADA"
    db.commit()
    return solicitacao
