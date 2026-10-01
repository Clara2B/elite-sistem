"""Lista de chamados de suporte (2026-10-01, a pedido da Clara) — área de
Configuração, só pra Admin, lista o que foi aberto pelo pop-up (ver
routes_suporte.py/services/suporte.py) com opção de marcar como resolvido."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Chamado, Usuario
from app.services.auditoria import registrar
from app.web.areas_configuracao import AREAS_CONFIGURACAO
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/chamados")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "areas_configuracao": AREAS_CONFIGURACAO,
        "chamados": db.scalars(
            select(Chamado).order_by(Chamado.resolvido, Chamado.criado_em.desc())
        ).all(),
    }


@router.get("")
def tela(request: Request, usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "chamados.html", _contexto_base(db, usuario))


@router.post("/{chamado_id}/resolvido")
def alterar_resolvido(
    chamado_id: int,
    resolvido: bool,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    chamado = db.get(Chamado, chamado_id)
    if chamado is not None:
        chamado.resolvido = resolvido
        chamado.resolvido_em = datetime.utcnow() if resolvido else None
        db.commit()
        registrar(
            db, usuario, "RESOLVEU_CHAMADO" if resolvido else "REABRIU_CHAMADO",
            entidade="chamado", entidade_id=chamado_id,
        )
    return RedirectResponse("/app/chamados", status_code=303)
