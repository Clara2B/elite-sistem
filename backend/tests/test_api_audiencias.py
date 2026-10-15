"""Auditoria M29: os testes de API de Audiências (tests/test_permissoes.py)
só checavam permissão (403/filtro por setor), nunca o conteúdo da resposta
— estende a cobertura no mesmo padrão de tests/test_api_correspondencias.py
e tests/test_api_laudos.py (import via API, relatório JSON/PDF/Excel)."""
from __future__ import annotations

import io
from datetime import date

import openpyxl
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Audiencia
from app.services.empresas import get_or_create_empresa


def _planilha_audiencias_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["EMPRESA", "NOME COMPLETO", "DATA DE RECEBIMENTO", "CPF"])
    ws.append(["ABSOLUTA", "Fulano de Tal", date(2026, 9, 5), "111.111.111-11"])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_import_e_relatorio_via_api(db, admin_token):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    headers = {"Authorization": f"Bearer {admin_token}"}
    try:
        client = TestClient(app)

        resp = client.post(
            "/audiencias/import",
            files={
                "arquivo": (
                    "audiencias.xlsx", _planilha_audiencias_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["linhas_novas"] == 1

        resp = client.get(
            "/audiencias/relatorio",
            params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9, "quinzena": 1},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["empresa"] == "ABSOLUTA"
        assert body["clientes"] == ["Fulano de Tal"]
        assert body["quantidade_mes"] == 1
        assert body["valor_unitario"] == 400.0  # 1ª faixa padrão (1-20)
        assert body["total"] == 400.0
        assert "FULANO DE TAL" in body["texto"]

        resp_pdf = client.get(
            "/audiencias/relatorio.pdf",
            params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9, "quinzena": 1},
            headers=headers,
        )
        assert resp_pdf.status_code == 200
        assert resp_pdf.headers["content-type"] == "application/pdf"
        assert resp_pdf.content[:4] == b"%PDF"

        resp_xlsx = client.get(
            "/audiencias/relatorio.xlsx",
            params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9, "quinzena": 1},
            headers=headers,
        )
        assert resp_xlsx.status_code == 200
        assert resp_xlsx.headers["content-type"] == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert resp_xlsx.content[:2] == b"PK"

        resp_sem_login = client.get(
            "/audiencias/relatorio", params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9, "quinzena": 1},
        )
        assert resp_sem_login.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_relatorio_empresa_nao_encontrada_404(client, db, admin_token):
    resp = client.get(
        "/audiencias/relatorio",
        params={"empresa": "NÃO EXISTE", "ano": 2026, "mes": 9, "quinzena": 1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_apagar_todas_audiencias_via_api_exige_admin(client, db, admin_token):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(Audiencia(empresa_cliente_id=empresa.id, nome_cliente="Fulano", data_recebimento=date(2026, 9, 5)))
    db.commit()

    resp = client.delete("/audiencias", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["apagados"] == 1
    assert db.query(Audiencia).count() == 0

    resp_sem_login = client.delete("/audiencias")
    assert resp_sem_login.status_code == 401
