"""Envio de e-mail via Resend (Fase 1 — Solicitação de Audiência,
2026-10-16, trocado da Postmark em 2026-10-23 — ver app/services/
email_resend.py) — API HTTPS via urllib, mesmo padrão de
app/services/suporte.py (webhook do Discord). Modo de teste é o padrão
(a pedido explícito da Clara: nenhum e-mail real sai durante
desenvolvimento/testes) — redireciona tudo pra `email_destinatario_teste`
até alguém ligar EMAIL_ENVIO_REAL=true."""
from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from app.config import settings
from app.services.email_resend import ErroEnvioEmail, enviar_email

_requisicoes: list[dict] = []


class _RespostaFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"id": "fake-id"}'


def _urlopen_falso(requisicao, timeout=None):
    _requisicoes.append(
        {"corpo": json.loads(requisicao.data.decode("utf-8")), "headers": dict(requisicao.header_items())}
    )
    return _RespostaFalsa()


def _urlopen_falha_http(requisicao, timeout=None):
    raise urllib.error.HTTPError(
        url="https://api.resend.com/emails", code=422, msg="Unprocessable Entity",
        hdrs=None, fp=io.BytesIO(b'{"statusCode": 422, "message": "Invalid email request"}'),
    )


@pytest.fixture(autouse=True)
def _config_padrao(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "chave-fake-de-teste")
    monkeypatch.setattr(settings, "resend_remetente", "conciliacao@camaraeximia.com")
    monkeypatch.setattr(settings, "email_envio_real", False)
    monkeypatch.setattr(settings, "email_destinatario_teste", "clara@elitemediacoes.com.br")
    _requisicoes.clear()


def test_sem_chave_configurada_levanta_erro(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", None)
    with pytest.raises(ErroEnvioEmail, match="RESEND_API_KEY"):
        enviar_email(["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo")


def test_sem_remetente_configurado_levanta_erro(monkeypatch):
    monkeypatch.setattr(settings, "resend_remetente", None)
    with pytest.raises(ErroEnvioEmail, match="RESEND_REMETENTE"):
        enviar_email(["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo")


def test_modo_teste_sem_destinatario_configurado_levanta_erro(monkeypatch):
    monkeypatch.setattr(settings, "email_destinatario_teste", None)
    with pytest.raises(ErroEnvioEmail, match="EMAIL_DESTINATARIO_TESTE"):
        enviar_email(["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo")


def test_modo_teste_redireciona_para_destinatario_de_teste(monkeypatch):
    """O ponto central do requisito da Clara: em modo de teste, nenhum
    e-mail real do cliente/banco recebe nada — só o endereço de teste."""
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(["cliente.de.verdade@banco.com", "outro@banco.com"], "Assunto", "<p>Corpo</p>", "Corpo")

    assert len(_requisicoes) == 1
    corpo = _requisicoes[0]["corpo"]
    assert corpo["to"] == ["clara@elitemediacoes.com.br"]
    assert "cliente.de.verdade@banco.com" not in corpo["to"]


def test_modo_producao_envia_para_destinatario_real(monkeypatch):
    monkeypatch.setattr(settings, "email_envio_real", True)
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(["cliente.de.verdade@banco.com"], "Assunto", "<p>Corpo</p>", "Corpo")

    corpo = _requisicoes[0]["corpo"]
    assert corpo["to"] == ["cliente.de.verdade@banco.com"]


def test_envia_assunto_e_corpo_html_e_texto(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(["cliente@teste.com"], "Assunto da carta", "<p>HTML</p>", "texto puro")

    corpo = _requisicoes[0]["corpo"]
    assert corpo["subject"] == "Assunto da carta"
    assert corpo["html"] == "<p>HTML</p>"
    assert corpo["text"] == "texto puro"
    assert corpo["from"] == "conciliacao@camaraeximia.com"


def test_envia_header_de_autorizacao_e_user_agent(monkeypatch):
    """O User-Agent não é opcional — a Resend já bloqueou (Cloudflare,
    erro 1010) chamadas sem um, num uso anterior deste mesmo sistema
    (DECISIONS.md 2026-09-29, ver docstring de email_resend.py)."""
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo")

    headers = _requisicoes[0]["headers"]
    assert headers["Authorization"] == "Bearer chave-fake-de-teste"
    assert headers["User-agent"] == "EliteSistem/1.0 (+https://elite-sistem.onrender.com)"


def test_inclui_anexo_em_base64(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(
        ["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo",
        anexos=[("Carta.pdf", b"conteudo-fake-pdf", "application/pdf")],
    )

    anexo = _requisicoes[0]["corpo"]["attachments"][0]
    assert anexo["filename"] == "Carta.pdf"
    assert anexo["content_type"] == "application/pdf"


def test_inclui_imagem_inline_com_content_id(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(
        ["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo",
        imagens_inline=[("logo-carta", b"bytes-fake-jpeg", "image/jpeg")],
    )

    anexo = _requisicoes[0]["corpo"]["attachments"][0]
    assert anexo["content_id"] == "logo-carta"


def test_falha_http_da_resend_levanta_erro_envio_email(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falha_http)

    with pytest.raises(ErroEnvioEmail, match="422"):
        enviar_email(["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo")
