"""Tela /app/usuarios — validação de `papel_global` (2026-10-13, auditoria
M10). A API (`app/api/usuarios.py`) já validava que `papel_global` só pode
ser um valor de `PAPEIS_GLOBAIS` ou `None`; a tela web fazia o mesmo POST
sem checar nada, deixando um POST manual gravar um papel_global
arbitrário — um usuário "quebrado": não reconhecido como admin, mas também
não um colaborador comum.

Auditoria M30: não existia test_web_usuarios.py — só a API equivalente
(/usuarios, tests/test_permissoes.py) era testada; a tela (/app/usuarios)
tinha cobertura parcial, espalhada em test_web.py (edição de usuário,
"não pode deixar sistema sem admin"), mas faltava criação, ativar/
desativar e e-mail duplicado pela tela. Replica aqui os casos
equivalentes de test_permissoes.py."""
from __future__ import annotations

from sqlalchemy import select

from app.auth import hash_senha
from app.models import Setor, Usuario, UsuarioSetor


def _logar_admin(db, client, email="admin.webusuarios@teste.local"):
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


def _logar_colaborador(db, client, email="colab.webusuarios@teste.local"):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email=email, senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_admin_cria_usuario_com_setor_vinculado_pela_tela(client, db):
    _logar_admin(db, client)
    setor = db.scalar(select(Setor).where(Setor.nome == "Doutores(as)"))

    resposta = client.post(
        "/app/usuarios",
        data={"nome": "Dra. Fulana", "email": "dra.fulana.web@teste.local", "senha": "senha123", f"setor_{setor.id}": "on", f"papel_{setor.id}": "LIDER"},
    )
    assert resposta.status_code == 200
    assert "Dra. Fulana" in resposta.text

    criado = db.scalar(select(Usuario).where(Usuario.email == "dra.fulana.web@teste.local"))
    assert criado is not None
    vinculo = db.scalar(select(UsuarioSetor).where(UsuarioSetor.usuario_id == criado.id))
    assert vinculo.setor_id == setor.id
    assert vinculo.papel == "LIDER"

    login = client.post(
        "/login", data={"email": "dra.fulana.web@teste.local", "senha": "senha123"}, follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/"


def test_criar_usuario_pela_tela_exige_admin(client, db):
    _logar_colaborador(db, client)
    resposta = client.post(
        "/app/usuarios", data={"nome": "X", "email": "x@teste.local", "senha": "senha123"}, follow_redirects=False
    )
    assert resposta.status_code == 403
    assert db.scalar(select(Usuario).where(Usuario.email == "x@teste.local")) is None


def test_criar_usuario_pela_tela_email_duplicado_mostra_erro(client, db):
    _logar_admin(db, client, "admin.dup@teste.local")
    client.post("/app/usuarios", data={"nome": "Fulana", "email": "duplicado.web@teste.local", "senha": "senha123"})

    resposta = client.post("/app/usuarios", data={"nome": "Outra Fulana", "email": "duplicado.web@teste.local", "senha": "outrasenha"})
    assert resposta.status_code == 400
    assert "já existe" in resposta.text.lower()
    assert db.scalar(select(Usuario).where(Usuario.email == "duplicado.web@teste.local", Usuario.nome == "Outra Fulana")) is None


def test_criar_usuario_pela_tela_campos_obrigatorios_faltando_mostra_erro(client, db):
    _logar_admin(db, client, "admin.obrigatorios@teste.local")
    resposta = client.post("/app/usuarios", data={"nome": "", "email": "", "senha": ""})
    assert resposta.status_code == 400
    assert "obrigatórios" in resposta.text.lower()


def test_admin_ativa_e_desativa_usuario_pela_tela(client, db):
    _logar_admin(db, client, "admin.ativo@teste.local")
    alvo = Usuario(nome="Fulana", email="fulana.ativo@teste.local", senha_hash=hash_senha("senha123"))
    db.add(alvo)
    db.commit()
    db.refresh(alvo)

    resposta = client.post(f"/app/usuarios/{alvo.id}/ativo?ativo=false", follow_redirects=False)
    assert resposta.status_code == 303
    db.refresh(alvo)
    assert alvo.ativo is False

    # usuário inativo não consegue logar
    login_bloqueado = client.post(
        "/login", data={"email": "fulana.ativo@teste.local", "senha": "senha123"}, follow_redirects=False,
    )
    assert login_bloqueado.status_code == 401

    resposta = client.post(f"/app/usuarios/{alvo.id}/ativo?ativo=true", follow_redirects=False)
    assert resposta.status_code == 303
    db.refresh(alvo)
    assert alvo.ativo is True

    login_liberado = client.post(
        "/login", data={"email": "fulana.ativo@teste.local", "senha": "senha123"}, follow_redirects=False,
    )
    assert login_liberado.status_code == 303


def test_ativar_desativar_usuario_pela_tela_exige_admin(client, db):
    alvo = Usuario(nome="Fulana", email="fulana.semadmin@teste.local", senha_hash=hash_senha("senha123"))
    db.add(alvo)
    db.commit()
    db.refresh(alvo)

    _logar_colaborador(db, client, "colab.semadmin@teste.local")
    resposta = client.post(f"/app/usuarios/{alvo.id}/ativo?ativo=false", follow_redirects=False)
    assert resposta.status_code == 403
    db.refresh(alvo)
    assert alvo.ativo is True
