"""Pop-up de suporte (2026-09-28) — chamado via fetch (JSON), não form.

Guardado no banco (2026-10-01, trocado de e-mail depois de três tentativas
sem sucesso em produção — SMTP bloqueado, Resend bloqueada pelo Cloudflare,
domínio não verificando na Resend — ver services/suporte.py e
DECISIONS.md). O Discord é só um aviso complementar, opcional e best-
effort: ver test_abrir_chamado_discord_configurado_mas_falha_nao_impede_salvar."""
from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest
from sqlalchemy import select

from app.auth import hash_senha
from app.config import settings
from app.models import Chamado, LogAuditoria, Usuario
from app.services.suporte import abrir_chamado


@pytest.fixture()
def _sem_discord_configurado(monkeypatch):
    monkeypatch.setattr(settings, "discord_webhook_suporte", None)


@pytest.fixture()
def _com_discord_configurado(monkeypatch):
    monkeypatch.setattr(settings, "discord_webhook_suporte", "https://discord.com/api/webhooks/teste")


_requisicoes_enviadas: list[dict] = []


class _RespostaFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b""


def _urlopen_falso(requisicao, timeout=None):
    _requisicoes_enviadas.append(
        {"corpo": json.loads(requisicao.data.decode("utf-8")), "headers": dict(requisicao.header_items())}
    )
    return _RespostaFalsa()


def _urlopen_falha_http(requisicao, timeout=None):
    raise urllib.error.HTTPError(
        url="https://discord.com/api/webhooks/teste", code=404, msg="Not Found",
        hdrs=None, fp=io.BytesIO(b"Unknown Webhook"),
    )


def _usuario(db, email="chamado@teste.local") -> Usuario:
    usuario = Usuario(nome="Fulana", email=email, senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _usuario_logado(db, client, email="chamado@teste.local"):
    _usuario(db, email)
    client.post("/login", data={"email": email, "senha": "certa"})


def test_abrir_chamado_sem_discord_configurado_salva_normalmente(db, _sem_discord_configurado):
    usuario = _usuario(db)
    chamado = abrir_chamado(db, usuario, "Erro ao importar", "Não consigo importar a planilha de Laudos.")

    assert chamado.id is not None
    salvo = db.get(Chamado, chamado.id)
    assert salvo.assunto == "Erro ao importar"
    assert salvo.descricao == "Não consigo importar a planilha de Laudos."
    assert salvo.usuario_id == usuario.id
    assert salvo.resolvido is False


def test_abrir_chamado_com_discord_configurado_avisa(monkeypatch, db, _com_discord_configurado):
    _requisicoes_enviadas.clear()
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falso)
    usuario = _usuario(db)

    abrir_chamado(db, usuario, "Dúvida", "Como funciona X?")

    assert len(_requisicoes_enviadas) == 1
    corpo = _requisicoes_enviadas[0]["corpo"]
    assert "Dúvida" in corpo["content"]
    assert "Fulana" in corpo["content"]
    assert "Como funciona X?" in corpo["content"]
    headers = _requisicoes_enviadas[0]["headers"]
    assert "Python-urllib" not in headers.get("User-agent", "")


def test_abrir_chamado_discord_configurado_mas_falha_nao_impede_salvar(monkeypatch, db, _com_discord_configurado):
    """O aviso do Discord é complementar — se ele falhar, o chamado já foi
    salvo e continua lá (diferente da versão por e-mail de antes, onde a
    falha do provedor derrubava a abertura do chamado inteira)."""
    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_falha_http)
    usuario = _usuario(db)

    chamado = abrir_chamado(db, usuario, "Assunto", "Descrição")

    assert db.get(Chamado, chamado.id) is not None


def test_rota_chamado_sem_login_nao_acessa(client, db):
    resposta = client.post(
        "/app/suporte/chamado", json={"assunto": "X", "descricao": "Y"}, follow_redirects=False
    )
    assert resposta.status_code != 200


def test_rota_chamado_valida_campos_vazios(client, db):
    _usuario_logado(db, client)
    resposta = client.post("/app/suporte/chamado", json={"assunto": "  ", "descricao": "  "})
    assert resposta.status_code == 400
    assert "assunto" in resposta.json()["erro"].lower()


def test_rota_chamado_salva_e_retorna_ok(client, db):
    _usuario_logado(db, client, email="chamado.sucesso@teste.local")

    resposta = client.post(
        "/app/suporte/chamado",
        json={"assunto": "Relatório não abre", "descricao": "O PDF de Audiências não gera."},
    )
    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}

    chamado = db.scalar(select(Chamado).where(Chamado.assunto == "Relatório não abre"))
    assert chamado is not None
    assert chamado.descricao == "O PDF de Audiências não gera."

    log = db.scalar(select(LogAuditoria).where(LogAuditoria.acao == "ABRIU_CHAMADO_SUPORTE"))
    assert log is not None
    assert log.entidade_id == str(chamado.id)
