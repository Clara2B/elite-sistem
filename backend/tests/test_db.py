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


def test_remove_pgbouncer_da_query_string():
    # A tela "ORM"/Prisma do Supabase inclui isso na URL do pooler — é uma
    # flag do Prisma, não uma opção real do Postgres; o psycopg recusa a
    # conexão se ela vier na URL ("invalid connection option 'pgbouncer'").
    url = "postgresql://user:pass@aws-0-us-west-2.pooler.supabase.com:6543/postgres?pgbouncer=true"
    assert _normalizar_url(url) == "postgresql+psycopg://user:pass@aws-0-us-west-2.pooler.supabase.com:6543/postgres"


def test_preserva_outros_parametros_da_query_string():
    url = "postgresql://user:pass@host:5432/postgres?sslmode=require&pgbouncer=true"
    assert _normalizar_url(url) == "postgresql+psycopg://user:pass@host:5432/postgres?sslmode=require"
