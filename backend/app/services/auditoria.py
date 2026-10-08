from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LogAuditoria, Usuario

POR_PAGINA = 50


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


def humanizar_acao(acao: str) -> str:
    """`EXCLUIU_EMPRESAS_EM_MASSA` -> `Excluiu empresas em massa`. Genérico
    de propósito (troca `_` por espaço, só a primeira letra maiúscula) —
    os ~50 códigos de ação já seguem o padrão VERBO_OBJETO em português (ver
    cada `registrar(...)` espalhado pelo projeto), então isso funciona pra
    qualquer ação existente ou futura sem precisar manter um dicionário de
    tradução que ia ficar desatualizado toda vez que uma ação nova fosse
    adicionada em algum módulo."""
    texto = acao.replace("_", " ").strip().lower()
    return texto[:1].upper() + texto[1:] if texto else acao


@dataclass
class ResultadoAuditoria:
    registros: list[LogAuditoria]
    pagina: int
    total_paginas: int
    total_registros: int


def listar(
    db: Session,
    usuario_id: int | None = None,
    acao: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    pagina: int = 1,
) -> ResultadoAuditoria:
    """Lista paginada pra tela de Auditoria (2026-10-08, a pedido da Clara —
    "elevar o nível... otimização e produtividade": o log já existia e era
    gravado desde o início do projeto, só não tinha nenhuma tela pra
    consultar). Mais recente primeiro; `pagina` começa em 1."""
    query = select(LogAuditoria)
    if usuario_id is not None:
        query = query.where(LogAuditoria.usuario_id == usuario_id)
    if acao:
        query = query.where(LogAuditoria.acao == acao)
    if data_inicio is not None:
        query = query.where(LogAuditoria.criado_em >= datetime.combine(data_inicio, time.min))
    if data_fim is not None:
        query = query.where(LogAuditoria.criado_em <= datetime.combine(data_fim, time.max))

    total_registros = _contar(db, query)

    pagina = max(pagina, 1)
    total_paginas = max((total_registros + POR_PAGINA - 1) // POR_PAGINA, 1)
    pagina = min(pagina, total_paginas)

    registros = list(
        db.scalars(
            query.order_by(LogAuditoria.criado_em.desc(), LogAuditoria.id.desc())
            .offset((pagina - 1) * POR_PAGINA)
            .limit(POR_PAGINA)
        )
    )
    return ResultadoAuditoria(
        registros=registros, pagina=pagina, total_paginas=total_paginas, total_registros=total_registros
    )


def _contar(db: Session, query) -> int:
    return db.scalar(select(func.count()).select_from(query.subquery())) or 0


def acoes_distintas(db: Session) -> list[str]:
    """Pra popular o filtro de "Ação" na tela — só as que já aconteceram
    de verdade, não uma lista fixa que ia precisar ser atualizada toda vez
    que um módulo novo passasse a registrar uma ação nova (ex.: igual
    aconteceu com Correspondências nesta mesma sessão)."""
    return sorted(db.scalars(select(LogAuditoria.acao).distinct()))
