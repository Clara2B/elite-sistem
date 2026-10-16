"""Envio de e-mail via Postmark (Fase 1 — Solicitação de Audiência,
2026-10-16) — API HTTPS via urllib, mesmo padrão de
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
from app.services.email_postmark import ErroEnvioEmail, enviar_email

_requisicoes: list[dict] = []


class _RespostaFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"ErrorCode": 0, "Message": "OK"}'


def _urlopen_falso(requisicao, timeout=None):
    _requisicoes.append(
        {"corpo": json.loads(requisicao.data.decode("utf-8")), "headers": dict(requisicao.header_items())}
    )
    return _RespostaFalsa()


def _urlopen_falha_http(requisicao, timeout=None):
    raise urllib.error.HTTPError(
        url="https://api.postmarkapp.com/email", code=422, msg="Unprocessable Entity",
        hdrs=None, fp=io.BytesIO(b'{"ErrorCode": 300, "Message": "Invalid email request"}'),
    )


@pytest.fixture(autouse=True)
def _config_padrao(monkeypatch):
    monkeypatch.setattr(settings, "postmark_server_token", "token-fake-de-teste")
    monkeypatch.setattr(settings, "postmark_remetente", "conciliacao@camaraeximia.com")
    monkeypatch.setattr(settings, "email_envio_real", False)
    monkeypatch.setattr(settings, "email_destinatario_teste", "clara@elitemediacoes.com.br")
    _requisicoes.clear()


def test_sem_token_configurado_levanta_erro(monkeypatch):
    monkeypatch.setattr(settings, "postmark_server_token", None)
    with pytest.raises(ErroEnvioEmail, match="POSTMARK_SERVER_TOKEN"):
        enviar_email(["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo")


def test_sem_remetente_configurado_levanta_erro(monkeypatch):
    monkeypatch.setattr(settings, "postmark_remetente", None)
    with pytest.raises(ErroEnvioEmail, match="POSTMARK_REMETENTE"):
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
    assert corpo["To"] == "clara@elitemediacoes.com.br"
    assert "cliente.de.verdade@banco.com" not in corpo["To"]


def test_modo_producao_envia_para_destinatario_real(monkeypatch):
    monkeypatch.setattr(settings, "email_envio_real", True)
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(["cliente.de.verdade@banco.com"], "Assunto", "<p>Corpo</p>", "Corpo")

    corpo = _requisicoes[0]["corpo"]
    assert corpo["To"] == "cliente.de.verdade@banco.com"


def test_envia_assunto_e_corpo_html_e_texto(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(["cliente@teste.com"], "Assunto da carta", "<p>HTML</p>", "texto puro")

    corpo = _requisicoes[0]["corpo"]
    assert corpo["Subject"] == "Assunto da carta"
    assert corpo["HtmlBody"] == "<p>HTML</p>"
    assert corpo["TextBody"] == "texto puro"
    assert corpo["From"] == "conciliacao@camaraeximia.com"


def test_envia_header_do_token_postmark(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo")

    assert _requisicoes[0]["headers"]["X-postmark-server-token"] == "token-fake-de-teste"


def test_inclui_anexo_em_base64(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(
        ["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo",
        anexos=[("Carta.pdf", b"conteudo-fake-pdf", "application/pdf")],
    )

    anexo = _requisicoes[0]["corpo"]["Attachments"][0]
    assert anexo["Name"] == "Carta.pdf"
    assert anexo["ContentType"] == "application/pdf"


def test_inclui_imagem_inline_com_content_id(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)

    enviar_email(
        ["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo",
        imagens_inline=[("logo-carta", b"bytes-fake-jpeg", "image/jpeg")],
    )

    anexo = _requisicoes[0]["corpo"]["Attachments"][0]
    assert anexo["ContentID"] == "cid:logo-carta"


def test_falha_http_da_postmark_levanta_erro_envio_email(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falha_http)

    with pytest.raises(ErroEnvioEmail, match="422"):
        enviar_email(["cliente@teste.com"], "Assunto", "<p>Corpo</p>", "Corpo")
