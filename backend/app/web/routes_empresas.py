from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EmpresaCliente, Usuario
from app.services.auditoria import registrar
from app.services.empresas import (
    alterar_ativo_empresa,
    atualizar_empresa,
    criar_empresa,
    excluir_empresa,
    listar_empresas,
    sincronizar_lista_oficial,
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
    erro: str | None = None,
    mensagem: str | None = None,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    # erro/mensagem por query string: só usado depois de um redirect (ex.:
    # excluir, que precisa de POST + redirect, então não pode simplesmente
    # devolver a página com o erro no corpo da mesma resposta como os
    # outros formulários desta tela fazem).
    contexto["erro"] = erro
    contexto["mensagem"] = mensagem
    return templates.TemplateResponse(request, "empresas.html", contexto)


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


@router.post("/sincronizar-lista-oficial")
def sincronizar(
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Sincroniza com a lista oficial de 48 empresas (nome + CNPJ) que a
    Clara mandou em PDF (2026-09-24) — a confirmação (obrigatória, com o
    nome digitado) acontece no navegador antes desse POST (ver empresas.html
    e static/app.js). Irreversível para quem for excluído. Precisa ficar
    ANTES de `POST /{empresa_id}` abaixo — senão o Starlette casa essa rota
    com `empresa_id="sincronizar-lista-oficial"` primeiro e devolve 422."""
    resumo = sincronizar_lista_oficial(db)
    registrar(
        db, usuario, "SINCRONIZOU_EMPRESAS_OFICIAIS", entidade="empresa_cliente",
        detalhes=(
            f"{len(resumo.criadas)} criada(s), {len(resumo.atualizadas_cnpj)} CNPJ atualizado(s), "
            f"{len(resumo.excluidas)} excluída(s), {len(resumo.nao_excluidas_por_vinculo)} não excluída(s) por vínculo"
        ),
    )
    mensagem = (
        f"{len(resumo.criadas)} criada(s), {len(resumo.atualizadas_cnpj)} com CNPJ atualizado, "
        f"{len(resumo.excluidas)} excluída(s)."
    )
    if resumo.nao_excluidas_por_vinculo:
        mensagem += (
            f" {len(resumo.nao_excluidas_por_vinculo)} não puderam ser excluídas por terem histórico "
            f"vinculado: {', '.join(resumo.nao_excluidas_por_vinculo)}."
        )
    return RedirectResponse(f"/app/empresas?mensagem={quote(mensagem)}", status_code=303)


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


@router.post("/{empresa_id}/excluir")
def excluir(
    empresa_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Exclusão definitiva — a confirmação (obrigatória) acontece no
    navegador, num modal, antes desse POST ser disparado (ver empresas.html
    e static/app.js). O backend também recusa se houver dado vinculado."""
    empresa = db.get(EmpresaCliente, empresa_id)
    nome = empresa.nome if empresa else str(empresa_id)
    try:
        excluir_empresa(db, empresa_id)
    except ValueError as e:
        return RedirectResponse(f"/app/empresas?erro={quote(str(e))}", status_code=303)
    registrar(db, usuario, "EXCLUIU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa_id)
    return RedirectResponse(f"/app/empresas?mensagem={quote(f'Empresa {nome} excluída definitivamente.')}", status_code=303)
