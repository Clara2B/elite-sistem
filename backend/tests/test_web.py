"""Páginas HTML (Fase 6) — autenticação por cookie, navegação e permissões.
Testes de API JSON continuam em test_auth.py/test_permissoes.py; aqui só o
que é específico do fluxo de navegador (login por formulário, redirecionamento,
página 403)."""
from datetime import date

from sqlalchemy import select

from app.auth import hash_senha
from app.models import (
    Audiencia,
    Cobranca,
    EmpresaCliente,
    EventoProcesso,
    Laudo,
    Operadora,
    Processo,
    Setor,
    SetorModulo,
    Usuario,
    UsuarioSetor,
)


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
    assert "Configuração" in dashboard.text  # admin vê a área administrativa no menu


def test_usuario_sem_papel_global_nao_ve_configuracao_no_menu_e_leva_403(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()

    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    dashboard = client.get("/")
    assert "Configuração" not in dashboard.text

    resposta = client.get("/app/usuarios")
    assert resposta.status_code == 403
    assert "restrit" in resposta.text.lower()


def test_admin_edita_usuario_pela_tela(client, db):
    admin = Usuario(nome="Admin", email="admin.web@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR")
    db.add(admin)
    alvo = Usuario(nome="Fulana", email="fulana.web@teste.local", senha_hash=hash_senha("x"))
    db.add(alvo)
    db.commit()
    db.refresh(alvo)

    client.post("/login", data={"email": "admin.web@teste.local", "senha": "certa"})

    resposta = client.post(
        f"/app/usuarios/{alvo.id}",
        data={"nome": "Fulana de Tal", "email": "fulana.editada@teste.local", "papel_global": ""},
    )
    assert resposta.status_code == 200
    assert "atualizado" in resposta.text
    assert "Fulana de Tal" in resposta.text
    assert "fulana.editada@teste.local" in resposta.text


def test_edicao_pela_tela_nao_pode_deixar_sistema_sem_admin(client, db):
    admin = Usuario(nome="Admin", email="unico.admin@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR")
    db.add(admin)
    db.commit()
    db.refresh(admin)

    client.post("/login", data={"email": "unico.admin@teste.local", "senha": "certa"})

    resposta = client.post(
        f"/app/usuarios/{admin.id}",
        data={"nome": "Admin", "email": "unico.admin@teste.local", "papel_global": ""},
    )
    assert resposta.status_code == 400
    assert "último administrador" in resposta.text
    db.refresh(admin)
    assert admin.papel_global == "ADMIN_SUPERIOR"


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


def test_empresas_exclusao_com_destino_reatribui_e_exclui(client, db):
    db.add(Usuario(nome="Fulano", email="fulano.mover@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    origem = EmpresaCliente(nome="Origem Com Laudo Ltda")
    destino = EmpresaCliente(nome="Destino Ltda")
    db.add(origem)
    db.add(destino)
    db.flush()
    laudo = Laudo(empresa_cliente_id=origem.id, tipo_laudo_nome="Perícia", data=date(2026, 1, 10), status="SOLICITACAO")
    db.add(laudo)
    db.commit()
    client.post("/login", data={"email": "fulano.mover@teste.local", "senha": "certa"})

    resposta = client.post(
        f"/app/empresas/{origem.id}/excluir", data={"empresa_destino_id": str(destino.id)}, follow_redirects=False
    )
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/empresas?mensagem=")

    ids = [e["id"] for e in client.get("/empresas").json()]
    assert origem.id not in ids
    db.refresh(laudo)
    assert laudo.empresa_cliente_id == destino.id


def test_sincronizar_lista_oficial_via_web_exige_admin(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.add(EmpresaCliente(nome="EMPRESA FORA DA LISTA"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.post("/app/empresas/sincronizar-lista-oficial", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/empresas?mensagem=")

    nomes = {e["nome"] for e in client.get("/empresas").json()}
    assert "EMPRESA FORA DA LISTA" not in nomes
    assert "ABSOLUTA" in nomes


def test_sincronizar_lista_oficial_via_web_bloqueado_para_nao_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    resposta = client.post("/app/empresas/sincronizar-lista-oficial")
    assert resposta.status_code == 403


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


def test_excluir_empresas_inativas_via_web(client, db):
    admin = Usuario(nome="Admin", email="admin.inativas@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR")
    db.add(admin)
    ativa = EmpresaCliente(nome="ATIVA WEB")
    inativa = EmpresaCliente(nome="INATIVA WEB", ativo=False)
    db.add_all([ativa, inativa])
    db.commit()
    client.post("/login", data={"email": "admin.inativas@teste.local", "senha": "certa"})

    resposta = client.post("/app/empresas/excluir-inativas", follow_redirects=False)
    assert resposta.status_code == 303
    assert "mensagem=" in resposta.headers["location"]

    assert db.get(EmpresaCliente, ativa.id) is not None
    assert db.get(EmpresaCliente, inativa.id) is None


def test_excluir_empresas_inativas_bloqueado_para_nao_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab.inativas@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    inativa = EmpresaCliente(nome="INATIVA PROTEGIDA", ativo=False)
    db.add(inativa)
    db.commit()
    client.post("/login", data={"email": "colab.inativas@teste.local", "senha": "certa"})

    resposta = client.post("/app/empresas/excluir-inativas")
    assert resposta.status_code == 403
    assert db.get(EmpresaCliente, inativa.id) is not None


def test_funcionarios_admin_cria_edita_e_desativa(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.post("/app/funcionarios", data={"nome": "Danilo Teste"})
    assert resposta.status_code == 200
    assert "Danilo Teste" in resposta.text

    funcionario_id = client.get("/funcionarios").json()[0]["id"]

    resposta = client.post(f"/app/funcionarios/{funcionario_id}", data={"nome": "Danilo Editado"})
    assert resposta.status_code == 200
    assert "Danilo Editado" in resposta.text

    resposta = client.post(f"/app/funcionarios/{funcionario_id}/ativo?ativo=false", follow_redirects=False)
    assert resposta.status_code == 303
    dados = client.get("/funcionarios").json()
    assert dados[0]["ativo"] is False


def test_funcionarios_nome_duplicado_mostra_erro(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    client.post("/app/funcionarios", data={"nome": "Duplicado"})
    resposta = client.post("/app/funcionarios", data={"nome": "Duplicado"})
    assert resposta.status_code == 400
    assert "já existe" in resposta.text.lower()


def test_funcionarios_exclusao_definitiva_funciona(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    client.post("/app/funcionarios", data={"nome": "Excluível"})
    funcionario_id = next(f["id"] for f in client.get("/funcionarios").json() if f["nome"] == "Excluível")

    resposta = client.post(f"/app/funcionarios/{funcionario_id}/excluir", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/funcionarios?mensagem=")

    ids = [f["id"] for f in client.get("/funcionarios").json()]
    assert funcionario_id not in ids


def test_funcionarios_pagina_restrita_a_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    resposta = client.get("/app/funcionarios")
    assert resposta.status_code == 403


def test_relatorio_processos_geral_mostra_secao_por_empresa(client, db):
    """Bloco 1 (2026-09-25): tipo "Geral" — uma seção por empresa, com as
    duas partes (Nº processo/Evento/Fatal e Cliente/Nº processo/Último
    evento/Última observação). Bloco 4 (2026-09-28): sem a coluna
    Assistente — o filtro continua funcionando, só não aparece mais."""
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    empresa1 = EmpresaCliente(nome="ABSOLUTA")
    empresa2 = EmpresaCliente(nome="ALFA")
    db.add_all([empresa1, empresa2])
    db.flush()
    p1 = Processo(numero_processo="5012298-14.2025.8.13.0231", empresa_cliente_id=empresa1.id, nome_cliente="Fulano", assistente="DANILO")
    p2 = Processo(numero_processo="6012298-14.2025.8.13.0232", empresa_cliente_id=empresa2.id, nome_cliente="Beltrano", assistente="DANILO")
    db.add_all([p1, p2])
    db.flush()
    db.add_all(
        [
            EventoProcesso(processo_id=p1.id, data=date(2026, 9, 5), tipo_evento_nome="CUSTAS", prazo_fatal=True),
            EventoProcesso(processo_id=p2.id, data=date(2026, 9, 5), tipo_evento_nome="DOCUMENTOS"),
        ]
    )
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.get(
        "/app/processos",
        params={"periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30", "tipo": "geral"},
    )
    assert resposta.status_code == 200
    assert "ABSOLUTA — 1 processo(s)" in resposta.text
    assert "ALFA — 1 processo(s)" in resposta.text
    assert "DANILO" not in resposta.text  # Bloco 4: assistente não aparece mais no relatório
    assert "<td>Sim</td>" in resposta.text  # fatal da ABSOLUTA
    assert "<td>Não</td>" in resposta.text  # fatal da ALFA
    assert "Fulano" in resposta.text  # Parte 2 (resumo por cliente)


def test_relatorio_processos_por_empresa_filtra_uma_so(client, db):
    """Bloco 1 (2026-09-25): tipo "Por empresa" — só a empresa selecionada.
    Bloco 4 (2026-09-28): sem a coluna Assistente."""
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    empresa1 = EmpresaCliente(nome="ABSOLUTA")
    empresa2 = EmpresaCliente(nome="ALFA")
    db.add_all([empresa1, empresa2])
    db.flush()
    p1 = Processo(numero_processo="5012298-14.2025.8.13.0231", empresa_cliente_id=empresa1.id, nome_cliente="Fulano", assistente="DANILO")
    p2 = Processo(numero_processo="6012298-14.2025.8.13.0232", empresa_cliente_id=empresa2.id, nome_cliente="Beltrano", assistente="DANILO")
    db.add_all([p1, p2])
    db.flush()
    db.add_all(
        [
            EventoProcesso(processo_id=p1.id, data=date(2026, 9, 5), tipo_evento_nome="CUSTAS"),
            EventoProcesso(processo_id=p2.id, data=date(2026, 9, 5), tipo_evento_nome="CUSTAS"),
        ]
    )
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.get(
        "/app/processos",
        params={"periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30", "tipo": "empresa", "empresa": "ABSOLUTA"},
    )
    assert resposta.status_code == 200
    assert "ABSOLUTA — 1 processo(s)" in resposta.text
    assert "Beltrano" not in resposta.text  # processo da ALFA não aparece
    assert "DANILO" not in resposta.text  # Bloco 4: assistente não aparece mais no relatório
    assert '<div class="tabela-wrap">' in resposta.text  # Bloco 5: sem rolagem horizontal da página


def test_relatorio_processos_sem_resultado_mostra_mensagem_amigavel(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.get(
        "/app/processos",
        params={"periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30", "tipo": "geral"},
    )
    assert resposta.status_code == 200
    assert "Nenhum processo encontrado nesse período." in resposta.text


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


def test_laudos_resumo_por_assessoria_sem_empresa_cobre_todas(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    absoluta = EmpresaCliente(nome="ABSOLUTA")
    hunting = EmpresaCliente(nome="HUNTING")
    db.add_all([absoluta, hunting])
    db.flush()
    db.add_all(
        [
            Laudo(empresa_cliente_id=absoluta.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25), nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=hunting.id, tipo_laudo_nome="IMÓVEL", data=date(2026, 1, 25), nome_cliente="Beltrano", status="SOLICITAÇÃO"),
        ]
    )
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.get(
        "/app/laudos",
        params={"ano": 2026, "mes": 1, "status": "Solicitação + Corrigido (cobrança)"},
    )
    assert resposta.status_code == 200
    # cards visíveis (não mais fonte monoespaçada) — um <h2> por assessoria
    assert "<h2>ABSOLUTA</h2>" in resposta.text
    assert "<h2>HUNTING</h2>" in resposta.text
    assert "data-copiar-resumo" in resposta.text  # botão "Copiar resumo"
    assert "<textarea" not in resposta.text  # não é mais o campo de texto simples de antes


def test_laudos_resumo_por_assessoria_sempre_cobre_todas_mesmo_com_empresa_filtrada(client, db):
    """Bloco 4 (2026-09-25, a pedido da Clara): o resumo é sempre geral —
    filtrar o relatório detalhado por uma empresa não deve mais restringir
    o resumo, diferente do comportamento anterior (2026-09-24)."""
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    absoluta = EmpresaCliente(nome="ABSOLUTA")
    hunting = EmpresaCliente(nome="HUNTING")
    db.add_all([absoluta, hunting])
    db.flush()
    db.add_all(
        [
            Laudo(empresa_cliente_id=absoluta.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25), nome_cliente="Fulano", status="SOLICITAÇÃO"),
            Laudo(empresa_cliente_id=hunting.id, tipo_laudo_nome="IMÓVEL", data=date(2026, 1, 25), nome_cliente="Beltrano", status="SOLICITAÇÃO"),
        ]
    )
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.get(
        "/app/laudos",
        params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 1, "status": "Solicitação + Corrigido (cobrança)"},
    )
    assert resposta.status_code == 200
    assert "<h2>ABSOLUTA</h2>" in resposta.text
    assert "<h2>HUNTING</h2>" in resposta.text  # resumo continua geral mesmo filtrando o relatório
    # relatório detalhado da empresa também aparece, como já acontecia antes
    assert "AUTO" in resposta.text


def test_apagar_todas_audiencias_via_web_exige_admin(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    empresa = EmpresaCliente(nome="ABSOLUTA")
    db.add(empresa)
    db.flush()
    db.add(Audiencia(empresa_cliente_id=empresa.id, nome_cliente="Fulano", data_recebimento=date(2026, 1, 25)))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.post("/app/audiencias/apagar-tudo", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/audiencias?mensagem=")
    assert db.query(Audiencia).count() == 0


def test_apagar_todas_audiencias_via_web_bloqueado_para_nao_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    empresa = EmpresaCliente(nome="ABSOLUTA")
    db.add(empresa)
    db.flush()
    db.add(Audiencia(empresa_cliente_id=empresa.id, nome_cliente="Fulano", data_recebimento=date(2026, 1, 25)))
    db.commit()
    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    resposta = client.post("/app/audiencias/apagar-tudo")
    assert resposta.status_code == 403
    assert db.query(Audiencia).count() == 1  # nada foi apagado


def test_apagar_todas_pendencias_via_web_exige_admin(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    empresa = EmpresaCliente(nome="ABSOLUTA")
    db.add(empresa)
    db.flush()
    db.add(Cobranca(empresa_cliente_id=empresa.id, data=date(2026, 1, 25), tipo_cobranca="MENSALIDADE",
                     cobrador="ELITE", valor=100.0, status_pagamento="Não"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.post("/app/pendencias/apagar-tudo", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/pendencias?mensagem=")
    assert db.query(Cobranca).count() == 0


def test_apagar_todas_pendencias_via_web_bloqueado_para_nao_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    empresa = EmpresaCliente(nome="ABSOLUTA")
    db.add(empresa)
    db.flush()
    db.add(Cobranca(empresa_cliente_id=empresa.id, data=date(2026, 1, 25), tipo_cobranca="MENSALIDADE",
                     cobrador="ELITE", valor=100.0, status_pagamento="Não"))
    db.commit()
    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    resposta = client.post("/app/pendencias/apagar-tudo")
    assert resposta.status_code == 403
    assert db.query(Cobranca).count() == 1  # nada foi apagado


def test_apagar_todos_processos_via_web_exige_admin(client, db):
    db.add(Usuario(nome="Fulano", email="fulano@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    empresa = EmpresaCliente(nome="ABSOLUTA")
    db.add(empresa)
    db.flush()
    processo = Processo(numero_processo="5012298-14.2025.8.13.0231", empresa_cliente_id=empresa.id, nome_cliente="Fulano")
    db.add(processo)
    db.flush()
    db.add(EventoProcesso(processo_id=processo.id, data=date(2026, 1, 25), tipo_evento_nome="CUSTAS"))
    db.commit()
    client.post("/login", data={"email": "fulano@teste.local", "senha": "certa"})

    resposta = client.post("/app/processos/apagar-tudo", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/app/processos?mensagem=")
    assert db.query(Processo).count() == 0
    assert db.query(EventoProcesso).count() == 0


def test_apagar_todos_processos_via_web_bloqueado_para_nao_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    empresa = EmpresaCliente(nome="ABSOLUTA")
    db.add(empresa)
    db.flush()
    processo = Processo(numero_processo="5012298-14.2025.8.13.0231", empresa_cliente_id=empresa.id, nome_cliente="Fulano")
    db.add(processo)
    db.commit()
    client.post("/login", data={"email": "colab@teste.local", "senha": "certa"})

    resposta = client.post("/app/processos/apagar-tudo")
    assert resposta.status_code == 403
    assert db.query(Processo).count() == 1  # nada foi apagado


def test_configuracao_lista_as_4_areas_administrativas(client, db):
    admin = Usuario(nome="Admin", email="admin.config@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR")
    db.add(admin)
    db.commit()
    client.post("/login", data={"email": "admin.config@teste.local", "senha": "certa"})

    resposta = client.get("/app/configuracao")
    assert resposta.status_code == 200
    for rotulo in ("Usuários", "Empresas-clientes", "Assistentes", "Setores"):
        assert rotulo in resposta.text


def test_configuracao_bloqueada_para_nao_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab.config@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    client.post("/login", data={"email": "colab.config@teste.local", "senha": "certa"})

    assert client.get("/app/configuracao").status_code == 403


def test_menu_destaca_configuracao_em_qualquer_tela_administrativa(client, db):
    admin = Usuario(nome="Admin", email="admin.ativo@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR")
    db.add(admin)
    db.commit()
    client.post("/login", data={"email": "admin.ativo@teste.local", "senha": "certa"})

    for url in ("/app/usuarios", "/app/empresas", "/app/funcionarios", "/app/setores"):
        resposta = client.get(url)
        assert resposta.status_code == 200
        assert 'href="/app/configuracao" class="ativo"' in resposta.text
        assert "Voltar à Configuração" in resposta.text


def test_admin_cadastra_e_edita_setor_pela_tela(client, db):
    admin = Usuario(nome="Admin", email="admin.setor@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR")
    db.add(admin)
    db.commit()
    client.post("/login", data={"email": "admin.setor@teste.local", "senha": "certa"})

    operadora = db.query(Setor).first().operadora
    resposta = client.post("/app/setores", data={"nome": "Cobrança", "operadora_id": operadora.id})
    assert resposta.status_code == 200
    assert "Cobrança" in resposta.text

    novo = db.scalar(select(Setor).where(Setor.nome == "Cobrança"))
    assert novo is not None

    resposta = client.post(f"/app/setores/{novo.id}", data={"nome": "Cobrança e Financeiro", "operadora_id": operadora.id})
    assert resposta.status_code == 200
    assert "Cobrança e Financeiro" in resposta.text

    resposta = client.post(f"/app/setores/{novo.id}/ativo?ativo=false", follow_redirects=False)
    assert resposta.status_code == 303
    db.refresh(novo)
    assert novo.ativo is False


def test_setores_bloqueado_para_nao_admin(client, db):
    setor = db.query(Setor).first()
    usuario = Usuario(nome="Colaboradora", email="colab.setor@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    client.post("/login", data={"email": "colab.setor@teste.local", "senha": "certa"})

    assert client.get("/app/setores").status_code == 403
    assert client.post("/app/setores", data={"nome": "X", "operadora_id": setor.operadora_id}).status_code == 403


def test_admin_restringe_abas_do_setor_pela_tela(client, db):
    admin = Usuario(nome="Admin", email="admin.modulos@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR")
    db.add(admin)
    db.commit()
    client.post("/login", data={"email": "admin.modulos@teste.local", "senha": "certa"})

    operadora = db.scalar(select(Operadora).where(Operadora.nome == "ELITE"))
    resposta = client.post(
        "/app/setores",
        data={
            "nome": "Restrito Web",
            "operadora_id": str(operadora.id),
            "restringir_modulos": "true",
            "modulos": ["LAUDOS"],
        },
    )
    assert resposta.status_code == 200
    novo = db.scalar(select(Setor).where(Setor.nome == "Restrito Web"))
    assert novo is not None
    modulos = {m.modulo for m in db.scalars(select(SetorModulo).where(SetorModulo.setor_id == novo.id))}
    assert modulos == {"LAUDOS"}

    # tira a restrição de novo (checkbox "restringir_modulos" ausente = acesso total)
    resposta = client.post(f"/app/setores/{novo.id}", data={"nome": "Restrito Web", "operadora_id": str(operadora.id)})
    assert resposta.status_code == 200
    modulos = list(db.scalars(select(SetorModulo).where(SetorModulo.setor_id == novo.id)))
    assert modulos == []


def test_menu_nao_mostra_processos_para_setor_restrito_a_laudos(client, db):
    setor = db.scalar(select(Setor).where(Setor.nome == "Financeiro", Setor.operadora.has(nome="ELITE")))
    db.add(SetorModulo(setor_id=setor.id, modulo="LAUDOS"))
    usuario = Usuario(nome="Colab", email="colab.menu@teste.local", senha_hash=hash_senha("certa"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    client.post("/login", data={"email": "colab.menu@teste.local", "senha": "certa"})

    resposta = client.get("/app/laudos")
    assert resposta.status_code == 200
    assert 'href="/app/processos"' not in resposta.text
    assert client.get("/app/processos", follow_redirects=False).status_code == 403


def test_modo_escuro_tem_botao_e_script_anti_flash(client, db):
    """Modo escuro (2026-09-28): o botão de alternar tema aparece nas
    páginas autenticadas, e o script que aplica o tema salvo antes da
    primeira pintura está presente tanto nelas quanto no login."""
    login = client.get("/login")
    assert "elite-sistem-tema" in login.text
    assert "data-alternar-tema" not in login.text  # sem sidebar, sem usuário logado

    db.add(Usuario(nome="Fulano", email="fulano.tema@teste.local", senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": "fulano.tema@teste.local", "senha": "certa"})

    dashboard = client.get("/")
    assert "data-alternar-tema" in dashboard.text
    assert "elite-sistem-tema" in dashboard.text
