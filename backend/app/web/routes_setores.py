"""Cadastro de Setores (2026-09-28, a pedido da Clara — "adicionar setores e
papéis para os setores") — antes só existiam pré-cadastrados via
DEFAULT_SETORES (app/db.py), sem nenhuma tela de administração; o vínculo
usuário-setor (com o papel LIDER/COLABORADOR dentro do setor) já existia em
Usuários e continua lá, sem mudança. Mesmo padrão de Empresas-clientes:
edição inline na tabela, sem exclusão (só ativar/desativar — um Setor com
usuários vinculados não pode ser removido sem quebrar o histórico)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Operadora, Setor, Usuario
from app.services.auditoria import registrar
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/setores")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "setores": db.scalars(select(Setor).order_by(Setor.operadora_id, Setor.nome)).all(),
        "operadoras": db.scalars(select(Operadora).order_by(Operadora.nome)).all(),
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(request: Request, usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "setores.html", _contexto_base(db, usuario))


@router.post("")
async def criar(request: Request, usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db)):
    form = await request.form()
    contexto = _contexto_base(db, usuario)

    nome = str(form.get("nome", "")).strip()
    operadora_id = form.get("operadora_id")

    if not nome or not operadora_id:
        contexto["erro"] = "Nome e operadora são obrigatórios."
        return templates.TemplateResponse(request, "setores.html", contexto, status_code=400)

    novo = Setor(nome=nome, operadora_id=int(operadora_id))
    db.add(novo)
    db.commit()
    registrar(db, usuario, "CRIOU_SETOR", entidade="setor", entidade_id=novo.id)

    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Setor {nome} criado."
    return templates.TemplateResponse(request, "setores.html", contexto)


@router.post("/{setor_id}")
async def editar(
    request: Request,
    setor_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)

    alvo = db.get(Setor, setor_id)
    if alvo is None:
        contexto["erro"] = "Setor não encontrado."
        return templates.TemplateResponse(request, "setores.html", contexto, status_code=404)

    nome = str(form.get("nome", "")).strip()
    operadora_id = form.get("operadora_id")
    if not nome or not operadora_id:
        contexto["erro"] = "Nome e operadora são obrigatórios."
        return templates.TemplateResponse(request, "setores.html", contexto, status_code=400)

    alvo.nome = nome
    alvo.operadora_id = int(operadora_id)
    db.commit()
    registrar(db, usuario, "EDITOU_SETOR", entidade="setor", entidade_id=alvo.id)

    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Setor {nome} atualizado."
    return templates.TemplateResponse(request, "setores.html", contexto)


@router.post("/{setor_id}/ativo")
def alterar_ativo(
    setor_id: int,
    ativo: bool,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    alvo = db.get(Setor, setor_id)
    if alvo is not None:
        alvo.ativo = ativo
        db.commit()
        registrar(db, usuario, "ATIVOU_SETOR" if ativo else "DESATIVOU_SETOR", entidade="setor", entidade_id=setor_id)
    return RedirectResponse("/app/setores", status_code=303)
