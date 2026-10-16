"""Auditoria M29: os testes de API de Pendências (tests/test_permissoes.py)
só checavam permissão (403/filtro por operadora acessível), nunca o
conteúdo da resposta — estende a cobertura no mesmo padrão de
tests/test_api_correspondencias.py (import via API, conteúdo do
relatório)."""
from __future__ import annotations

import io
from datetime import date

import openpyxl
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Cobranca
from app.services.empresas import get_or_create_empresa


def _planilha_pendencias_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DATA", "EMPRESA", "TIPO DE COBRANÇA", "VALOR", "PAGO"])
    ws.append([date(2026, 9, 5), "ABSOLUTA", "MENSALIDADE", "R$ 180,00", "NÃO"])
    ws.append([date(2026, 9, 5), "ABSOLUTA", "AUDIÊNCIA EXTRAJUDICIAL", "R$ 400,00", "NÃO"])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_import_e_mensagens_via_api(db, admin_token):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    headers = {"Authorization": f"Bearer {admin_token}"}
    try:
        client = TestClient(app)

        resp = client.post(
            "/pendencias/import",
            files={
                "arquivo": (
                    "pendencias.xlsx", _planilha_pendencias_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["linhas_novas"] == 2

        resp = client.get("/pendencias/mensagens", params={"empresa": "ABSOLUTA"}, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2  # EXIMIA (audiência) e ELITE (mensalidade), cobrança pendente cada

        por_cobrador = {m["cobrador"]: m for m in body}
        assert por_cobrador["EXIMIA"]["total"] == 400.0
        assert por_cobrador["ELITE"]["total"] == 180.0
        assert por_cobrador["ELITE"]["empresa"] == "ABSOLUTA"
        assert len(por_cobrador["ELITE"]["itens"]) == 1
        assert "Total Pendente" in por_cobrador["ELITE"]["texto"]

        resp_sem_login = client.get("/pendencias/mensagens", params={"empresa": "ABSOLUTA"})
        assert resp_sem_login.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_mensagens_empresa_nao_encontrada_404(client, db, admin_token):
    resp = client.get(
        "/pendencias/mensagens", params={"empresa": "NÃO EXISTE"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_mensagens_sem_pendencia_retorna_lista_vazia(client, db, admin_token):
    get_or_create_empresa(db, "ABSOLUTA")
    db.commit()

    resp = client.get(
        "/pendencias/mensagens", params={"empresa": "ABSOLUTA"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_apagar_todas_pendencias_via_api_exige_admin(client, db, admin_token):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(Cobranca(
        empresa_cliente_id=empresa.id, data=date(2026, 9, 5), tipo_cobranca="MENSALIDADE",
        cobrador="ELITE", valor=180.0, status_pagamento="NÃO",
    ))
    db.commit()

    resp = client.delete("/pendencias", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["apagados"] == 1
    assert db.query(Cobranca).count() == 0

    resp_sem_login = client.delete("/pendencias")
    assert resp_sem_login.status_code == 401
