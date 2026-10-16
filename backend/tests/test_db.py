from datetime import datetime, timedelta

from app.auth import hash_senha
from app.db import _limpar_sessoes_expiradas, _normalizar_url
from app.models import Sessao, Usuario


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


def test_limpar_sessoes_expiradas_remove_so_as_vencidas(db):
    """Auditoria M11: Sessao nunca era podada — toda sessão criada ficava
    pra sempre no banco, mesmo depois de expirada."""
    usuario = Usuario(nome="Fulano", email="sessao.limpa@teste.local", senha_hash=hash_senha("x"))
    db.add(usuario)
    db.flush()

    expirada = Sessao(token="t" * 64, usuario_id=usuario.id, expira_em=datetime.utcnow() - timedelta(hours=1))
    valida = Sessao(token="v" * 64, usuario_id=usuario.id, expira_em=datetime.utcnow() + timedelta(hours=1))
    db.add_all([expirada, valida])
    db.commit()

    _limpar_sessoes_expiradas(db)

    assert db.get(Sessao, "t" * 64) is None
    assert db.get(Sessao, "v" * 64) is not None
