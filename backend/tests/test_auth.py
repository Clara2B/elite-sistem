from datetime import datetime, timedelta

from app.auth import _hash_token, hash_senha
from app.models import LogAuditoria, Sessao, Usuario


def _criar_usuario(db, email="fulano@teste.com", senha="senha123", papel_global=None):
    usuario = Usuario(nome="Fulano", email=email, senha_hash=hash_senha(senha), papel_global=papel_global)
    db.add(usuario)
    db.commit()
    return usuario


def test_login_com_senha_certa(client, db):
    _criar_usuario(db, senha="senha123")
    resp = client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "senha123"})
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["usuario"]["email"] == "fulano@teste.com"


def test_login_com_senha_errada(client, db):
    _criar_usuario(db, senha="senha123")
    resp = client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "errada"})
    assert resp.status_code == 401


def test_login_usuario_inexistente(client):
    resp = client.post("/auth/login", json={"email": "ninguem@teste.com", "senha": "x"})
    assert resp.status_code == 401


def test_login_bloqueia_apos_5_tentativas_falhas(client, db):
    """Auditoria M08: sem isso, nenhuma tentativa automatizada de login
    travava — só o custo do bcrypt. 5 falhas seguidas pro mesmo e-mail
    bloqueiam tentativas novas por um tempo, mesmo com a senha certa."""
    _criar_usuario(db, email="bloqueio@teste.com", senha="senha123")

    for _ in range(5):
        resp = client.post("/auth/login", json={"email": "bloqueio@teste.com", "senha": "errada"})
        assert resp.status_code == 401

    resp = client.post("/auth/login", json={"email": "bloqueio@teste.com", "senha": "senha123"})
    assert resp.status_code == 429


def test_bloqueio_de_login_eh_por_email_nao_global(client, db):
    _criar_usuario(db, email="vitima@teste.com", senha="senha123")
    _criar_usuario(db, email="outro.usuario@teste.com", senha="senha456")

    for _ in range(5):
        client.post("/auth/login", json={"email": "vitima@teste.com", "senha": "errada"})

    resp = client.post("/auth/login", json={"email": "outro.usuario@teste.com", "senha": "senha456"})
    assert resp.status_code == 200


def test_tentativas_fora_da_janela_de_bloqueio_nao_contam(client, db):
    _criar_usuario(db, email="janela@teste.com", senha="senha123")
    antigo = datetime.utcnow() - timedelta(minutes=30)
    for _ in range(5):
        db.add(LogAuditoria(acao="LOGIN_FALHOU", entidade="usuario", entidade_id="janela@teste.com", criado_em=antigo))
    db.commit()

    resp = client.post("/auth/login", json={"email": "janela@teste.com", "senha": "senha123"})
    assert resp.status_code == 200


def test_me_sem_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_com_token(client, db):
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "senha123"})
    token = login.json()["token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "fulano@teste.com"


def test_logout_invalida_o_token(client, db):
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "senha123"})
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_token_de_sessao_nunca_fica_em_texto_puro_no_banco(client, db):
    """Auditoria M07: `Sessao.token` guarda o hash, não o token de verdade
    — um dump/backup do banco não deve entregar um token pronto pra uso."""
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "senha123"})
    token = login.json()["token"]

    todas_as_sessoes = db.query(Sessao).all()
    assert len(todas_as_sessoes) == 1
    sessao = todas_as_sessoes[0]
    assert sessao.token != token
    assert sessao.token == _hash_token(token)

    # Buscar pelo token em texto puro direto (sem passar pelo hash) não
    # pode achar nada — é exatamente o que um leitor direto do banco veria.
    assert db.get(Sessao, token) is None


def test_trocar_senha(client, db):
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "senha123"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    resp = client.post("/auth/senha", json={"senha_atual": "senha123", "senha_nova": "nova456"}, headers=headers)
    assert resp.status_code == 200

    assert client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "senha123"}).status_code == 401
    assert client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "nova456"}).status_code == 200


def test_trocar_senha_com_senha_atual_errada(client, db):
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "senha123"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    resp = client.post("/auth/senha", json={"senha_atual": "errada", "senha_nova": "nova456"}, headers=headers)
    assert resp.status_code == 401


def test_usuario_inativo_nao_loga(client, db):
    usuario = _criar_usuario(db, senha="senha123")
    usuario.ativo = False
    db.commit()
    resp = client.post("/auth/login", json={"email": "fulano@teste.com", "senha": "senha123"})
    assert resp.status_code == 401


def test_login_com_email_mal_formado_e_recusado(client, db):
    """M34: o campo de e-mail na API é validado por formato (EmailStr) —
    uma string sem "@" não é mais aceita como e-mail."""
    resp = client.post("/auth/login", json={"email": "nao-e-um-email", "senha": "x"})
    assert resp.status_code == 422
