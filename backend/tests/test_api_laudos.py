import io
from datetime import date

import openpyxl
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Laudo
from app.services.empresas import get_or_create_empresa


def _planilha_laudos_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SETEMBRO"
    ws.append(["EMPRESA", "TIPO DE LAUDO", "DATA", "NOME DO CLIENTE", "ENTRADA DE LAUDO"])
    ws.append(["ABSOLUTA", "AUTO", date(2026, 9, 25), "Fulano de Tal", "Solicitação"])
    ws.append(["ABSOLUTA", "IMÓVEL", date(2026, 9, 26), "Beltrano", "Corrigido"])
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
            "/laudos/import",
            files={"arquivo": ("laudos.xlsx", _planilha_laudos_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["linhas_novas"] == 2

        resp = client.get(
            "/laudos/relatorio",
            params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9, "status": "Solicitação + Corrigido (cobrança)"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 40.0 + 70.0
        assert len(body["linhas"]) == 2

        resp_pdf = client.get(
            "/laudos/relatorio.pdf",
            params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9, "status": "Solicitação + Corrigido (cobrança)"},
            headers=headers,
        )
        assert resp_pdf.status_code == 200
        assert resp_pdf.headers["content-type"] == "application/pdf"
        assert resp_pdf.content[:4] == b"%PDF"

        resp_sem_login = client.get("/laudos/relatorio", params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9})
        assert resp_sem_login.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_apagar_todos_laudos_via_api_exige_admin(client, db, admin_token):
    empresa = get_or_create_empresa(db, "ABSOLUTA")
    db.add(Laudo(empresa_cliente_id=empresa.id, tipo_laudo_nome="AUTO", data=date(2026, 1, 25),
                 nome_cliente="Fulano", status="SOLICITAÇÃO"))
    db.commit()

    resp = client.delete("/laudos", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["apagados"] == 1
    assert db.query(Laudo).count() == 0

    resp_sem_login = client.delete("/laudos")
    assert resp_sem_login.status_code == 401
