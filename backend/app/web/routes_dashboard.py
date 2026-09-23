from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.web.auth import usuario_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter()

_DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _data_por_extenso(hoje: date) -> str:
    return f"{_DIAS_SEMANA[hoje.weekday()]}, {hoje.day} de {_MESES[hoje.month - 1]} de {hoje.year}"


@router.get("/")
def dashboard(
    request: Request,
    usuario: Usuario = Depends(usuario_logado_web),
    db: Session = Depends(get_db),
):
    menu = itens_menu(db, usuario)
    return templates.TemplateResponse(
        request, "dashboard.html",
        {"usuario": usuario, "menu": menu, "data_hoje": _data_por_extenso(date.today())},
    )
