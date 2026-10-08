"""Tela /app/empresas — exclusão e realocação em massa (2026-10-06, a pedido
da Clara: "selecionar e apagar empresas em massa, além de realocá-las em
massa se necessário")."""
from __future__ import annotations

from datetime import date

from sqlalchemy import event

from app.auth import hash_senha
from app.models import Audiencia, EmpresaCliente, Laudo, Usuario
from app.services.empresas import get_or_create_empresa


def _logar_admin(db, client, email="admin.empresas.massa@teste.local"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _logar_colaborador(db, client, email="colab.empresas.massa@teste.local"):
    db.add(Usuario(nome="Colaborador", email=email, senha_hash=hash_senha("certa")))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_excluir_em_massa_pela_tela(client, db):
    _logar_admin(db, client)
    a = get_or_create_empresa(db, "WEB MASSA EXCLUIR A")
    b = get_or_create_empresa(db, "WEB MASSA EXCLUIR B")
    db.commit()

    resposta = client.post(
        "/app/empresas/excluir-em-massa",
        data={"empresa_ids": [str(a.id), str(b.id)]},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    assert "exclu%C3%ADda" in resposta.headers["location"]
    assert db.get(EmpresaCliente, a.id) is None
    assert db.get(EmpresaCliente, b.id) is None


def test_excluir_em_massa_com_destino_pela_tela(client, db):
    _logar_admin(db, client)
    origem = get_or_create_empresa(db, "WEB MASSA EXCLUIR DESTINO ORIGEM")
    destino = get_or_create_empresa(db, "WEB MASSA EXCLUIR DESTINO")
    db.add(Laudo(empresa_cliente_id=origem.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 1), status="SOLICITAÇÃO"))
    db.commit()

    resposta = client.post(
        "/app/empresas/excluir-em-massa",
        data={"empresa_ids": [str(origem.id)], "empresa_destino_id": str(destino.id)},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    assert db.get(EmpresaCliente, origem.id) is None
    assert db.query(Laudo).one().empresa_cliente_id == destino.id


def test_excluir_em_massa_sem_selecao_mostra_erro(client, db):
    _logar_admin(db, client)

    resposta = client.post("/app/empresas/excluir-em-massa", data={}, follow_redirects=False)
    assert resposta.status_code == 303
    assert "Nenhuma%20empresa%20selecionada" in resposta.headers["location"]


def test_excluir_em_massa_exige_admin(client, db):
    _logar_colaborador(db, client)
    a = get_or_create_empresa(db, "WEB MASSA EXCLUIR SEM PERMISSAO")
    db.commit()

    resposta = client.post(
        "/app/empresas/excluir-em-massa", data={"empresa_ids": [str(a.id)]}, follow_redirects=False
    )
    assert resposta.status_code != 303
    assert db.get(EmpresaCliente, a.id) is not None


def test_realocar_em_massa_pela_tela(client, db):
    _logar_admin(db, client)
    origem = get_or_create_empresa(db, "WEB MASSA REALOCAR ORIGEM")
    destino = get_or_create_empresa(db, "WEB MASSA REALOCAR DESTINO")
    db.add(Audiencia(empresa_cliente_id=origem.id, nome_cliente="Fulano", data_recebimento=date(2026, 1, 1)))
    db.commit()

    resposta = client.post(
        "/app/empresas/realocar-em-massa",
        data={"empresa_ids": [str(origem.id)], "empresa_destino_id": str(destino.id)},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    assert "movido" in resposta.headers["location"]
    # a empresa de origem continua cadastrada e ativa — só o histórico se move
    origem_db = db.get(EmpresaCliente, origem.id)
    assert origem_db is not None
    assert origem_db.ativo
    assert db.query(Audiencia).one().empresa_cliente_id == destino.id


def test_realocar_em_massa_sem_destino_mostra_erro(client, db):
    _logar_admin(db, client)
    a = get_or_create_empresa(db, "WEB MASSA REALOCAR SEM DESTINO")
    db.commit()

    resposta = client.post(
        "/app/empresas/realocar-em-massa", data={"empresa_ids": [str(a.id)]}, follow_redirects=False
    )
    assert resposta.status_code == 303
    assert "destino" in resposta.headers["location"].lower()
    assert db.get(EmpresaCliente, a.id) is not None


def test_realocar_em_massa_exige_admin(client, db):
    _logar_colaborador(db, client)
    origem = get_or_create_empresa(db, "WEB MASSA REALOCAR SEM PERMISSAO")
    destino = get_or_create_empresa(db, "WEB MASSA REALOCAR SEM PERMISSAO DESTINO")
    db.commit()

    resposta = client.post(
        "/app/empresas/realocar-em-massa",
        data={"empresa_ids": [str(origem.id)], "empresa_destino_id": str(destino.id)},
        follow_redirects=False,
    )
    assert resposta.status_code != 303


def test_tela_nao_faz_uma_consulta_por_empresa(client, db):
    """2026-10-08, varredura de otimização: `_contexto_base` rodava 5
    consultas (uma por tipo de vínculo) PRA CADA empresa cadastrada —
    `contar_vinculos_todas_empresas` reduz isso a 5 no total, não importa
    quantas empresas existam. Sem esse teste, uma mudança futura poderia
    reintroduzir o padrão N+1 sem que nenhum teste existente percebesse
    (o resultado fica igual, só fica lento)."""
    _logar_admin(db, client)
    for i in range(10):
        empresa = get_or_create_empresa(db, f"WEB MASSA QUERY COUNT {i}")
        if i % 2 == 0:
            db.add(
                Laudo(
                    empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO",
                    data=date(2026, 1, 1), status="SOLICITAÇÃO",
                )
            )
    db.commit()

    consultas = []
    engine = db.get_bind()

    def _contar(conn, cursor, statement, parameters, context, executemany):
        consultas.append(statement)

    event.listen(engine, "before_cursor_execute", _contar)
    try:
        resposta = client.get("/app/empresas")
    finally:
        event.remove(engine, "before_cursor_execute", _contar)

    assert resposta.status_code == 200
    # bem abaixo de "10 empresas × 5 consultas" (50) — um número pequeno e
    # fixo, que não cresce com a quantidade de empresas cadastradas.
    assert len(consultas) < 15, f"consultas demais ({len(consultas)}) — voltou o padrão N+1?"
