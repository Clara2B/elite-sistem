"""Tela /app/funcionarios — paginação/busca (2026-11-27, a pedido da Clara,
item da varredura completa: listagens administrativas sem busca/paginação
viravam uma página enorme conforme o cadastro crescia)."""
from __future__ import annotations

from app.auth import hash_senha
from app.models import Funcionario, Usuario


def _logar_admin(db, client, email="admin.funcionarios@teste.com"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_lista_pagina_quando_passa_de_30(db, client):
    _logar_admin(db, client)
    for i in range(35):
        db.add(Funcionario(nome=f"ASSISTENTE {i:02d}"))
    db.commit()

    resp = client.get("/app/funcionarios")
    assert resp.status_code == 200
    assert "Página 1 de 2" in resp.text
    assert "Cadastrados (35)" in resp.text

    resp_pagina2 = client.get("/app/funcionarios", params={"pagina": 2})
    assert resp_pagina2.status_code == 200
    assert "Página 2 de 2" in resp_pagina2.text


def test_busca_filtra_por_nome(db, client):
    _logar_admin(db, client)
    db.add(Funcionario(nome="DANILO"))
    db.add(Funcionario(nome="JULIA"))
    db.commit()

    resp = client.get("/app/funcionarios", params={"busca": "dani"})
    assert resp.status_code == 200
    assert "DANILO" in resp.text
    assert "JULIA" not in resp.text


def test_busca_sem_resultado_mostra_mensagem_especifica(db, client):
    _logar_admin(db, client)
    db.add(Funcionario(nome="DANILO"))
    db.commit()

    resp = client.get("/app/funcionarios", params={"busca": "NAO EXISTE"})
    assert resp.status_code == 200
    assert "Nenhum assistente encontrado para essa busca" in resp.text
