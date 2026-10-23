"""Gera e envia as duas Cartas Convite (Cliente/Banco) de uma
`SolicitacaoAudiencia` (Fase 1 — Solicitação de Audiência, 2026-10-16) —
reaproveita app/services/cartas.py (texto/HTML, nenhuma regra duplicada) e
app/pdf_export.py (PDF anexado, a pedido da Clara: "corpo e pdf").

Dois e-mails separados (cliente e banco), mesmo assunto nos dois
(confirmado pela Clara), corpo = texto da carta correspondente, com o
logotipo embutido inline (Content-ID) só no e-mail de verdade — a
pré-visualização em tela (`montar_previas`) não tem como resolver um
`cid:`, então fica sem a imagem."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Banco, EnvioEmail, SolicitacaoAudiencia, Usuario
from app.pdf_export import gerar_pdf_carta_banco, gerar_pdf_carta_cliente
from app.services import email_resend, google_sheets
from app.services.cartas import (
    ConviteBanco,
    ConviteCliente,
    formatar_html_carta_banco,
    formatar_html_carta_cliente,
    formatar_texto_carta_banco,
    formatar_texto_carta_cliente,
    montar_assunto_email,
    montar_convite_banco,
    montar_convite_cliente,
)
from app.services.solicitacoes_audiencia import ABA_AGENDAMENTO
from app.utils import nome_arquivo_pdf

_logger = logging.getLogger("elite_sistem.email")
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "audiencias_logo_0.jpeg"
_LOGO_CID = "logo-carta"


@dataclass
class PreviaEmail:
    destinatarios: list[str]
    assunto: str
    corpo_html: str
    corpo_texto: str


@dataclass
class PreviaEmails:
    cliente: PreviaEmail
    banco: PreviaEmail


def _montar_convites(db: Session, solicitacao: SolicitacaoAudiencia) -> tuple[ConviteCliente, ConviteBanco]:
    banco = db.get(Banco, solicitacao.banco_id)
    hora = solicitacao.hora_agendamento
    convite_cliente = montar_convite_cliente(
        solicitacao.nome_cliente, banco.nome, solicitacao.data_agendamento, hora, solicitacao.link_audiencia,
    )
    # Qual CNPJ usar na carta — escolhido na tela quando o banco tem um
    # 2° CNPJ cadastrado (ver reservar_horario); sem alternativo, usa
    # sempre o principal, igual ao comportamento de antes dessa opção
    # existir.
    cnpj = banco.cnpj_alternativo if (solicitacao.usar_cnpj_alternativo and banco.cnpj_alternativo) else banco.cnpj
    # O CPF já foi validado e formatado na reserva (reservar_horario) — mas
    # `montar_convite_banco` espera o valor cru pra rodar `identificar_documento`
    # de novo, então passa normal, ele reconhece CPF formatado sem problema.
    convite_banco = montar_convite_banco(
        banco.nome, cnpj, solicitacao.nome_cliente, solicitacao.cpf_cliente, solicitacao.numero_contrato,
        solicitacao.data_agendamento, hora, solicitacao.link_audiencia,
    )
    return convite_cliente, convite_banco


def _destinatarios_banco(banco: Banco) -> list[str]:
    """O e-mail do banco pode ter vários endereços separados por ";" na
    planilha real (jurídico + ouvidoria, por exemplo) — manda pra todos
    (confirmado pela Clara)."""
    return [e.strip() for e in banco.email.split(";") if e.strip()]


def montar_previas(db: Session, solicitacao: SolicitacaoAudiencia) -> PreviaEmails:
    """Só monta o conteúdo — nada é enviado. Usada pela tela de prévia
    antes do clique em "Enviar" (a pedido explícito da Clara)."""
    convite_cliente, convite_banco = _montar_convites(db, solicitacao)
    banco = db.get(Banco, solicitacao.banco_id)
    assunto = montar_assunto_email(
        solicitacao.data_agendamento, solicitacao.hora_agendamento, solicitacao.nome_cliente,
    )
    return PreviaEmails(
        cliente=PreviaEmail(
            destinatarios=[solicitacao.email_cliente],
            assunto=assunto,
            corpo_html=formatar_html_carta_cliente(convite_cliente),
            corpo_texto=formatar_texto_carta_cliente(convite_cliente),
        ),
        banco=PreviaEmail(
            destinatarios=_destinatarios_banco(banco),
            assunto=assunto,
            corpo_html=formatar_html_carta_banco(convite_banco),
            corpo_texto=formatar_texto_carta_banco(convite_banco),
        ),
    )


@dataclass
class ResultadoEnvio:
    cliente_enviado: bool
    cliente_erro: str | None
    banco_enviado: bool
    banco_erro: str | None


def _registrar_envio(
    db: Session, usuario: Usuario, solicitacao: SolicitacaoAudiencia, tipo: str,
    destinatarios: list[str], assunto: str, status: str, erro: str | None,
) -> None:
    db.add(EnvioEmail(
        solicitacao_id=solicitacao.id, tipo=tipo, destinatarios="; ".join(destinatarios),
        assunto=assunto, status=status, erro=erro, enviado_por=usuario.id,
    ))
    db.commit()


def _enviar_uma_carta(
    db: Session, usuario: Usuario, solicitacao: SolicitacaoAudiencia, tipo: str,
    destinatarios: list[str], assunto: str, corpo_html: str, corpo_texto: str,
    anexos: list[tuple[str, bytes, str]], imagens_inline: list[tuple[str, bytes, str]] | None,
) -> tuple[bool, str | None]:
    try:
        email_resend.enviar_email(destinatarios, assunto, corpo_html, corpo_texto, anexos, imagens_inline)
    except email_resend.ErroEnvioEmail as e:
        _registrar_envio(db, usuario, solicitacao, tipo, destinatarios, assunto, "ERRO", str(e))
        return False, str(e)
    _registrar_envio(db, usuario, solicitacao, tipo, destinatarios, assunto, "ENVIADO", None)
    return True, None


def enviar_emails(
    db: Session, usuario: Usuario, solicitacao: SolicitacaoAudiencia, spreadsheet_id: str | None = None,
) -> ResultadoEnvio:
    """Gera as duas cartas (texto + HTML + PDF anexado) e envia os dois
    e-mails, registrando cada um em `EnvioEmail` (sucesso ou erro — uma
    falha nunca impede a tentativa da outra carta). Em caso de falha, não
    marca como concluído: a tela permite tentar de novo, e cada tentativa
    grava uma linha nova aqui (histórico completo, nunca sobrescrito).

    Quando os dois são enviados com sucesso e `spreadsheet_id` é passado,
    marca NOTIFICAÇÃO = "CLIENTE E BANCO" na planilha de controle — mesmo
    valor que o time já preenche à mão hoje (confirmado pela Clara: "o
    mais prático por enquanto"). Em caso de falha parcial, a coluna fica
    como estava, sinalizando que ainda falta alguma notificação."""
    convite_cliente, convite_banco = _montar_convites(db, solicitacao)
    banco = db.get(Banco, solicitacao.banco_id)
    assunto = montar_assunto_email(
        solicitacao.data_agendamento, solicitacao.hora_agendamento, solicitacao.nome_cliente,
    )

    logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.exists() else None
    imagens_inline = [(_LOGO_CID, logo_bytes, "image/jpeg")] if logo_bytes else None
    logo_cid = _LOGO_CID if imagens_inline else None

    pdf_cliente = gerar_pdf_carta_cliente(convite_cliente)
    pdf_banco = gerar_pdf_carta_banco(convite_banco)

    cliente_enviado, cliente_erro = _enviar_uma_carta(
        db, usuario, solicitacao, "CLIENTE", [solicitacao.email_cliente], assunto,
        formatar_html_carta_cliente(convite_cliente, logo_cid=logo_cid),
        formatar_texto_carta_cliente(convite_cliente),
        [(nome_arquivo_pdf("Carta_Convite_Cliente", convite_cliente.autor), pdf_cliente, "application/pdf")],
        imagens_inline,
    )
    banco_enviado, banco_erro = _enviar_uma_carta(
        db, usuario, solicitacao, "BANCO", _destinatarios_banco(banco), assunto,
        formatar_html_carta_banco(convite_banco, logo_cid=logo_cid),
        formatar_texto_carta_banco(convite_banco),
        [(nome_arquivo_pdf("Carta_Convite_Banco", convite_banco.nome), pdf_banco, "application/pdf")],
        imagens_inline,
    )

    if cliente_enviado and banco_enviado:
        solicitacao.status = "EMAILS_ENVIADOS"
        db.commit()
        if spreadsheet_id:
            try:
                google_sheets.escrever_valores(
                    spreadsheet_id, ABA_AGENDAMENTO, solicitacao.linha_planilha, {"NOTIFICAÇÃO": "CLIENTE E BANCO"},
                )
            except Exception:
                # Os dois e-mails já saíram com sucesso — uma falha aqui
                # (ex.: rede, credencial revogada) é só um registro
                # informativo perdido na planilha, não pode fazer o
                # usuário achar que o envio inteiro falhou.
                _logger.warning(
                    "Não foi possível marcar NOTIFICAÇÃO na planilha (linha %s) — "
                    "os e-mails já foram enviados com sucesso.", solicitacao.linha_planilha, exc_info=True,
                )

    return ResultadoEnvio(cliente_enviado, cliente_erro, banco_enviado, banco_erro)
