"""Tela administrativa das faixas de preço de Audiências (2026-10-13,
auditoria M05) — só admin, dentro de Configuração (mesmo padrão de
Setores/Auditoria/Relatórios das Assessorias: sem item próprio na barra
lateral). Antes, ampliar o limite de audiências/mês que o sistema sabe
cobrar (`DEFAULT_FAIXAS_AUDIENCIA`, app/db.py) só era possível editando o
banco direto — ver services/faixas_audiencia.py."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.services.auditoria import registrar
from app.services.faixas_audiencia import (
    atualizar_faixa,
    criar_faixa,
    excluir_faixa,
    listar_faixas,
)
from app.web.areas_configuracao import AREAS_CONFIGURACAO
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/faixas-audiencia")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "areas_configuracao": AREAS_CONFIGURACAO,
        "faixas": listar_faixas(db),
        "mensagem": None,
        "erro": None,
    }


def _ler_faixa_do_form(form) -> tuple[int, int, float]:
    inicio = int(form.get("inicio", 0) or 0)
    fim = int(form.get("fim", 0) or 0)
    valor = float(str(form.get("valor", "0") or "0").replace(",", "."))
    return inicio, fim, valor


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
    return templates.TemplateResponse(request, "faixas_audiencia.html", contexto)


@router.post("")
async def criar(request: Request, usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db)):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    try:
        inicio, fim, valor = _ler_faixa_do_form(form)
        faixa = criar_faixa(db, inicio, fim, valor)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "faixas_audiencia.html", contexto, status_code=400)

    registrar(db, usuario, "CRIOU_FAIXA_AUDIENCIA", entidade="faixa_audiencia", entidade_id=faixa.id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Faixa {faixa.inicio}-{faixa.fim} criada."
    return templates.TemplateResponse(request, "faixas_audiencia.html", contexto)


@router.post("/{faixa_id}")
async def editar(
    request: Request,
    faixa_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    try:
        inicio, fim, valor = _ler_faixa_do_form(form)
        faixa = atualizar_faixa(db, faixa_id, inicio, fim, valor)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "faixas_audiencia.html", contexto, status_code=400)

    registrar(db, usuario, "EDITOU_FAIXA_AUDIENCIA", entidade="faixa_audiencia", entidade_id=faixa.id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Faixa {faixa.inicio}-{faixa.fim} atualizada."
    return templates.TemplateResponse(request, "faixas_audiencia.html", contexto)


@router.post("/{faixa_id}/excluir")
def excluir(
    faixa_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Exclusão definitiva — a confirmação (obrigatória) acontece no
    navegador, num modal, antes desse POST (mesmo padrão de Setores)."""
    try:
        excluir_faixa(db, faixa_id)
    except ValueError as e:
        return RedirectResponse(f"/app/faixas-audiencia?erro={quote(str(e))}", status_code=303)

    registrar(db, usuario, "EXCLUIU_FAIXA_AUDIENCIA", entidade="faixa_audiencia", entidade_id=faixa_id)
    return RedirectResponse(
        f"/app/faixas-audiencia?mensagem={quote('Faixa excluída.')}", status_code=303
    )
