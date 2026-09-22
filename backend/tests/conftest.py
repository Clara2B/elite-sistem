import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import criar_sessao, hash_senha
from app.db import (
    DEFAULT_FAIXAS_AUDIENCIA,
    DEFAULT_SETORES,
    DEFAULT_TIPOS_EVENTO,
    DEFAULT_TIPOS_LAUDO,
)
from app.db import get_db as get_db_dependency
from app.main import app
from app.models import (
    Base,
    FaixaAudiencia,
    Operadora,
    Setor,
    TipoEvento,
    TipoLaudo,
    Usuario,
)


@pytest.fixture()
def db():
    """Sessão contra um SQLite em memória — mais rápido que subir um
    Postgres no CI, e o schema (tipos simples, sem recursos exclusivos de
    Postgres) é totalmente compatível entre os dois."""
    # check_same_thread=False + StaticPool: o TestClient da FastAPI roda a
    # app numa thread separada da do teste, e um SQLite ":memory:" comum cria
    # um banco novo (vazio) a cada conexão do pool — StaticPool força reusar
    # a mesma conexão/banco em memória entre as duas threads (padrão
    # recomendado pela própria SQLAlchemy para testar com SQLite em memória).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    for nome, valor in DEFAULT_TIPOS_LAUDO.items():
        session.add(TipoLaudo(nome=nome, valor_padrao=valor))
    for inicio, fim, valor in DEFAULT_FAIXAS_AUDIENCIA:
        session.add(FaixaAudiencia(inicio=inicio, fim=fim, valor=valor))
    for nome in DEFAULT_TIPOS_EVENTO:
        session.add(TipoEvento(nome=nome))

    operadoras = {}
    for nome in ("EXIMIA", "ELITE"):
        operadora = Operadora(nome=nome)
        session.add(operadora)
        session.flush()
        operadoras[nome] = operadora
    for operadora_nome, nomes_setor in DEFAULT_SETORES.items():
        for nome_setor in nomes_setor:
            session.add(Setor(operadora_id=operadoras[operadora_nome].id, nome=nome_setor))

    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def admin_token(db) -> str:
    """Cria um Admin Superior de teste (acesso total) e devolve o token de
    sessão pronto para usar em `headers={"Authorization": f"Bearer {token}"}`."""
    usuario = Usuario(
        nome="Admin Teste",
        email="admin@teste.local",
        senha_hash=hash_senha("senha-teste"),
        papel_global="ADMIN_SUPERIOR",
    )
    db.add(usuario)
    db.commit()
    sessao = criar_sessao(db, usuario)
    return sessao.token


@pytest.fixture()
def client(db) -> TestClient:
    """TestClient com `get_db` apontando para a sessão de teste (SQLite em
    memória), pronto pra usar nos testes de API."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db_dependency] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
