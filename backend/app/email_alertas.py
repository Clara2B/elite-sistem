"""Envio de e-mail de alerta de prazo (Fase 5) via Resend (free tier).

Sem `RESEND_API_KEY`/`RESEND_EMAIL_REMETENTE` configurados, `enviar_email`
não faz nada e devolve False — o resto do sistema continua funcionando
normalmente (o painel de "prazos próximos" dentro do sistema não depende
disso). Nunca levanta exceção: um provedor de e-mail fora do ar não pode
derrubar uma rota da API.
"""
from __future__ import annotations

import httpx

from app.config import settings

RESEND_API_URL = "https://api.resend.com/emails"


def enviar_email(destinatario: str, assunto: str, corpo_texto: str) -> bool:
    if not settings.resend_api_key or not settings.resend_email_remetente:
        return False
    try:
        resposta = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_email_remetente,
                "to": [destinatario],
                "subject": assunto,
                "text": corpo_texto,
            },
            timeout=10.0,
        )
        return resposta.status_code < 300
    except httpx.HTTPError:
        return False
