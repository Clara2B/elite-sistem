import io
from datetime import date

import openpyxl
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


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


def test_import_e_relatorio_via_api(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)

        resp = client.post(
            "/laudos/import",
            files={"arquivo": ("laudos.xlsx", _planilha_laudos_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        assert resp.json()["linhas_novas"] == 2

        resp = client.get(
            "/laudos/relatorio",
            params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9, "status": "Solicitação + Corrigido (cobrança)"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 40.0 + 70.0
        assert len(body["linhas"]) == 2

        resp_pdf = client.get(
            "/laudos/relatorio.pdf",
            params={"empresa": "ABSOLUTA", "ano": 2026, "mes": 9, "status": "Solicitação + Corrigido (cobrança)"},
        )
        assert resp_pdf.status_code == 200
        assert resp_pdf.headers["content-type"] == "application/pdf"
        assert resp_pdf.content[:4] == b"%PDF"
    finally:
        app.dependency_overrides.clear()
