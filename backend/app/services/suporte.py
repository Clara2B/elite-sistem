"""Chamados de suporte (2026-09-28, a pedido da Clara) — o pop-up flutuante
(ver templates/base.html) manda o chamado pra cá.

Guardado direto no banco (2026-10-01) — depois de três tentativas sem
sucesso de enviar por e-mail em produção (SMTP bloqueado pelo Render,
depois a API HTTP da Resend bloqueada pelo Cloudflare, depois o domínio
elitemediacoes.com.br não verificando na Resend mesmo em duas tentativas da
Clara — ver DECISIONS.md 2026-10-01), abandonamos e-mail de vez: guardar o
chamado no próprio sistema nunca depende de provedor externo, sempre
funciona. A tela de Configuração > Chamados (ver web/routes_chamados.py)
lista todos.

`_avisar_discord` é só um aviso complementar, opcional (configurado via
`DISCORD_WEBHOOK_SUPORTE`) — o chamado já foi salvo antes dela ser chamada,
então uma falha aqui (webhook não configurado, Discord fora do ar, etc.)
nunca derruba a abertura do chamado; só fica sem o aviso em tempo real."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chamado, Usuario

_logger = logging.getLogger("elite_sistem.suporte")


def abrir_chamado(db: Session, usuario: Usuario, assunto: str, descricao: str) -> Chamado:
    chamado = Chamado(usuario_id=usuario.id, assunto=assunto, descricao=descricao)
    db.add(chamado)
    db.commit()
    db.refresh(chamado)
    _avisar_discord(usuario, chamado)
    return chamado


def _avisar_discord(usuario: Usuario, chamado: Chamado) -> None:
    if not settings.discord_webhook_suporte:
        return

    corpo = {
        "content": (
            f"**Novo chamado — {chamado.assunto}**\n"
            f"De: {usuario.nome} ({usuario.email})\n\n"
            f"{chamado.descricao}"
        )
    }
    requisicao = urllib.request.Request(
        settings.discord_webhook_suporte,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "EliteSistem/1.0 (+https://elite-sistem.onrender.com)",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(requisicao, timeout=10)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        _logger.warning("Não foi possível avisar o Discord sobre o chamado #%s: %s", chamado.id, e)
