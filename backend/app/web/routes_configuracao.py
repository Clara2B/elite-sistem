"""Área administrativa separada (2026-09-28, a pedido da Clara) — uma tela
de entrada com cards pras 4 telas de administração (Usuários, Empresas-
clientes, Assistentes, Setores), que continuam com suas próprias rotas e
lógica (nada foi reescrito, só ganhou um ponto de entrada comum e destacado
do resto do menu)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.web.areas_configuracao import AREAS_CONFIGURACAO
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/configuracao")


@router.get("")
def tela(request: Request, usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "configuracao.html",
        {"usuario": usuario, "menu": itens_menu(db, usuario), "areas": AREAS_CONFIGURACAO},
    )
