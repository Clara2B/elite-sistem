from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.services.auditoria import registrar
from app.services.empresas import (
    alterar_ativo_empresa,
    atualizar_empresa,
    criar_empresa,
    listar_empresas,
)
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/empresas")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": listar_empresas(db, apenas_ativas=False),
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(
    request: Request,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(request, "empresas.html", _contexto_base(db, usuario))


@router.post("")
async def criar(
    request: Request,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    nome = str(form.get("nome", "")).strip()
    cnpj = str(form.get("cnpj", "")).strip() or None
    if not nome:
        contexto["erro"] = "Nome é obrigatório."
        return templates.TemplateResponse(request, "empresas.html", contexto, status_code=400)
    try:
        empresa = criar_empresa(db, nome, cnpj)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "empresas.html", contexto, status_code=400)
    registrar(db, usuario, "CRIOU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa.id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Empresa {empresa.nome} cadastrada."
    return templates.TemplateResponse(request, "empresas.html", contexto)


@router.post("/{empresa_id}")
async def editar(
    request: Request,
    empresa_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    nome = str(form.get("nome", "")).strip()
    cnpj = str(form.get("cnpj", "")).strip() or None
    if not nome:
        contexto["erro"] = "Nome é obrigatório."
        return templates.TemplateResponse(request, "empresas.html", contexto, status_code=400)
    try:
        empresa = atualizar_empresa(db, empresa_id, nome, cnpj)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "empresas.html", contexto, status_code=400)
    registrar(db, usuario, "EDITOU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa_id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Empresa {empresa.nome} atualizada."
    return templates.TemplateResponse(request, "empresas.html", contexto)


@router.post("/{empresa_id}/ativo")
def alterar_ativo(
    empresa_id: int,
    ativo: bool,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    try:
        alterar_ativo_empresa(db, empresa_id, ativo)
    except ValueError:
        pass
    else:
        registrar(
            db, usuario, "ATIVOU_EMPRESA" if ativo else "DESATIVOU_EMPRESA",
            entidade="empresa_cliente", entidade_id=empresa_id,
        )
    return RedirectResponse("/app/empresas", status_code=303)
