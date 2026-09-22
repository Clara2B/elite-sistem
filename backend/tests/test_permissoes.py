from datetime import date

from sqlalchemy import select

from app.auth import criar_sessao, hash_senha
from app.models import Cobranca, Setor, Usuario, UsuarioSetor
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
