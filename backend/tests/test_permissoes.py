from datetime import date

from sqlalchemy import select

from app.auth import criar_sessao, hash_senha, modulos_acessiveis
from app.models import Cobranca, Operadora, Setor, SetorModulo, Usuario, UsuarioSetor
from app.services.empresas import get_or_create_empresa


def _usuario_com_setor(db, operadora_nome: str, email: str) -> str:
    setor = db.scalar(select(Setor).where(Setor.nome == "Financeiro", Setor.operadora.has(nome=operadora_nome)))
    usuario = Usuario(nome="Colaborador", email=email, senha_hash=hash_senha("x"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel="COLABORADOR"))
    db.commit()
    return criar_sessao(db, usuario).token


def test_setor_elite_acessa_laudos_mas_nao_audiencias(client, db):
    token = _usuario_com_setor(db, "ELITE", "financeiro.elite@teste.local")
    headers = {"Authorization": f"Bearer {token}"}

    resp_laudos = client.get("/laudos/relatorio", params={"empresa": "X", "ano": 2026, "mes": 1}, headers=headers)
    assert resp_laudos.status_code in (404, 200)  # passou pela checagem de acesso (empresa pode não existir)

    resp_audiencias = client.get(
        "/audiencias/relatorio", params={"empresa": "X", "ano": 2026, "mes": 1, "quinzena": 1}, headers=headers
    )
    assert resp_audiencias.status_code == 403


def test_setor_eximia_acessa_audiencias_mas_nao_laudos(client, db):
    token = _usuario_com_setor(db, "EXIMIA", "financeiro.eximia@teste.local")
    headers = {"Authorization": f"Bearer {token}"}

    resp_laudos = client.get("/laudos/relatorio", params={"empresa": "X", "ano": 2026, "mes": 1}, headers=headers)
    assert resp_laudos.status_code == 403

    resp_audiencias = client.get(
        "/audiencias/relatorio", params={"empresa": "X", "ano": 2026, "mes": 1, "quinzena": 1}, headers=headers
    )
    assert resp_audiencias.status_code in (404, 200)


def test_pendencias_filtra_por_operadora_acessivel(client, db):
    empresa = get_or_create_empresa(db, "NOVA GLOBAL")
    db.add(
        Cobranca(
            empresa_cliente_id=empresa.id, data=date(2026, 1, 1), tipo_cobranca="MENSALIDADE",
            cobrador="ELITE", valor=100.0, status_pagamento="EM ATRASO",
        )
    )
    db.add(
        Cobranca(
            empresa_cliente_id=empresa.id, data=date(2026, 1, 2), tipo_cobranca="AUDIENCIA EXTRA",
            cobrador="EXIMIA", valor=50.0, status_pagamento="PENDENTE",
        )
    )
    db.commit()

    token = _usuario_com_setor(db, "ELITE", "financeiro.elite2@teste.local")
    resp = client.get(
        "/pendencias/mensagens", params={"empresa": "NOVA GLOBAL"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    cobradores = {m["cobrador"] for m in resp.json()}
    assert cobradores == {"ELITE"}  # não vê a pendência da EXIMIA


def test_admin_superior_acessa_os_dois(client, db, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    for rota, params in [
        ("/laudos/relatorio", {"empresa": "X", "ano": 2026, "mes": 1}),
        ("/audiencias/relatorio", {"empresa": "X", "ano": 2026, "mes": 1, "quinzena": 1}),
    ]:
        resp = client.get(rota, params=params, headers=headers)
        assert resp.status_code != 403


def test_rota_de_usuarios_exige_admin(client, db):
    token = _usuario_com_setor(db, "ELITE", "colaborador@teste.local")
    resp = client.get("/usuarios", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_cria_usuario(client, admin_token, db):
    setor = db.scalar(select(Setor).where(Setor.nome == "Doutores(as)"))
    resp = client.post(
        "/usuarios",
        json={
            "nome": "Dra. Fulana",
            "email": "dra.fulana@teste.local",
            "senha": "senha123",
            "setores": [{"setor_id": setor.id, "papel": "COLABORADOR"}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["setores"][0]["setor"] == "Doutores(as)"

    login = client.post("/auth/login", json={"email": "dra.fulana@teste.local", "senha": "senha123"})
    assert login.status_code == 200


def test_admin_edita_usuario(client, admin_token, db):
    setor = db.scalar(select(Setor).where(Setor.nome == "Doutores(as)"))
    criado = client.post(
        "/usuarios",
        json={"nome": "Dra. Fulana", "email": "fulana@teste.local", "senha": "senha123"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    resp = client.patch(
        f"/usuarios/{criado['id']}",
        json={
            "nome": "Dra. Fulana de Tal",
            "email": "fulana.novo@teste.local",
            "senha": "senha-nova",
            "setores": [{"setor_id": setor.id, "papel": "LIDER"}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Dra. Fulana de Tal"
    assert body["email"] == "fulana.novo@teste.local"
    assert body["setores"] == [{"setor_id": setor.id, "setor": "Doutores(as)", "operadora": "ELITE", "papel": "LIDER"}]

    # senha antiga não funciona mais, a nova sim
    assert client.post("/auth/login", json={"email": "fulana.novo@teste.local", "senha": "senha123"}).status_code == 401
    assert client.post("/auth/login", json={"email": "fulana.novo@teste.local", "senha": "senha-nova"}).status_code == 200


def test_edicao_sem_senha_mantem_a_senha_atual(client, admin_token, db):
    criado = client.post(
        "/usuarios",
        json={"nome": "Dra. Fulana", "email": "mantem@teste.local", "senha": "senha123"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    resp = client.patch(
        f"/usuarios/{criado['id']}",
        json={"nome": "Dra. Fulana", "email": "mantem@teste.local"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert client.post("/auth/login", json={"email": "mantem@teste.local", "senha": "senha123"}).status_code == 200


def test_edicao_nao_pode_deixar_sistema_sem_admin(client, admin_token, db):
    admin_id = db.scalar(select(Usuario.id).where(Usuario.email == "admin@teste.local"))
    resp = client.patch(
        f"/usuarios/{admin_id}",
        json={"nome": "Admin Teste", "email": "admin@teste.local", "papel_global": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "último administrador" in resp.json()["detail"]
    assert db.scalar(select(Usuario.papel_global).where(Usuario.id == admin_id)) == "ADMIN_SUPERIOR"


def test_edicao_permite_trocar_admin_se_houver_outro(client, admin_token, db):
    client.post(
        "/usuarios",
        json={"nome": "Segundo Admin", "email": "segundo@teste.local", "senha": "senha123", "papel_global": "ADMIN_TI"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    admin_id = db.scalar(select(Usuario.id).where(Usuario.email == "admin@teste.local"))

    resp = client.patch(
        f"/usuarios/{admin_id}",
        json={"nome": "Admin Teste", "email": "admin@teste.local", "papel_global": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["papel_global"] is None


# --- Seleção de abas (módulos) por setor (2026-09-28) ------------------------


def _usuario_no_setor(db, setor_id: int, email: str) -> Usuario:
    usuario = Usuario(nome="Colaborador", email=email, senha_hash=hash_senha("x"))
    db.add(usuario)
    db.flush()
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor_id, papel="COLABORADOR"))
    db.commit()
    return usuario


def test_modulos_acessiveis_admin_ve_todos(db, admin_token):
    admin = db.scalar(select(Usuario).where(Usuario.email == "admin@teste.local"))
    assert modulos_acessiveis(db, admin) == {"LAUDOS", "PROCESSOS", "AUDIENCIAS", "CARTAS", "PENDENCIAS"}


def test_modulos_acessiveis_setor_sem_configuracao_libera_tudo_da_operadora(db):
    setor = db.scalar(select(Setor).where(Setor.nome == "Financeiro", Setor.operadora.has(nome="ELITE")))
    usuario = _usuario_no_setor(db, setor.id, "setor.sem-config@teste.local")
    assert modulos_acessiveis(db, usuario) == {"LAUDOS", "PROCESSOS", "PENDENCIAS"}


def test_modulos_acessiveis_setor_restrito_fica_so_com_o_configurado(db):
    setor = db.scalar(select(Setor).where(Setor.nome == "Financeiro", Setor.operadora.has(nome="ELITE")))
    db.add(SetorModulo(setor_id=setor.id, modulo="LAUDOS"))
    db.commit()
    usuario = _usuario_no_setor(db, setor.id, "setor.restrito@teste.local")
    assert modulos_acessiveis(db, usuario) == {"LAUDOS"}


def test_modulos_acessiveis_uniao_de_varios_setores(db):
    setor_eximia = db.scalar(select(Setor).where(Setor.nome == "Financeiro", Setor.operadora.has(nome="EXIMIA")))
    setor_elite = db.scalar(select(Setor).where(Setor.nome == "Financeiro", Setor.operadora.has(nome="ELITE")))
    db.add(SetorModulo(setor_id=setor_eximia.id, modulo="CARTAS"))
    db.commit()
    usuario = _usuario_no_setor(db, setor_eximia.id, "setor.multiplo@teste.local")
    db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor_elite.id, papel="COLABORADOR"))
    db.commit()
    # EXIMIA restrito a CARTAS + ELITE sem configuração (tudo da operadora)
    assert modulos_acessiveis(db, usuario) == {"CARTAS", "LAUDOS", "PROCESSOS", "PENDENCIAS"}


def test_setor_restrito_a_laudos_nao_acessa_processos_nem_pendencias(client, db):
    setor = db.scalar(select(Setor).where(Setor.nome == "Financeiro", Setor.operadora.has(nome="ELITE")))
    db.add(SetorModulo(setor_id=setor.id, modulo="LAUDOS"))
    db.commit()
    usuario = _usuario_no_setor(db, setor.id, "restrito.laudos@teste.local")
    token = criar_sessao(db, usuario).token
    headers = {"Authorization": f"Bearer {token}"}

    resp_laudos = client.get("/laudos/relatorio", params={"empresa": "X", "ano": 2026, "mes": 1}, headers=headers)
    assert resp_laudos.status_code in (404, 200)

    resp_processos = client.get(
        "/processos/relatorio", params={"periodo_ini": "2026-01-01", "periodo_fim": "2026-01-31"}, headers=headers
    )
    assert resp_processos.status_code == 403

    resp_pendencias = client.get("/pendencias/mensagens", params={"empresa": "X"}, headers=headers)
    assert resp_pendencias.status_code == 403


def test_admin_cria_setor_ja_restrito_a_modulos(client, admin_token, db):
    operadora = db.scalar(select(Operadora).where(Operadora.nome == "ELITE"))
    resp = client.post(
        "/setores",
        json={"nome": "Só Laudos", "operadora_id": operadora.id, "modulos": ["LAUDOS"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["modulos"] == ["LAUDOS"]


def test_admin_edita_setor_remove_restricao_com_modulos_none(client, admin_token, db):
    operadora = db.scalar(select(Operadora).where(Operadora.nome == "ELITE"))
    criado = client.post(
        "/setores",
        json={"nome": "Restrito", "operadora_id": operadora.id, "modulos": ["LAUDOS"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    assert criado["modulos"] == ["LAUDOS"]

    resp = client.patch(
        f"/setores/{criado['id']}",
        json={"nome": "Restrito", "operadora_id": operadora.id, "modulos": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["modulos"] is None


def test_admin_cria_setor_com_modulo_de_outra_operadora_e_rejeitado(client, admin_token, db):
    operadora_elite = db.scalar(select(Operadora).where(Operadora.nome == "ELITE"))
    resp = client.post(
        "/setores",
        # AUDIENCIAS é da EXIMIA — depois de filtrado pra operadora ELITE, não sobra nenhum módulo válido.
        json={"nome": "Setor ELITE com módulo errado", "operadora_id": operadora_elite.id, "modulos": ["AUDIENCIAS"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


def test_admin_cria_e_edita_setor(client, admin_token, db):
    operadora = db.scalar(select(Operadora).where(Operadora.nome == "ELITE"))

    resp = client.post(
        "/setores",
        json={"nome": "Cobrança", "operadora_id": operadora.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Cobrança"
    assert body["operadora"] == "ELITE"
    assert body["ativo"] is True

    resp = client.patch(
        f"/setores/{body['id']}",
        json={"nome": "Cobrança e Financeiro", "operadora_id": operadora.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Cobrança e Financeiro"

    resp = client.patch(
        f"/setores/{body['id']}/ativo",
        params={"ativo": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["ativo"] is False


def test_setores_exige_admin(client, db):
    token = _usuario_com_setor(db, "ELITE", "colaboradora.setor@teste.local")
    resp = client.post("/setores", json={"nome": "X", "operadora_id": 1}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
