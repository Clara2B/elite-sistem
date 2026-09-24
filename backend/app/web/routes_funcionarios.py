from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Funcionario, Usuario
from app.services.auditoria import registrar
from app.services.funcionarios import (
    alterar_ativo_funcionario,
    atualizar_funcionario,
    criar_funcionario,
    excluir_funcionario,
    listar_funcionarios,
)
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/funcionarios")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "funcionarios": listar_funcionarios(db, apenas_ativos=False),
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(
    request: Request,
    erro: str | None = None,
    mensagem: str | None = None,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["erro"] = erro
    contexto["mensagem"] = mensagem
    return templates.TemplateResponse(request, "funcionarios.html", contexto)


@router.post("")
async def criar(
    request: Request,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    nome = str(form.get("nome", "")).strip()
    if not nome:
        contexto["erro"] = "Nome é obrigatório."
        return templates.TemplateResponse(request, "funcionarios.html", contexto, status_code=400)
    try:
        funcionario = criar_funcionario(db, nome)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "funcionarios.html", contexto, status_code=400)
    registrar(db, usuario, "CRIOU_FUNCIONARIO", entidade="funcionario", entidade_id=funcionario.id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Funcionário {funcionario.nome} cadastrado."
    return templates.TemplateResponse(request, "funcionarios.html", contexto)


@router.post("/{funcionario_id}")
async def editar(
    request: Request,
    funcionario_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    nome = str(form.get("nome", "")).strip()
    if not nome:
        contexto["erro"] = "Nome é obrigatório."
        return templates.TemplateResponse(request, "funcionarios.html", contexto, status_code=400)
    try:
        funcionario = atualizar_funcionario(db, funcionario_id, nome)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "funcionarios.html", contexto, status_code=400)
    registrar(db, usuario, "EDITOU_FUNCIONARIO", entidade="funcionario", entidade_id=funcionario_id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Funcionário {funcionario.nome} atualizado."
    return templates.TemplateResponse(request, "funcionarios.html", contexto)


@router.post("/{funcionario_id}/ativo")
def alterar_ativo(
    funcionario_id: int,
    ativo: bool,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    try:
        alterar_ativo_funcionario(db, funcionario_id, ativo)
    except ValueError:
        pass
    else:
        registrar(
            db, usuario, "ATIVOU_FUNCIONARIO" if ativo else "DESATIVOU_FUNCIONARIO",
            entidade="funcionario", entidade_id=funcionario_id,
        )
    return RedirectResponse("/app/funcionarios", status_code=303)


@router.post("/{funcionario_id}/excluir")
def excluir(
    funcionario_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Exclusão definitiva — a confirmação (obrigatória) acontece no
    navegador, num modal, antes desse POST (ver funcionarios.html e
    static/app.js). Não afeta processos/eventos já gravados (ver
    services/funcionarios.py::excluir_funcionario)."""
    funcionario = db.get(Funcionario, funcionario_id)
    nome = funcionario.nome if funcionario else str(funcionario_id)
    try:
        excluir_funcionario(db, funcionario_id)
    except ValueError as e:
        return RedirectResponse(f"/app/funcionarios?erro={quote(str(e))}", status_code=303)
    registrar(db, usuario, "EXCLUIU_FUNCIONARIO", entidade="funcionario", entidade_id=funcionario_id)
    return RedirectResponse(
        f"/app/funcionarios?mensagem={quote(f'Funcionário {nome} excluído definitivamente.')}", status_code=303
    )
