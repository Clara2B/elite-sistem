"""Páginas HTML (Fase 6) — autenticação por cookie, navegação e permissões.
Testes de API JSON continuam em test_auth.py/test_permissoes.py; aqui só o
que é específico do fluxo de navegador (login por formulário, redirecionamento,
página 403)."""
from datetime import date

from app.auth import hash_senha
from app.models import EmpresaCliente, Laudo, Setor, Usuario, UsuarioSetor


def test_login_form_carrega(client):
    resposta = client.get("/login")
    assert resposta.status_code == 200
    assert "Entrar" in resposta.text


def test_pagina_protegida_sem_login_redireciona(client):
    resposta = client.get("/app/processos", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


def test_login_senha_errada_mostra_erro(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa")))
    db.commit()
    resposta = client.post("/login", data={"email": "fulano@teste.local", "senha": "errada"})
    assert resposta.status_code == 401
    assert "incorretos" in resposta.text


def test_login_certo_seta_cookie_e_leva_ao_dashboard(client, db):
    db.add(Usuario(nome="Fulano de Tal", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()

    resposta = client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"}, follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"
    assert "sessao" in resposta.cookies

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Fulano" in dashboard.text
    assert "Usuários" in dashboard.text  # admin vê o módulo de usuários no menu


def test_usuario_sem_papel_global_nao_ve_usuarios_no_menu_e_leva_403(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()

    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    dashboard = client.get("/")
    assert "Usuários" not in dashboard.text

    resposta = client.get("/app/usuarios")
    assert resposta.status_code == 403
    assert "restrit" in resposta.text.lower()


def test_logout_limpa_sessao(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})
    assert client.get("/").status_code == 200

    resposta = client.post("/logout", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"

    resposta = client.get("/app/processos", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


def test_pdf_via_cookie_de_sessao_funciona_sem_bearer(client, db):
    """O mesmo cookie que autentica as páginas HTML também autentica a API
    JSON usada por elas (ex.: o link "Baixar PDF") — ver app/auth.py
    `_extrair_token`."""
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.get("/processos/relatorio.pdf?periodo_ini=2026-01-01&periodo_fim=2026-01-31")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert "attachment" in resposta.headers["content-disposition"]


def test_empresas_admin_cria_edita_e_desativa(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.post("/app/empresas", data={"nome": "Absoluta Teste", "cnpj": "11.111.111/0001-11"})
    assert resposta.status_code == 200
    assert "Absoluta Teste" in resposta.text
    assert "11.111.111" in resposta.text

    empresa_id = client.get("/empresas").json()[0]["id"]

    resposta = client.post(f"/app/empresas/{empresa_id}", data={"nome": "Absoluta Editada", "cnpj": "22.222.222/0001-22"})
    assert resposta.status_code == 200
    assert "Absoluta Editada" in resposta.text
    assert "22.222.222" in resposta.text

    resposta = client.post(f"/app/empresas/{empresa_id}/ativo?ativo=false", follow_redirects=False)
    assert resposta.status_code == 303
    dados = client.get("/empresas").json()
    assert dados[0]["ativo"] is False


def test_empresas_nome_duplicado_mostra_erro(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    client.post("/app/empresas", data={"nome": "Duplicada Ltda"})
    resposta = client.post("/app/empresas", data={"nome": "Duplicada Ltda"})
    assert resposta.status_code == 400
    assert "já existe" in resposta.text.lower()


def test_empresas_exclusao_definitiva_funciona_sem_vinculos(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    client.post("/app/empresas", data={"nome": "Excluível Ltda"})
    empresa_id = next(e["id"] for e in client.get("/empresas").json() if e["nome"] == "Excluível Ltda")

    resposta = client.post(f"/app/empresas/{empresa_id}/excluir", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/empresas?mensagem=")

    ids = [e["id"] for e in client.get("/empresas").json()]
    assert empresa_id not in ids


def test_empresas_exclusao_bloqueada_se_tiver_laudo_vinculado(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    empresa = EmpresaCliente(nome="Com Laudo Ltda")
    db.add(empresa)
    db.flush()
    db.add(Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="Perícia", data=date(2026, 1, 10), status="SOLICITACAO"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.post(f"/app/empresas/{empresa.id}/excluir", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/empresas?erro=")

    ids = [e["id"] for e in client.get("/empresas").json()]
    assert empresa.id in ids


def test_empresas_pagina_restrita_a_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    resposta = client.get("/app/empresas")
    assert resposta.status_code == 403


def test_erro_nao_tratado_em_rota_html_mostra_pagina_estilizada(client, db, monkeypatch):
    """A Clara reportou 'Internal Server Error' em branco ao importar
    audiências (era StringDataRightTruncation, já corrigido) — mas qualquer
    erro inesperado numa rota de tela merece a mesma página estilizada, não
    o crash cru do servidor. Simula um erro genérico (não é o bug real, só
    prova que o handler funciona pra qualquer exceção não tratada)."""
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    import app.web.routes_audiencias as rotas

    def _quebra(*args, **kwargs):
        raise RuntimeError("erro inesperado simulado")

    monkeypatch.setattr(rotas.audiencias_service, "importar_planilha", _quebra)

    # Starlette registra um handler pra `Exception` na camada mais externa
    # (ServerErrorMiddleware) — funciona certinho contra um navegador/uvicorn
    # de verdade (devolve a resposta certa pro cliente), mas o TestClient por
    # padrão (`raise_server_exceptions=True`) relança a exceção mesmo assim,
    # como um alarme pra bug não tratado. Aqui o "não tratado" é
    # intencional — o teste é sobre o handler, não sobre deixar passar.
    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    cliente_sem_relancar = TestClient(fastapi_app, raise_server_exceptions=False)
    cliente_sem_relancar.cookies = client.cookies

    resposta = cliente_sem_relancar.post(
        "/app/audiencias/import",
        files={"arquivo": ("planilha.xlsx", b"conteudo", "application/vnd.ms-excel")},
    )
    assert resposta.status_code == 500
    assert "algo deu errado" in resposta.text.lower()
    assert "internal server error" not in resposta.text.lower()
    assert "ELITE SISTEM" in resposta.text  # página da marca, não o crash cru


def test_erro_nao_tratado_em_rota_json_devolve_json(client, admin_token, monkeypatch):
    import app.api.empresas as api_empresas

    def _quebra(*args, **kwargs):
        raise RuntimeError("erro inesperado simulado")

    monkeypatch.setattr(api_empresas, "listar_empresas", _quebra)

    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    cliente_sem_relancar = TestClient(fastapi_app, raise_server_exceptions=False)
    resposta = cliente_sem_relancar.get("/empresas", headers={"Authorization": f"Bearer {admin_token}"})
    assert resposta.status_code == 500
    assert resposta.headers["content-type"].startswith("application/json")


def test_apagar_todos_laudos_via_web_exige_admin(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    empresa = EmpresaCliente(nome="ABSOLUTA")
    db.add(empresa)
    db.flush()
    db.add(Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25), nome_cliente="Fulano", status="SOLICITAÇÃO"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.post("/app/laudos/apagar-tudo", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/laudos?mensagem=")
    assert db.query(Laudo).count() == 0


def test_apagar_todos_laudos_via_web_bloqueado_para_nao_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    empresa = EmpresaCliente(nome="ABSOLUTA")
    db.add(empresa)
    db.flush()
    db.add(Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25), nome_cliente="Fulano", status="SOLICITAÇÃO"))
    db.commit()
    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    resposta = client.post("/app/laudos/apagar-tudo")
    assert resposta.status_code == 403
    assert db.query(Laudo).count() == 1  # nada foi apagado
