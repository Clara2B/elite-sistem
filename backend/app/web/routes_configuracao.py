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
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/configuracao")

_AREAS = [
    {"url": "/app/usuarios", "rotulo": "Usuários", "icone": "usuarios", "descricao": "Cadastrar, editar e gerenciar acessos da equipe."},
    {"url": "/app/empresas", "rotulo": "Empresas-clientes", "icone": "empresas", "descricao": "Cadastro, CNPJ e ativação das empresas atendidas."},
    {"url": "/app/funcionarios", "rotulo": "Assistentes", "icone": "funcionarios", "descricao": "Assistentes de Gestão de Processos — alimenta o relatório."},
    {"url": "/app/setores", "rotulo": "Setores", "icone": "setores", "descricao": "Setores por operadora — usados nos vínculos de usuário."},
]


@router.get("")
def tela(request: Request, usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "configuracao.html",
        {"usuario": usuario, "menu": itens_menu(db, usuario), "areas": _AREAS},
    )
