"""Correspondências (Fase 9, ELITE, 2026-10-05, a pedido da Clara) — mesmo
padrão de Laudos: upload de planilha (acumula histórico), filtro por mês +
empresa, PDF/Excel. Ver app/web/routes_laudos.py pro espelho exato dessa
rota."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import PAPEIS_GLOBAIS
from app.db import get_db
from app.models import Usuario
from app.services import correspondencias as correspondencias_service
from app.services.auditoria import registrar
from app.services.empresas import listar_empresas
from app.web.auth import admin_logado_web, require_modulo_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/correspondencias")

_acesso_elite = require_modulo_web("CORRESPONDENCIAS")

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": listar_empresas(db, apenas_ativas=False),
        "meses": MESES,
        "filtro": {"empresa": None, "mes": None},
        "mensagem": None,
        "resultado": None,
        "erro": None,
        "eh_admin": usuario.papel_global in PAPEIS_GLOBAIS,
    }


@router.get("")
def tela(
    request: Request,
    empresa: str | None = None,
    mes: str | None = None,
    mensagem: str | None = None,
    erro: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["filtro"] = {"empresa": empresa, "mes": mes}
    contexto["mensagem"] = mensagem
    contexto["erro"] = erro

    if empresa and mes and not erro:
        try:
            resultado = correspondencias_service.gerar_relatorio(db, empresa, mes)
        except ValueError as e:
            contexto["erro"] = str(e)
        else:
            registrar(db, usuario, "GEROU_RELATORIO_CORRESPONDENCIAS", entidade="empresa_cliente", entidade_id=empresa)
            contexto["resultado"] = resultado
    return templates.TemplateResponse(request, "correspondencias.html", contexto)


@router.post("/import")
async def importar(
    request: Request,
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    mensagem = None
    erro = None
    try:
        resumo = correspondencias_service.importar_planilha(db, path)
    except ValueError as e:
        erro = str(e)
    else:
        registrar(db, usuario, "IMPORTOU_CORRESPONDENCIAS", entidade="correspondencia", detalhes=str(resumo))
        mensagem = (
            f"{resumo.linhas_novas} linha(s) nova(s) importada(s) "
            f"({resumo.linhas_ja_existentes} já existiam de antes)."
        )
    # _contexto_base DEPOIS do import (não antes): a planilha pode trazer
    # empresa nova, que só existe no banco depois de importar_planilha
    # rodar — calculado antes, o dropdown de empresa saía sem a que acabou
    # de ser criada, obrigando a recarregar a página à toa.
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = mensagem
    contexto["erro"] = erro
    return templates.TemplateResponse(request, "correspondencias.html", contexto)


@router.post("/apagar-tudo")
def apagar_tudo(
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Apaga todo o histórico de correspondências — mesmo padrão de
    `routes_laudos.py::apagar_tudo` (confirmação obrigatória no navegador
    antes desse POST). Só Admin Superior/T.I."""
    total = correspondencias_service.apagar_todas_correspondencias(db)
    registrar(
        db, usuario, "APAGOU_TODAS_CORRESPONDENCIAS",
        entidade="correspondencia", detalhes=f"{total} correspondência(s) apagada(s)",
    )
    mensagem = quote(f"{total} correspondência(s) apagada(s). Pode importar a planilha do zero agora.")
    return RedirectResponse(f"/app/correspondencias?mensagem={mensagem}", status_code=303)
