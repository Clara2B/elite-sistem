"""Envio de e-mail via Resend (Fase 1 — Solicitação de Audiência, trocado
da Postmark em 2026-10-23, a pedido da Clara: a conta da Postmark ficou
presa em "pendente de aprovação" sem resposta por dias). API HTTPS simples
via `urllib` (mesmo padrão já usado em app/services/suporte.py pro webhook
do Discord), sem SDK novo.

ATENÇÃO — Cloudflare: a Resend já causou um bloqueio anti-bot (erro
"1010") num uso anterior deste mesmo sistema (pop-up de suporte,
DECISIONS.md 2026-09-29) — a causa era a ausência de um User-Agent próprio
nas chamadas (o padrão do `urllib`, "Python-urllib/3.x", é reconhecido e
bloqueado por proteções anti-bot, independente da chave de API estar
certa). Por isso o mesmo User-Agent usado em suporte.py é obrigatório
aqui desde o início — não é opcional."""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request

from app.config import settings

_logger = logging.getLogger("elite_sistem.email")
_URL_RESEND = "https://api.resend.com/emails"
_USER_AGENT = "EliteSistem/1.0 (+https://elite-sistem.onrender.com)"


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
    """Envia um e-mail via Resend. `anexos`/`imagens_inline` são listas de
    (nome_ou_content_id, conteúdo_em_bytes, tipo_mime) — imagens inline
    ficam disponíveis no HTML via `cid:<content_id>` (ver
    app/services/cartas.py::formatar_html_carta_*), usando o campo
    `content_id` do anexo (ver "embed inline images" na documentação da
    Resend).

    Modo de teste (`settings.email_envio_real = False`, o padrão — a
    pedido explícito da Clara: "nenhum email real deve ser enviado durante
    o desenvolvimento e os testes"): redireciona TODOS os destinatários
    pra `settings.email_destinatario_teste`. O e-mail sai de verdade (não
    é uma simulação), só que sempre pra esse endereço — nunca pro
    cliente/banco real — até alguém ligar EMAIL_ENVIO_REAL=true no Render."""
    if not settings.resend_api_key:
        raise ErroEnvioEmail("RESEND_API_KEY não está configurado.")
    if not settings.resend_remetente:
        raise ErroEnvioEmail("RESEND_REMETENTE não está configurado.")

    destinatarios_reais = destinatarios
    if not settings.email_envio_real:
        if not settings.email_destinatario_teste:
            raise ErroEnvioEmail(
                "Modo de teste ativo (EMAIL_ENVIO_REAL não está 'true') mas "
                "EMAIL_DESTINATARIO_TESTE não está configurado — não há pra onde enviar."
            )
        destinatarios_reais = [settings.email_destinatario_teste]

    corpo: dict = {
        "from": settings.resend_remetente,
        "to": destinatarios_reais,
        "subject": assunto,
        "html": corpo_html,
        "text": corpo_texto,
    }
    anexos_resend = [
        {"filename": nome, "content": base64.b64encode(conteudo).decode("ascii"), "content_type": tipo_mime}
        for nome, conteudo, tipo_mime in (anexos or [])
    ]
    for content_id, conteudo, tipo_mime in imagens_inline or []:
        anexos_resend.append({
            "filename": content_id,
            "content": base64.b64encode(conteudo).decode("ascii"),
            "content_type": tipo_mime,
            "content_id": content_id,
        })
    if anexos_resend:
        corpo["attachments"] = anexos_resend

    requisicao = urllib.request.Request(
        _URL_RESEND,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.resend_api_key}",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=15) as resposta:
            resposta.read()
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")
        _logger.warning("Resend recusou o envio (HTTP %s): %s", e.code, detalhe)
        raise ErroEnvioEmail(f"Resend recusou o envio (HTTP {e.code}): {detalhe}") from e
    except urllib.error.URLError as e:
        _logger.warning("Não foi possível conectar à Resend: %s", e)
        raise ErroEnvioEmail(f"Não foi possível conectar à Resend: {e}") from e
