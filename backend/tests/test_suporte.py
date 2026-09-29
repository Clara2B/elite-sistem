"""Pop-up de suporte (2026-09-28) — chamado via fetch (JSON), não form.

Envia por e-mail via a API HTTP da Resend (2026-09-29, trocado de SMTP
direto depois de confirmar em produção que o Render bloqueia/derruba a
conexão de saída por SMTP — ver services/suporte.py e DECISIONS.md)."""
import io
import json
import urllib.error
import urllib.request

import pytest

from app.auth import hash_senha
from app.config import settings
from app.models import Usuario
from app.services.suporte import enviar_chamado


@pytest.fixture()
def _sem_resend_configurado(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", None)


@pytest.fixture()
def _com_resend_configurado(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_chave_de_teste")
    monkeypatch.setattr(settings, "resend_remetente", "Elite Sistem <onboarding@resend.dev>")
    monkeypatch.setattr(settings, "destinatario_suporte", "claracosta@elitemediacoes.com.br")


_requisicoes_enviadas: list[dict] = []


class _RespostaFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"id": "email-de-teste"}'


def _urlopen_falso(requisicao, timeout=None):
    _requisicoes_enviadas.append(
        {"corpo": json.loads(requisicao.data.decode("utf-8")), "headers": dict(requisicao.header_items())}
    )
    return _RespostaFalsa()


def _urlopen_falha_http(requisicao, timeout=None):
    raise urllib.error.HTTPError(
        url="https://api.resend.com/emails", code=422, msg="Unprocessable Entity",
        hdrs=None, fp=io.BytesIO(b'{"message": "domain not verified"}'),
    )


def _usuario_logado(db, client, email="chamado@teste.local"):
    db.add(Usuario(nome="Fulana", email=email, senha_hash=hash_senha("certa")))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_enviar_chamado_sem_api_key_recusa(db, _sem_resend_configurado):
    usuario = Usuario(nome="Fulana", email="fulana@teste.local", senha_hash=hash_senha("x"))
    with pytest.raises(ValueError, match="não está configurado"):
        enviar_chamado(usuario, "Assunto", "Descrição")


def test_enviar_chamado_com_resend_mockado_envia(monkeypatch, db, _com_resend_configurado):
    _requisicoes_enviadas.clear()
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)
    usuario = Usuario(nome="Fulana", email="fulana@teste.local", senha_hash=hash_senha("x"))

    enviar_chamado(usuario, "Erro ao importar", "Não consigo importar a planilha de Laudos.")

    assert len(_requisicoes_enviadas) == 1
    corpo = _requisicoes_enviadas[0]["corpo"]
    assert corpo["subject"] == "[Elite Sistem] Erro ao importar"
    assert corpo["to"] == ["claracosta@elitemediacoes.com.br"]
    assert corpo["reply_to"] == "fulana@teste.local"
    assert "Não consigo importar a planilha de Laudos." in corpo["text"]
    assert _requisicoes_enviadas[0]["headers"]["Authorization"] == "Bearer re_chave_de_teste"


def test_enviar_chamado_resend_recusa_http_vira_erro_amigavel(monkeypatch, db, _com_resend_configurado):
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falha_http)
    usuario = Usuario(nome="Fulana", email="fulana@teste.local", senha_hash=hash_senha("x"))

    with pytest.raises(ValueError, match="domain not verified"):
        enviar_chamado(usuario, "Assunto", "Descrição")


def test_rota_chamado_sem_login_nao_envia(client, db, _sem_resend_configurado):
    resposta = client.post(
        "/app/suporte/chamado", json={"assunto": "X", "descricao": "Y"}, follow_redirects=False
    )
    assert resposta.status_code != 200


def test_rota_chamado_valida_campos_vazios(client, db, _com_resend_configurado):
    _usuario_logado(db, client)
    resposta = client.post("/app/suporte/chamado", json={"assunto": "  ", "descricao": "  "})
    assert resposta.status_code == 400
    assert "assunto" in resposta.json()["erro"].lower()


def test_rota_chamado_sem_api_key_retorna_erro_amigavel(client, db, _sem_resend_configurado):
    _usuario_logado(db, client)
    resposta = client.post("/app/suporte/chamado", json={"assunto": "Dúvida", "descricao": "Como funciona X?"})
    assert resposta.status_code == 400
    assert "administrador" in resposta.json()["erro"].lower()


def test_rota_chamado_com_resend_mockado_envia_e_retorna_ok(monkeypatch, client, db, _com_resend_configurado):
    _requisicoes_enviadas.clear()
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)
    _usuario_logado(db, client, email="chamado.sucesso@teste.local")

    resposta = client.post(
        "/app/suporte/chamado",
        json={"assunto": "Relatório não abre", "descricao": "O PDF de Audiências não gera."},
    )
    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}
    assert len(_requisicoes_enviadas) == 1
