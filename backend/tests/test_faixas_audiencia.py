"""Tela/serviço de faixas de preço de Audiências (2026-10-13, auditoria M05)
— cobre o cadastro/edição/exclusão pela tela admin (que antes não existia:
ampliar a faixa exigia editar o banco direto) e as validações de
`services/faixas_audiencia.py` (sem faixa sobreposta, início/fim/valor
coerentes)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.auth import hash_senha
from app.models import FaixaAudiencia, Usuario
from app.services.faixas_audiencia import (
    atualizar_faixa,
    criar_faixa,
    excluir_faixa,
    listar_faixas,
)


def _logar_admin(db, client, email="admin.faixas@teste.local"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _logar_colaborador(db, client, email="colab.faixas@teste.local"):
    db.add(Usuario(nome="Colaborador", email=email, senha_hash=hash_senha("certa")))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_criar_faixa_acima_das_existentes(db):
    criar_faixa(db, 101, 150, 250.0)
    faixas = listar_faixas(db)
    assert faixas[-1].inicio == 101
    assert faixas[-1].fim == 150
    assert faixas[-1].valor == 250.0


def test_criar_faixa_sobreposta_eh_rejeitada(db):
    with pytest.raises(ValueError, match="sobrepõe"):
        criar_faixa(db, 50, 70, 300.0)  # cruza com a faixa seed 40-60 e 61-79


def test_criar_faixa_fim_menor_que_inicio_eh_rejeitada(db):
    with pytest.raises(ValueError, match="início"):
        criar_faixa(db, 50, 10, 100.0)


def test_criar_faixa_valor_negativo_eh_rejeitada(db):
    with pytest.raises(ValueError, match="negativo"):
        criar_faixa(db, 101, 150, -1.0)


def test_atualizar_faixa_ignora_sobreposicao_com_ela_mesma(db):
    # Reduz a faixa 1-20 pra 1-15 — ela própria não deve contar como
    # "sobreposição" ao comparar o novo intervalo contra as faixas
    # existentes (ignorar_id exclui a faixa que está sendo editada).
    faixa = db.scalar(select(FaixaAudiencia).where(FaixaAudiencia.inicio == 1))
    atualizar_faixa(db, faixa.id, 1, 15, 420.0)
    db.refresh(faixa)
    assert faixa.fim == 15
    assert faixa.valor == 420.0


def test_excluir_faixa(db):
    faixa = criar_faixa(db, 101, 150, 250.0)
    excluir_faixa(db, faixa.id)
    assert db.get(FaixaAudiencia, faixa.id) is None


def test_tela_cria_e_edita_faixa_via_http(client, db):
    _logar_admin(db, client)

    resposta = client.post(
        "/app/faixas-audiencia", data={"inicio": "101", "fim": "150", "valor": "250.00"}
    )
    assert resposta.status_code == 200
    faixa = db.scalar(select(FaixaAudiencia).where(FaixaAudiencia.inicio == 101))
    assert faixa is not None
    assert faixa.valor == 250.0

    resposta = client.post(
        f"/app/faixas-audiencia/{faixa.id}", data={"inicio": "101", "fim": "160", "valor": "260.00"}
    )
    assert resposta.status_code == 200
    db.refresh(faixa)
    assert faixa.fim == 160
    assert faixa.valor == 260.0


def test_tela_rejeita_faixa_sobreposta_com_mensagem_de_erro(client, db):
    _logar_admin(db, client)
    resposta = client.post("/app/faixas-audiencia", data={"inicio": "50", "fim": "70", "valor": "300"})
    assert resposta.status_code == 400
    assert "sobrep" in resposta.text


def test_tela_exclui_faixa_via_http(client, db):
    _logar_admin(db, client)
    faixa = criar_faixa(db, 101, 150, 250.0)

    resposta = client.post(f"/app/faixas-audiencia/{faixa.id}/excluir", follow_redirects=False)
    assert resposta.status_code == 303
    assert db.get(FaixaAudiencia, faixa.id) is None


def test_colaborador_sem_papel_global_nao_acessa_tela(client, db):
    _logar_colaborador(db, client)
    resposta = client.get("/app/faixas-audiencia", follow_redirects=False)
    assert resposta.status_code == 403


def test_sem_login_redireciona_para_login(client):
    resposta = client.get("/app/faixas-audiencia", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"
