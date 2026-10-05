"""Tela /app/correspondencias — mesmo padrão de Laudos."""
from __future__ import annotations

import io

import openpyxl

from app.auth import hash_senha
from app.models import Usuario


def _planilha_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ADV. CONTRATOS"
    ws.append(["MÊS", "ADVOGADO", "AUTOR", "EMPRESA", "ADV / PREPOSTO", "VALOR", "TIPO DE AÇÃO"])
    ws.append(["Janeiro", "Dra. Fulana", "Cliente A", "EROS", "ADVOGADO", "R$ 180,00", "PROCON"])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _logar_admin(db, client, email="admin.correspondencias@teste.local"):
    db.add(Usuario(nome="Admin", email=email, senha_hash=hash_senha("certa"), papel_global="ADMIN_SUPERIOR"))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def _logar_colaborador(db, client, email="colab.correspondencias@teste.local"):
    db.add(Usuario(nome="Colaborador", email=email, senha_hash=hash_senha("certa")))
    db.commit()
    client.post("/login", data={"email": email, "senha": "certa"})


def test_tela_sem_login_redireciona(client, db):
    resposta = client.get("/app/correspondencias", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


def test_importa_e_gera_relatorio_pela_tela(client, db):
    _logar_admin(db, client)

    resposta = client.post(
        "/app/correspondencias/import",
        files={
            "arquivo": (
                "correspondencias.xlsx", _planilha_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resposta.status_code == 200
    assert "1 linha(s) nova(s)" in resposta.text
    # a empresa da planilha (EROS) é nova no sistema — tem que aparecer no
    # dropdown já na resposta do próprio import, sem precisar recarregar
    # (bug real encontrado nesta sessão: o dropdown era montado antes do
    # import rodar).
    assert '<option value="EROS"' in resposta.text

    resposta = client.get("/app/correspondencias", params={"empresa": "EROS", "mes": "Janeiro"})
    assert resposta.status_code == 200
    assert "Cliente A" in resposta.text
    assert "Dra. Fulana" in resposta.text
    assert "Baixar Excel" in resposta.text
    assert "Baixar PDF" in resposta.text


def test_relatorio_sem_resultado_mostra_mensagem_amigavel(client, db):
    _logar_admin(db, client, "admin.vazio@teste.local")
    resposta = client.get("/app/correspondencias", params={"empresa": "Inexistente", "mes": "Janeiro"})
    assert resposta.status_code == 200
    assert "não foi encontrada" in resposta.text


def test_apagar_tudo_exige_admin(client, db):
    _logar_colaborador(db, client)
    resposta = client.post("/app/correspondencias/apagar-tudo", follow_redirects=False)
    assert resposta.status_code != 200


def test_apagar_tudo_funciona_pra_admin(client, db):
    _logar_admin(db, client, "admin.apagar@teste.local")
    client.post(
        "/app/correspondencias/import",
        files={
            "arquivo": (
                "correspondencias.xlsx", _planilha_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    resposta = client.post("/app/correspondencias/apagar-tudo", follow_redirects=False)
    assert resposta.status_code == 303
    assert "location" in resposta.headers
