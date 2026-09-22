from app.db import _normalizar_url


def test_normaliza_postgresql_para_psycopg():
    url = "postgresql://user:pass@host:5432/postgres"
    assert _normalizar_url(url) == "postgresql+psycopg://user:pass@host:5432/postgres"


def test_normaliza_postgres_antigo_para_psycopg():
    url = "postgres://user:pass@host:5432/postgres"
    assert _normalizar_url(url) == "postgresql+psycopg://user:pass@host:5432/postgres"


def test_nao_mexe_em_sqlite():
    url = "sqlite:///:memory:"
    assert _normalizar_url(url) == url


def test_nao_mexe_se_driver_ja_especificado():
    url = "postgresql+psycopg2://user:pass@host:5432/postgres"
    assert _normalizar_url(url) == url
