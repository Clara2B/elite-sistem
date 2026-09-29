"""Chamados de suporte (2026-09-28, a pedido da Clara) — o pop-up flutuante
(ver templates/base.html) manda o chamado pra cá, que envia por SMTP direto
(smtplib, sem serviço terceiro) pro e-mail de suporte. Sem as variáveis de
ambiente de e-mail configuradas (SMTP_HOST/SMTP_USUARIO/SMTP_SENHA), o envio
recusa com uma mensagem amigável em vez de estourar um erro genérico."""
from __future__ import annotations

import smtplib
import socket
from email.message import EmailMessage

from app.config import settings
from app.models import Usuario


class _SMTPForcandoIPv4(smtplib.SMTP):
    """`smtplib.SMTP` comum deixa a escolha entre IPv4/IPv6 a cargo do SO
    (via `socket.create_connection`, que resolve com `AF_UNSPEC`) — em
    produção (Render, 2026-09-29, achado real com a Clara: `OSError:
    [Errno 101] Network is unreachable` tentando falar com o Gmail), a
    resolução de `smtp.gmail.com` às vezes devolve o endereço IPv6
    primeiro, e o container não tem rota de saída por IPv6 configurada — a
    conexão cai antes mesmo de tentar autenticar. Forçando a busca só por
    IPv4 aqui evita isso. `self._host` continua sendo o nome (não o IP
    resolvido) — a verificação de certificado TLS em `starttls()` (que usa
    `server_hostname=self._host`) continua correta."""

    def _get_socket(self, host, port, timeout):
        ultimo_erro: OSError | None = None
        for familia, tipo, proto, _, endereco in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
            sock = socket.socket(familia, tipo, proto)
            try:
                if timeout is not None:
                    sock.settimeout(timeout)
                sock.connect(endereco)
                return sock
            except OSError as e:
                sock.close()
                ultimo_erro = e
        raise ultimo_erro or OSError(f"Não foi possível resolver um endereço IPv4 para {host}.")


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
        with _SMTPForcandoIPv4(settings.smtp_host, settings.smtp_porta, timeout=15) as servidor:
            servidor.starttls()
            servidor.login(settings.smtp_usuario, settings.smtp_senha)
            servidor.send_message(mensagem)
    except (smtplib.SMTPException, OSError) as e:
        raise ValueError(f"Não foi possível enviar o chamado agora ({e}). Tente de novo em instantes.") from e
