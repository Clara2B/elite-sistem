from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base, FaixaAudiencia, TipoLaudo

DEFAULT_TIPOS_LAUDO = {
    "AUTO": 40.0,
    "AUTO-BALÃO": 60.0,
    "CONSÓRCIO": 200.0,
    "EMPRÉSTIMO": 40.0,
    "LOTEAMENTO": 400.0,
    "IMÓVEL": 70.0,
}

DEFAULT_FAIXAS_AUDIENCIA = (
    (1, 20, 400.0),
    (21, 39, 350.0),
    (40, 60, 300.0),
    (61, 79, 250.0),
    (80, 100, 200.0),
)

_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL não configurado. Defina a variável de ambiente antes de usar o banco."
            )
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Cria as tabelas (se não existirem) e semeia valores padrão, igual ao
    comportamento do core/db.py do sistema atual na primeira execução."""
    Base.metadata.create_all(get_engine())
    session_factory = get_session_factory()
    with session_factory() as db:
        if db.scalar(select(TipoLaudo.id).limit(1)) is None:
            for nome, valor in DEFAULT_TIPOS_LAUDO.items():
                db.add(TipoLaudo(nome=nome, valor_padrao=valor))
        if db.scalar(select(FaixaAudiencia.id).limit(1)) is None:
            for inicio, fim, valor in DEFAULT_FAIXAS_AUDIENCIA:
                db.add(FaixaAudiencia(inicio=inicio, fim=fim, valor=valor))
        db.commit()
