"""Serviço e tela de Auditoria (2026-10-08, a pedido da Clara — "elevar o
nível do sistema com foco em otimização e produtividade"): o log já existia
desde o início (todo `registrar(...)` espalhado pelo projeto), só faltava
uma tela pra consultar."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.auth import hash_senha
from app.models import LogAuditoria, Usuario
from app.services.auditoria import (
    POR_PAGINA,
    acoes_distintas,
    humanizar_acao,
    listar,
    registrar,
)


def _usuario(db, nome="Fulana", email="fulana@teste.local") -> Usuario:
    usuario = Usuario(nome=nome, email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR")
    db.add(usuario)
    db.commit()
    return usuario


def test_humanizar_acao():
    assert humanizar_acao("EXCLUIU_EMPRESAS_EM_MASSA") == "Excluiu empresas em massa"
    assert humanizar_acao("LOGIN") == "Login"
    assert humanizar_acao("") == ""


def test_listar_mais_recente_primeiro(db):
    usuario = _usuario(db)
    registrar(db, usuario, "CRIOU_EMPRESA", entidade="empresa_cliente", entidade_id=1)
    registrar(db, usuario, "EDITOU_EMPRESA", entidade="empresa_cliente", entidade_id=1)

    resultado = listar(db)

    assert [r.acao for r in resultado.registros] == ["EDITOU_EMPRESA", "CRIOU_EMPRESA"]
    assert resultado.total_registros == 2
    assert resultado.total_paginas == 1


def test_listar_filtra_por_usuario(db):
    fulana = _usuario(db, "Fulana", "fulana2@teste.local")
    beltrano = _usuario(db, "Beltrano", "beltrano@teste.local")
    registrar(db, fulana, "LOGIN")
    registrar(db, beltrano, "LOGIN")

    resultado = listar(db, usuario_id=fulana.id)

    assert resultado.total_registros == 1
    assert resultado.registros[0].usuario_id == fulana.id


def test_listar_filtra_por_acao(db):
    usuario = _usuario(db)
    registrar(db, usuario, "LOGIN")
    registrar(db, usuario, "LOGOUT")

    resultado = listar(db, acao="LOGOUT")

    assert resultado.total_registros == 1
    assert resultado.registros[0].acao == "LOGOUT"


def test_listar_filtra_por_periodo(db):
    usuario = _usuario(db)
    registrar(db, usuario, "LOGIN")
    registro_antigo = db.query(LogAuditoria).order_by(LogAuditoria.id.desc()).first()
    registro_antigo.criado_em = datetime.utcnow() - timedelta(days=10)
    db.commit()
    registrar(db, usuario, "LOGOUT")

    hoje = date.today()
    resultado = listar(db, data_inicio=hoje, data_fim=hoje)

    assert resultado.total_registros == 1
    assert resultado.registros[0].acao == "LOGOUT"


def test_listar_pagina_corretamente(db):
    usuario = _usuario(db)
    for _ in range(POR_PAGINA + 5):
        registrar(db, usuario, "LOGIN")

    pagina_1 = listar(db, pagina=1)
    pagina_2 = listar(db, pagina=2)

    assert len(pagina_1.registros) == POR_PAGINA
    assert len(pagina_2.registros) == 5
    assert pagina_1.total_paginas == 2
    assert pagina_1.total_registros == POR_PAGINA + 5
    # sem sobreposição entre as páginas
    ids_pagina_1 = {r.id for r in pagina_1.registros}
    ids_pagina_2 = {r.id for r in pagina_2.registros}
    assert ids_pagina_1.isdisjoint(ids_pagina_2)


def test_listar_pagina_alem_do_fim_volta_pra_ultima(db):
    usuario = _usuario(db)
    registrar(db, usuario, "LOGIN")

    resultado = listar(db, pagina=999)

    assert resultado.pagina == 1


def test_acoes_distintas_sem_duplicatas_e_ordenado(db):
    usuario = _usuario(db)
    registrar(db, usuario, "LOGOUT")
    registrar(db, usuario, "LOGIN")
    registrar(db, usuario, "LOGIN")

    assert acoes_distintas(db) == ["LOGIN", "LOGOUT"]


def _logar_admin(db, client, email="admin.auditoria@teste.local"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _logar_colaborador(db, client, email="colab.auditoria@teste.local"):
    db.add(Usuario(nome="Colaborador", email=email, senha_hash=hash_senha("certa")))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_tela_exige_admin(client, db):
    _logar_colaborador(db, client)
    resposta = client.get("/app/auditoria", follow_redirects=False)
    assert resposta.status_code != 200


def test_tela_sem_login_redireciona(client, db):
    resposta = client.get("/app/auditoria", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


def test_tela_lista_registros_e_filtros(client, db):
    _logar_admin(db, client)
    registrar(db, None, "CRIOU_EMPRESA", entidade="empresa_cliente", detalhes="Empresa TESTE cadastrada.")

    resposta = client.get("/app/auditoria")

    assert resposta.status_code == 200
    assert "Criou empresa" in resposta.text
    assert "Empresa TESTE cadastrada." in resposta.text


def test_tela_filtra_por_acao_na_url(client, db):
    _logar_admin(db, client)
    registrar(db, None, "LOGIN")
    registrar(db, None, "LOGOUT")

    resposta = client.get("/app/auditoria", params={"acao": "LOGOUT"})

    assert resposta.status_code == 200
    assert "Registros (1)" in resposta.text


def test_tela_aceita_campos_de_filtro_vazios(client, db):
    """Bug real encontrado nesta sessão: o formulário de filtro é um GET
    normal — campos de data/usuário deixados em branco mandam string vazia
    ("") em vez de omitir o parâmetro, e FastAPI recusava (422) converter
    "" direto pra int/date. Reproduz exatamente a querystring que o
    navegador manda ao clicar em "Filtrar" sem preencher nada."""
    _logar_admin(db, client)

    resposta = client.get(
        "/app/auditoria",
        params={"usuario_id": "", "acao": "", "data_inicio": "", "data_fim": ""},
    )

    assert resposta.status_code == 200
    assert "Auditoria" in resposta.text
