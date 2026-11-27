"""Cabeçalhos de segurança básicos (2026-10-13, auditoria M09) — confirma
que toda resposta (mesmo sem login, mesmo uma rota simples) já sai com os
cabeçalhos de defesa em profundidade, sem precisar simular HTTPS (que o
TestClient não faz por padrão, por isso HSTS não é testado aqui)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_resposta_tem_cabecalhos_de_seguranca():
    resposta = client.get("/health")
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["X-Frame-Options"] == "DENY"
    assert resposta.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in resposta.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in resposta.headers["Content-Security-Policy"]


def test_sem_hsts_em_requisicao_http():
    # O TestClient faz a requisição com esquema "http" por padrão — o
    # cabeçalho HSTS só deve existir quando o esquema for "https" (mesmo
    # critério do cookie de sessão).
    resposta = client.get("/health")
    assert "Strict-Transport-Security" not in resposta.headers
