from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import PAPEIS_GLOBAIS
from app.db import get_db
from app.models import Usuario
from app.services import laudos as laudos_service
from app.services.auditoria import registrar
from app.services.empresas import listar_empresas
from app.web.auth import admin_logado_web, require_operadora_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/laudos")

_acesso_elite = require_operadora_web("ELITE")


@router.get("")
def tela(
    request: Request,
    empresa: str | None = None,
    ano: int | None = None,
    mes: int | None = None,
    status: str | None = None,
    mensagem: str | None = None,
    erro: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    contexto = {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": listar_empresas(db, apenas_ativas=False),
        "opcoes_status": laudos_service.OPCOES_STATUS,
        "hoje": date.today(),
        "filtro": {"empresa": empresa, "ano": ano, "mes": mes, "status": status},
        "mensagem": mensagem,
        "resultado": None,
        "erro": erro,
        "eh_admin": usuario.papel_global in PAPEIS_GLOBAIS,
    }
    if empresa and ano and mes and status:
        periodo_ini, periodo_fim = laudos_service.periodo_20_a_20(ano, mes)
        try:
            resultado = laudos_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim, status)
        except ValueError as e:
            contexto["erro"] = str(e)
        else:
            registrar(db, usuario, "GEROU_RELATORIO_LAUDOS", entidade="empresa_cliente", entidade_id=empresa)
            contexto["resultado"] = resultado
    return templates.TemplateResponse(request, "laudos.html", contexto)


@router.post("/import")
async def importar(
    request: Request,
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    contexto = {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": listar_empresas(db, apenas_ativas=False),
        "opcoes_status": laudos_service.OPCOES_STATUS,
        "hoje": date.today(),
        "filtro": {},
        "resultado": None,
        "mensagem": None,
        "erro": None,
        "eh_admin": usuario.papel_global in PAPEIS_GLOBAIS,
    }
    try:
        resumo = laudos_service.importar_planilha(db, path)
    except ValueError as e:
        contexto["erro"] = str(e)
    else:
        registrar(db, usuario, "IMPORTOU_LAUDOS", entidade="laudo", detalhes=str(resumo))
        contexto["mensagem"] = (
            f"{resumo.linhas_novas} linha(s) nova(s) importada(s) "
            f"({resumo.linhas_ja_existentes} já existiam de antes)."
        )
    return templates.TemplateResponse(request, "laudos.html", contexto)


@router.post("/apagar-tudo")
def apagar_tudo(
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Apaga todo o histórico de laudos — a pedido explícito da Clara
    (2026-09-24), pra corrigir de vez os laudos com data errada gravados
    antes do bug da coluna de data ser corrigido (ver DECISIONS.md). Só
    Admin Superior/T.I.; a confirmação (obrigatória, com o nome digitado)
    acontece no navegador antes desse POST — ver laudos.html/static/app.js."""
    total = laudos_service.apagar_todos_laudos(db)
    registrar(db, usuario, "APAGOU_TODOS_LAUDOS", entidade="laudo", detalhes=f"{total} laudo(s) apagado(s)")
    mensagem = quote(f"{total} laudo(s) apagado(s). Pode importar a planilha do zero agora.")
    return RedirectResponse(f"/app/laudos?mensagem={mensagem}", status_code=303)
