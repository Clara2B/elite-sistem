"""Chamados de suporte (2026-09-28, a pedido da Clara) — o pop-up flutuante
(ver templates/base.html) manda o chamado pra cá, que envia por e-mail via a
API HTTP da Resend.

Não é SMTP direto de propósito: a primeira versão usava `smtplib`, e em
produção (Render) o envio nunca completava — primeiro `OSError: [Errno 101]
Network is unreachable` (corrigido forçando IPv4), depois "timed out" mesmo
assim (achado real com a Clara, 2026-09-29 — ver DECISIONS.md). Isso é o
padrão de um firewall de saída derrubando a conexão silenciosamente, comum
em plataformas de hospedagem pra evitar que a plataforma vire relay de
spam — não um bug de código. Uma API HTTP (porta 443, mesma usada por
qualquer chamada normal do navegador) contorna isso por completo; este
mesmo projeto já usou a Resend com sucesso nesse mesmo Render antes (alerta
de prazo de Gestão de Processos, removido depois por decisão de produto da
Clara, não por falha técnica — ver ARCHITECTURE.md 3.5).

Sem `RESEND_API_KEY` configurada, o envio recusa com uma mensagem amigável
em vez de estourar um erro genérico. Usa só a biblioteca padrão do Python
(`urllib`) — a Resend não exige nenhum SDK, é uma chamada HTTP simples."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.config import settings
from app.models import Usuario

_RESEND_URL = "https://api.resend.com/emails"


def enviar_chamado(usuario: Usuario, assunto: str, descricao: str) -> None:
    if not settings.resend_api_key:
        raise ValueError(
            "O envio de chamados ainda não está configurado neste sistema "
            "(falta a chave de API do Resend). Avise o administrador."
        )

    corpo = {
        "from": settings.resend_remetente,
        "to": [settings.destinatario_suporte],
        "reply_to": usuario.email,
        "subject": f"[Elite Sistem] {assunto}",
        "text": f"Chamado aberto por {usuario.nome} ({usuario.email}) no Elite Sistem.\n\n{descricao}",
    }
    requisicao = urllib.request.Request(
        _RESEND_URL,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        urllib.request.urlopen(requisicao, timeout=15)
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")
        raise ValueError(
            f"Não foi possível enviar o chamado agora (Resend recusou: {detalhe}). Tente de novo em instantes."
        ) from e
    except urllib.error.URLError as e:
        raise ValueError(f"Não foi possível enviar o chamado agora ({e.reason}). Tente de novo em instantes.") from e
