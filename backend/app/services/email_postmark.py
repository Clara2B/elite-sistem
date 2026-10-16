"""Envio de e-mail via Postmark (Fase 1 — Solicitação de Audiência,
2026-10-16) — provedor escolhido pela Clara depois do histórico de três
tentativas fracassadas com e-mail no pop-up de suporte (SMTP bloqueado pelo
Render, Resend bloqueada pelo Cloudflare — ver DECISIONS.md 2026-10-01).
API HTTPS simples via `urllib` (mesmo padrão já usado em
app/services/suporte.py pro webhook do Discord), sem SDK novo."""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request

from app.config import settings

_logger = logging.getLogger("elite_sistem.email")
_URL_POSTMARK = "https://api.postmarkapp.com/email"


class ErroEnvioEmail(Exception):
    """Levantada em qualquer falha de envio — mensagem já pronta pra
    guardar em `EnvioEmail.erro`. Nunca propaga a exceção original do
    `urllib`, só o texto."""


def enviar_email(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    corpo_texto: str,
    anexos: list[tuple[str, bytes, str]] | None = None,
    imagens_inline: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """Envia um e-mail via Postmark. `anexos`/`imagens_inline` são listas
    de (nome_ou_content_id, conteúdo_em_bytes, tipo_mime) — imagens inline
    ficam disponíveis no HTML via `cid:<content_id>` (ver
    app/services/cartas.py::formatar_html_carta_*).

    Modo de teste (`settings.email_envio_real = False`, o padrão — a
    pedido explícito da Clara: "nenhum email real deve ser enviado durante
    o desenvolvimento e os testes"): redireciona TODOS os destinatários
    pra `settings.email_destinatario_teste`. O e-mail sai de verdade (não
    é uma simulação), só que sempre pra esse endereço — nunca pro
    cliente/banco real — até alguém ligar EMAIL_ENVIO_REAL=true no Render."""
    if not settings.postmark_server_token:
        raise ErroEnvioEmail("POSTMARK_SERVER_TOKEN não está configurado.")
    if not settings.postmark_remetente:
        raise ErroEnvioEmail("POSTMARK_REMETENTE não está configurado.")

    destinatarios_reais = destinatarios
    if not settings.email_envio_real:
        if not settings.email_destinatario_teste:
            raise ErroEnvioEmail(
                "Modo de teste ativo (EMAIL_ENVIO_REAL não está 'true') mas "
                "EMAIL_DESTINATARIO_TESTE não está configurado — não há pra onde enviar."
            )
        destinatarios_reais = [settings.email_destinatario_teste]

    corpo: dict = {
        "From": settings.postmark_remetente,
        "To": ", ".join(destinatarios_reais),
        "Subject": assunto,
        "HtmlBody": corpo_html,
        "TextBody": corpo_texto,
        "MessageStream": "outbound",
    }
    anexos_postmark = [
        {"Name": nome, "Content": base64.b64encode(conteudo).decode("ascii"), "ContentType": tipo_mime}
        for nome, conteudo, tipo_mime in (anexos or [])
    ]
    for content_id, conteudo, tipo_mime in imagens_inline or []:
        anexos_postmark.append({
            "Name": content_id,
            "Content": base64.b64encode(conteudo).decode("ascii"),
            "ContentType": tipo_mime,
            "ContentID": f"cid:{content_id}",
        })
    if anexos_postmark:
        corpo["Attachments"] = anexos_postmark

    requisicao = urllib.request.Request(
        _URL_POSTMARK,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": settings.postmark_server_token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=15) as resposta:
            resposta.read()
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")
        _logger.warning("Postmark recusou o envio (HTTP %s): %s", e.code, detalhe)
        raise ErroEnvioEmail(f"Postmark recusou o envio (HTTP {e.code}): {detalhe}") from e
    except urllib.error.URLError as e:
        _logger.warning("Não foi possível conectar à Postmark: %s", e)
        raise ErroEnvioEmail(f"Não foi possível conectar à Postmark: {e}") from e
