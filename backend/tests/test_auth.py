from app.auth import hash_senha
from app.models import Usuario


def _criar_usuario(db, email="fulano@teste.local", senha="senha123", papel_global=None):
    usuario = Usuario(nome="Fulano", email=email, senha_hash=hash_senha(senha), papel_global=papel_global)
    db.add(usuario)
    db.commit()
    return usuario


def test_login_com_senha_certa(client, db):
    _criar_usuario(db, senha="senha123")
    resp = client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "senha123"})
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["usuario"]["email"] == "fulano@teste.local"


def test_login_com_senha_errada(client, db):
    _criar_usuario(db, senha="senha123")
    resp = client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "errada"})
    assert resp.status_code == 401


def test_login_usuario_inexistente(client):
    resp = client.post("/auth/login", json={"email": "ninguem@teste.local", "senha": "x"})
    assert resp.status_code == 401


def test_me_sem_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_com_token(client, db):
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "senha123"})
    token = login.json()["token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "fulano@teste.local"


def test_logout_invalida_o_token(client, db):
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "senha123"})
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_trocar_senha(client, db):
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "senha123"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    resp = client.post("/auth/senha", json={"senha_atual": "senha123", "senha_nova": "nova456"}, headers=headers)
    assert resp.status_code == 200

    assert client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "senha123"}).status_code == 401
    assert client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "nova456"}).status_code == 200


def test_trocar_senha_com_senha_atual_errada(client, db):
    _criar_usuario(db, senha="senha123")
    login = client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "senha123"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    resp = client.post("/auth/senha", json={"senha_atual": "errada", "senha_nova": "nova456"}, headers=headers)
    assert resp.status_code == 401


def test_usuario_inativo_nao_loga(client, db):
    usuario = _criar_usuario(db, senha="senha123")
    usuario.ativo = False
    db.commit()
    resp = client.post("/auth/login", json={"email": "fulano@teste.local", "senha": "senha123"})
    assert resp.status_code == 401
