"""Auditoria M29: não existia test_api_processos.py — mesmo padrão de
tests/test_api_laudos.py e tests/test_api_correspondencias.py (import via
API, relatório JSON/PDF/Excel), mais prazos-proximos e resolver_evento,
que também não tinham nenhum teste de API."""
from __future__ import annotations

import io
from datetime import date

import openpyxl
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import EventoProcesso, Processo
from app.services.empresas import get_or_create_empresa


def _planilha_processos_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["CLIENTE", "Nº PROCESSO", "DATA", "EVENTO", "PRAZO FATAL"])
    ws.append(["ABSOLUTA - Fulano de Tal", "1111111-11.2026.8.11.0001", date(2026, 9, 5), "CUSTAS", "NÃO"])
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
            "/processos/import",
            files={
                "arquivo": (
                    "processos.xlsx", _planilha_processos_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["linhas_novas"] == 1

        resp = client.get(
            "/processos/relatorio",
            params={"periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30", "tipo": "geral"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["resultado"]["secoes"][0]["empresa"] == "ABSOLUTA"
        assert body["resultado"]["secoes"][0]["total_processos"] == 1
        assert "ABSOLUTA" in body["texto"]

        resp_por_empresa = client.get(
            "/processos/relatorio",
            params={
                "periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30",
                "tipo": "empresa", "empresa": "ABSOLUTA",
            },
            headers=headers,
        )
        assert resp_por_empresa.status_code == 200
        assert resp_por_empresa.json()["resultado"]["empresa"] == "ABSOLUTA"

        resp_sem_empresa = client.get(
            "/processos/relatorio",
            params={"periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30", "tipo": "empresa"},
            headers=headers,
        )
        assert resp_sem_empresa.status_code == 400

        resp_pdf = client.get(
            "/processos/relatorio.pdf",
            params={"periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30", "tipo": "geral"},
            headers=headers,
        )
        assert resp_pdf.status_code == 200
        assert resp_pdf.headers["content-type"] == "application/pdf"
        assert resp_pdf.content[:4] == b"%PDF"

        resp_xlsx = client.get(
            "/processos/relatorio.xlsx",
            params={"periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30", "tipo": "geral"},
            headers=headers,
        )
        assert resp_xlsx.status_code == 200
        assert resp_xlsx.headers["content-type"] == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert resp_xlsx.content[:2] == b"PK"

        resp_sem_login = client.get(
            "/processos/relatorio",
            params={"periodo_ini": "2026-09-01", "periodo_fim": "2026-09-30", "tipo": "geral"},
        )
        assert resp_sem_login.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_prazos_proximos_via_api(client, db, admin_token):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    processo = Processo(numero_processo="5012298-14.2025.8.13.0231", empresa_cliente_id=empresa.id, nome_cliente="Fulano")
    db.add(processo)
    db.flush()
    db.add(EventoProcesso(
        processo_id=processo.id, data=date.today(), tipo_evento_nome="CUSTAS",
        prazo_fatal=True, data_prazo=date.today(),
    ))
    db.commit()

    resp = client.get(
        "/processos/prazos-proximos", params={"dias": 30},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["nome_cliente"] == "Fulano"
    assert body[0]["numero_processo"] == "5012298-14.2025.8.13.0231"

    resp_sem_login = client.get("/processos/prazos-proximos")
    assert resp_sem_login.status_code == 401


def test_resolver_evento_via_api(client, db, admin_token):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    processo = Processo(numero_processo="5012298-14.2025.8.13.0231", empresa_cliente_id=empresa.id, nome_cliente="Fulano")
    db.add(processo)
    db.flush()
    evento = EventoProcesso(
        processo_id=processo.id, data=date.today(), tipo_evento_nome="CUSTAS",
        prazo_fatal=True, data_prazo=date.today(),
    )
    db.add(evento)
    db.commit()

    resp = client.post(
        f"/processos/eventos/{evento.id}/resolver",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolvido"] is True
    assert body["resolvido_em"] is not None

    resp_inexistente = client.post(
        "/processos/eventos/999999/resolver",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_inexistente.status_code == 404


def test_apagar_todos_processos_via_api_exige_admin(client, db, admin_token):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    processo = Processo(numero_processo="5012298-14.2025.8.13.0231", empresa_cliente_id=empresa.id, nome_cliente="Fulano")
    db.add(processo)
    db.commit()

    resp = client.delete("/processos", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["apagados"] == 1
    assert db.query(Processo).count() == 0

    resp_sem_login = client.delete("/processos")
    assert resp_sem_login.status_code == 401
