"""Chamados de suporte (2026-09-28, a pedido da Clara) — o pop-up flutuante
(ver templates/base.html) manda o chamado pra cá, que envia por SMTP direto
(smtplib, sem serviço terceiro) pro e-mail de suporte. Sem as variáveis de
ambiente de e-mail configuradas (SMTP_HOST/SMTP_USUARIO/SMTP_SENHA), o envio
recusa com uma mensagem amigável em vez de estourar um erro genérico."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings
from app.models import Usuario


def enviar_chamado(usuario: Usuario, assunto: str, descricao: str) -> None:
    if not settings.smtp_host or not settings.smtp_usuario or not settings.smtp_senha:
        raise ValueError(
            "O envio de chamados ainda não está configurado neste sistema "
            "(faltam as variáveis de e-mail). Avise o administrador."
        )

    remetente = settings.smtp_remetente or settings.smtp_usuario
    mensagem = EmailMessage()
    mensagem["Subject"] = f"[Elite Sistem] {assunto}"
    mensagem["From"] = remetente
    mensagem["To"] = settings.smtp_destinatario_suporte
    mensagem["Reply-To"] = usuario.email
    mensagem.set_content(
        f"Chamado aberto por {usuario.nome} ({usuario.email}) no Elite Sistem.\n\n{descricao}"
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_porta, timeout=15) as servidor:
            servidor.starttls()
            servidor.login(settings.smtp_usuario, settings.smtp_senha)
            servidor.send_message(mensagem)
    except (smtplib.SMTPException, OSError) as e:
        raise ValueError(f"Não foi possível enviar o chamado agora ({e}). Tente de novo em instantes.") from e
