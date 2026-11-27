"""Auditoria M29: rotas de API (Authorization: Bearer) de Cartas não tinham
nenhum teste — exatamente a camada que uma integração externa (não a tela
web) usaria. tests/test_cartas.py já cobre bem as rotas web equivalentes
(/app/cartas/...); aqui só as duas rotas de API (/cartas/...)."""
from __future__ import annotations


def test_convite_cliente_pdf_via_api(client, db, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.get(
        "/cartas/convite-cliente.pdf",
        params={
            "autor": "Fulano da Silva", "reu": "Banco Tal", "dia": "2026-10-15",
            "hora": "14:05", "link": "meet.google.com/abc-defg-hij",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert "attachment" in resp.headers["content-disposition"]

    resp_sem_login = client.get(
        "/cartas/convite-cliente.pdf",
        params={
            "autor": "Fulano da Silva", "reu": "Banco Tal", "dia": "2026-10-15",
            "hora": "14:05", "link": "meet.google.com/abc-defg-hij",
        },
    )
    assert resp_sem_login.status_code == 401


def test_convite_cliente_pdf_via_api_link_invalido_400(client, db, admin_token):
    resp = client.get(
        "/cartas/convite-cliente.pdf",
        params={
            "autor": "A", "reu": "B", "dia": "2026-10-15",
            "hora": "14:05", "link": "site-qualquer.com",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "Link da audiência inválido" in resp.json()["detail"]


def test_convite_banco_pdf_via_api(client, db, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.get(
        "/cartas/convite-banco.pdf",
        params={
            "banco_nome": "Banco Tal", "banco_cnpj": "00.000.000/0001-00", "nome": "Fulana de Tal",
            "cpf": "529.982.247-25", "contrato": "12345", "data": "2026-11-03",
            "hora": "09:30", "link": "teams.microsoft.com/l/meetup-join/xyz",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"

    resp_sem_login = client.get(
        "/cartas/convite-banco.pdf",
        params={
            "banco_nome": "Banco Tal", "banco_cnpj": "00.000.000/0001-00", "nome": "Fulana de Tal",
            "cpf": "529.982.247-25", "contrato": "12345", "data": "2026-11-03",
            "hora": "09:30", "link": "teams.microsoft.com/l/meetup-join/xyz",
        },
    )
    assert resp_sem_login.status_code == 401


def test_convite_banco_pdf_via_api_cpf_invalido_400(client, db, admin_token):
    resp = client.get(
        "/cartas/convite-banco.pdf",
        params={
            "banco_nome": "Banco Tal", "banco_cnpj": "00.000.000/0001-00", "nome": "Fulana",
            "cpf": "111.111.111-11", "contrato": "123", "data": "2026-11-03",
            "hora": "09:30", "link": "meet.google.com/x",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "CPF inválido" in resp.json()["detail"]
