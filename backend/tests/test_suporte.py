"""Pop-up de suporte (2026-09-28) — chamado via fetch (JSON), não form."""
import smtplib
from typing import ClassVar

import pytest

from app.auth import hash_senha
from app.config import settings
from app.models import Usuario
from app.services.suporte import enviar_chamado


@pytest.fixture()
def _sem_smtp_configurado(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "smtp_usuario", None)
    monkeypatch.setattr(settings, "smtp_senha", None)


@pytest.fixture()
def _com_smtp_configurado(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.teste.local")
    monkeypatch.setattr(settings, "smtp_porta", 587)
    monkeypatch.setattr(settings, "smtp_usuario", "sistema@elitemediacoes.com.br")
    monkeypatch.setattr(settings, "smtp_senha", "senha-de-app")
    monkeypatch.setattr(settings, "smtp_remetente", None)
    monkeypatch.setattr(settings, "smtp_destinatario_suporte", "claracosta@elitemediacoes.com.br")


class _SmtpFalso:
    enviados: ClassVar[list] = []

    def __init__(self, host, porta, timeout=None):
        self.host = host
        self.porta = porta

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        pass

    def login(self, usuario, senha):
        self.usuario = usuario
        self.senha = senha

    def send_message(self, mensagem):
        _SmtpFalso.enviados.append(mensagem)


def _usuario_logado(db, client, email="chamado@teste.local"):
    db.add(Usuario(nome="Fulana", email=email, senha_hash=hash_senha("certa")))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_enviar_chamado_sem_smtp_configurado_recusa(db, _sem_smtp_configurado):
    usuario = Usuario(nome="Fulana", email="fulana@teste.local", senha_hash=hash_senha("x"))
    with pytest.raises(ValueError, match="não está configurado"):
        enviar_chamado(usuario, "Assunto", "Descrição")


def test_enviar_chamado_com_smtp_mockado_envia(monkeypatch, db, _com_smtp_configurado):
    _SmtpFalso.enviados = []
    monkeypatch.setattr(smtplib, "SMTP", _SmtpFalso)
    usuario = Usuario(nome="Fulana", email="fulana@teste.local", senha_hash=hash_senha("x"))

    enviar_chamado(usuario, "Erro ao importar", "Não consigo importar a planilha de Laudos.")

    assert len(_SmtpFalso.enviados) == 1
    mensagem = _SmtpFalso.enviados[0]
    assert mensagem["Subject"] == "[Elite Sistem] Erro ao importar"
    assert mensagem["To"] == "claracosta@elitemediacoes.com.br"
    assert mensagem["Reply-To"] == "fulana@teste.local"


def test_rota_chamado_sem_login_nao_envia(client, db, _sem_smtp_configurado):
    resposta = client.post(
        "/app/suporte/chamado", json={"assunto": "X", "descricao": "Y"}, follow_redirects=False
    )
    assert resposta.status_code != 200


def test_rota_chamado_valida_campos_vazios(client, db, _com_smtp_configurado):
    _usuario_logado(db, client)
    resposta = client.post("/app/suporte/chamado", json={"assunto": "  ", "descricao": "  "})
    assert resposta.status_code == 400
    assert "assunto" in resposta.json()["erro"].lower()


def test_rota_chamado_sem_smtp_configurado_retorna_erro_amigavel(client, db, _sem_smtp_configurado):
    _usuario_logado(db, client)
    resposta = client.post("/app/suporte/chamado", json={"assunto": "Dúvida", "descricao": "Como funciona X?"})
    assert resposta.status_code == 400
    assert "administrador" in resposta.json()["erro"].lower()


def test_rota_chamado_com_smtp_mockado_envia_e_retorna_ok(monkeypatch, client, db, _com_smtp_configurado):
    _SmtpFalso.enviados = []
    monkeypatch.setattr(smtplib, "SMTP", _SmtpFalso)
    _usuario_logado(db, client, email="chamado.sucesso@teste.local")

    resposta = client.post(
        "/app/suporte/chamado",
        json={"assunto": "Relatório não abre", "descricao": "O PDF de Audiências não gera."},
    )
    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}
    assert len(_SmtpFalso.enviados) == 1
