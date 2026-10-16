"""Tela /app/usuarios — validação de `papel_global` (2026-10-13, auditoria
M10). A API (`app/api/usuarios.py`) já validava que `papel_global` só pode
ser um valor de `PAPEIS_GLOBAIS` ou `None`; a tela web fazia o mesmo POST
sem checar nada, deixando um POST manual gravar um papel_global
arbitrário — um usuário "quebrado": não reconhecido como admin, mas também
não um colaborador comum."""
from __future__ import annotations

from sqlalchemy import select

from app.auth import hash_senha
from app.models import Usuario


def _logar_admin(db, client, email="admin.papel.global@teste.local"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_criar_usuario_com_papel_global_invalido_eh_rejeitado(client, db):
    _logar_admin(db, client)

    resposta = client.post(
        "/app/usuarios",
        data={
            "nome": "Fulano Quebrado", "email": "quebrado@teste.local",
            "senha": "senha123", "papel_global": "SUPER_HACKER",
        },
    )
    assert resposta.status_code == 400
    assert "papel_global" in resposta.text
    assert db.scalar(select(Usuario).where(Usuario.email == "quebrado@teste.local")) is None


def test_criar_usuario_com_papel_global_valido_funciona(client, db):
    _logar_admin(db, client)

    resposta = client.post(
        "/app/usuarios",
        data={
            "nome": "Fulano Admin", "email": "fulano.admin@teste.local",
            "senha": "senha123", "papel_global": "ADMIN_TI",
        },
    )
    assert resposta.status_code == 200
    criado = db.scalar(select(Usuario).where(Usuario.email == "fulano.admin@teste.local"))
    assert criado is not None
    assert criado.papel_global == "ADMIN_TI"


def test_criar_usuario_sem_papel_global_funciona(client, db):
    _logar_admin(db, client)

    resposta = client.post(
        "/app/usuarios",
        data={"nome": "Colaborador Comum", "email": "comum@teste.local", "senha": "senha123"},
    )
    assert resposta.status_code == 200
    criado = db.scalar(select(Usuario).where(Usuario.email == "comum@teste.local"))
    assert criado is not None
    assert criado.papel_global is None


def test_editar_usuario_com_papel_global_invalido_eh_rejeitado(client, db):
    _logar_admin(db, client)
    alvo = Usuario(nome="Fulano", email="editar.quebrado@teste.local", senha_hash=hash_senha("x"))
    db.add(alvo)
    db.commit()

    resposta = client.post(
        f"/app/usuarios/{alvo.id}",
        data={"nome": "Fulano", "email": "editar.quebrado@teste.local", "papel_global": "SUPER_HACKER"},
    )
    assert resposta.status_code == 400
    db.refresh(alvo)
    assert alvo.papel_global is None


def test_editar_usuario_com_papel_global_valido_funciona(client, db):
    _logar_admin(db, client)
    alvo = Usuario(nome="Fulano", email="editar.ok@teste.local", senha_hash=hash_senha("x"))
    db.add(alvo)
    db.commit()

    resposta = client.post(
        f"/app/usuarios/{alvo.id}",
        data={"nome": "Fulano", "email": "editar.ok@teste.local", "papel_global": "ADMIN_SUPERIOR"},
    )
    assert resposta.status_code == 200
    db.refresh(alvo)
    assert alvo.papel_global == "ADMIN_SUPERIOR"
