from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.db import get_db
from app.models import Usuario
from app.services import laudos as laudos_service
from app.services.auditoria import registrar
from app.services.empresas import listar_empresas
from app.web.auth import require_operadora_web
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
        "erro": None,
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
