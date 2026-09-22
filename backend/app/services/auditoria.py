from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import LogAuditoria, Usuario


def registrar(
    db: Session,
    usuario: Usuario | None,
    acao: str,
    entidade: str | None = None,
    entidade_id: object = None,
    detalhes: str | None = None,
) -> None:
    db.add(
        LogAuditoria(
            usuario_id=usuario.id if usuario else None,
            acao=acao,
            entidade=entidade,
            entidade_id=str(entidade_id) if entidade_id is not None else None,
            detalhes=detalhes,
        )
    )
    db.commit()
