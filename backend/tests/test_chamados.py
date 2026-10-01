"""Tela de Configuração > Chamados (2026-10-01) — lista os chamados salvos
por services/suporte.py::abrir_chamado e permite marcar/desmarcar
resolvido. Só Admin acessa, mesmo padrão das outras áreas de Configuração."""
from __future__ import annotations

from app.auth import hash_senha
from app.models import Chamado, Usuario
from app.services.suporte import abrir_chamado


def _logar_admin(db, client, email="admin.chamados@teste.local"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _logar_colaborador(db, client, email="colab.chamados@teste.local"):
    usuario = Usuario(nome="Colaborador", email=email, senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})
    return usuario


def test_tela_chamados_exige_admin(client, db):
    _logar_colaborador(db, client)
    resposta = client.get("/app/chamados", follow_redirects=False)
    assert resposta.status_code != 200


def test_tela_chamados_lista_chamados_abertos(client, db):
    colaborador = _logar_colaborador(db, client, "colab.lista@teste.local")
    abrir_chamado(db, colaborador, "Erro ao importar", "Não consigo importar a planilha de Laudos.")

    _logar_admin(db, client, "admin.lista@teste.local")
    resposta = client.get("/app/chamados")
    assert resposta.status_code == 200
    assert "Erro ao importar" in resposta.text
    assert "Não consigo importar a planilha de Laudos." in resposta.text
    assert "Aberto" in resposta.text


def test_marcar_chamado_resolvido_exige_admin(client, db):
    colaborador = _logar_colaborador(db, client, "colab.resolver@teste.local")
    chamado = abrir_chamado(db, colaborador, "Assunto", "Descrição")

    resposta = client.post(f"/app/chamados/{chamado.id}/resolvido?resolvido=true", follow_redirects=False)
    assert resposta.status_code != 200
    db.refresh(chamado)
    assert chamado.resolvido is False


def test_marcar_chamado_resolvido_e_reabrir(client, db):
    colaborador = _logar_colaborador(db, client, "colab.toggle@teste.local")
    chamado = abrir_chamado(db, colaborador, "Assunto", "Descrição")
    chamado_id = chamado.id

    _logar_admin(db, client, "admin.toggle@teste.local")
    resposta = client.post(f"/app/chamados/{chamado_id}/resolvido?resolvido=true", follow_redirects=False)
    assert resposta.status_code == 303

    db.expire_all()
    assert db.get(Chamado, chamado_id).resolvido is True

    resposta = client.post(f"/app/chamados/{chamado_id}/resolvido?resolvido=false", follow_redirects=False)
    assert resposta.status_code == 303
    db.expire_all()
    assert db.get(Chamado, chamado_id).resolvido is False
