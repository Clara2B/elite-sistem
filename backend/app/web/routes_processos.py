from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.db import get_db
from app.models import Usuario
from app.services import processos as processos_service
from app.services.auditoria import registrar
from app.web.auth import require_operadora_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/processos")

_acesso_elite = require_operadora_web("ELITE")


def _periodo_padrao() -> tuple[date, date]:
    hoje = date.today()
    return hoje.replace(day=1), hoje


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "filtro": {},
        "resultado": None,
        "prazos": processos_service.prazos_proximos(db, dias=30),
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(
    request: Request,
    periodo_ini: date | None = None,
    periodo_fim: date | None = None,
    agrupar_por: str = "assistente",
    pessoa: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    padrao_ini, padrao_fim = _periodo_padrao()
    contexto["filtro"] = {
        "periodo_ini": periodo_ini or padrao_ini,
        "periodo_fim": periodo_fim or padrao_fim,
        "agrupar_por": agrupar_por,
        "pessoa": pessoa or "",
    }
    try:
        resultado = processos_service.gerar_relatorio(
            db, contexto["filtro"]["periodo_ini"], contexto["filtro"]["periodo_fim"],
            agrupar_por, pessoa or None,
        )
    except ValueError as e:
        contexto["erro"] = str(e)
    else:
        titulo = f"Relatório de {pessoa}" if pessoa else "Relatório geral da equipe"
        registrar(db, usuario, "GEROU_RELATORIO_PROCESSOS", entidade="processo", detalhes=titulo)
        contexto["resultado"] = resultado
    return templates.TemplateResponse(request, "processos.html", contexto)


@router.post("/import")
async def importar(
    request: Request,
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    contexto = _contexto_base(db, usuario)
    padrao_ini, padrao_fim = _periodo_padrao()
    contexto["filtro"] = {"periodo_ini": padrao_ini, "periodo_fim": padrao_fim, "agrupar_por": "assistente", "pessoa": ""}
    try:
        resumo = processos_service.importar_planilha(db, path, usuario_id=usuario.id)
    except ValueError as e:
        contexto["erro"] = str(e)
    else:
        registrar(db, usuario, "IMPORTOU_PROCESSOS", entidade="processo", detalhes=str(resumo))
        contexto["mensagem"] = (
            f"{resumo.linhas_novas} evento(s) novo(s) importado(s) "
            f"({resumo.linhas_ja_existentes} já existiam de antes)."
        )
        contexto["prazos"] = processos_service.prazos_proximos(db, dias=30)
    return templates.TemplateResponse(request, "processos.html", contexto)


@router.post("/eventos/{evento_id}/resolver")
def resolver(
    evento_id: int,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    try:
        processos_service.marcar_resolvido(db, evento_id)
    except ValueError:
        pass  # evento não existe mais — segue para a mesma tela sem quebrar
    else:
        registrar(db, usuario, "RESOLVEU_EVENTO_PROCESSO", entidade="evento_processo", entidade_id=evento_id)
    return RedirectResponse("/app/processos", status_code=303)
