from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.web.auth import usuario_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter()


@router.get("/")
def dashboard(
    request: Request,
    usuario: Usuario = Depends(usuario_logado_web),
    db: Session = Depends(get_db),
):
    menu = itens_menu(db, usuario)
    return templates.TemplateResponse(
        request, "dashboard.html", {"usuario": usuario, "menu": menu}
    )
