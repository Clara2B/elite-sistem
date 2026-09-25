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
from app.services import processos as processos_service
from app.services.auditoria import registrar
from app.services.empresas import listar_empresas
from app.services.funcionarios import listar_funcionarios
from app.web.auth import admin_logado_web, require_operadora_web
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
        "empresas": listar_empresas(db, apenas_ativas=False),
        "funcionarios": listar_funcionarios(db, apenas_ativos=False),
        "filtro": {},
        "resultado": None,
        "prazos": processos_service.prazos_proximos(db, dias=30),
        "mensagem": None,
        "erro": None,
        "eh_admin": usuario.papel_global in PAPEIS_GLOBAIS,
    }


@router.get("")
def tela(
    request: Request,
    periodo_ini: date | None = None,
    periodo_fim: date | None = None,
    tipo: str = "geral",
    empresa: str | None = None,
    assistente: str | None = None,
    mensagem: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = mensagem
    padrao_ini, padrao_fim = _periodo_padrao()
    contexto["filtro"] = {
        "periodo_ini": periodo_ini or padrao_ini,
        "periodo_fim": periodo_fim or padrao_fim,
        "tipo": tipo,
        "empresa": empresa or "",
        "assistente": assistente or "",
    }
    try:
        if tipo == "empresa":
            if not empresa:
                raise ValueError("Selecione uma empresa para o relatório \"Por empresa\".")
            resultado = processos_service.gerar_relatorio_por_empresa(
                db, empresa, contexto["filtro"]["periodo_ini"], contexto["filtro"]["periodo_fim"], assistente or None,
            )
        else:
            resultado = processos_service.gerar_relatorio_geral(
                db, contexto["filtro"]["periodo_ini"], contexto["filtro"]["periodo_fim"], assistente or None,
            )
    except ValueError as e:
        contexto["erro"] = str(e)
    else:
        registrar(db, usuario, "GEROU_RELATORIO_PROCESSOS", entidade="processo", detalhes=f"tipo={tipo}")
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
    contexto["filtro"] = {
        "periodo_ini": padrao_ini, "periodo_fim": padrao_fim,
        "tipo": "geral", "empresa": "", "assistente": "",
    }
    try:
        resumo = processos_service.importar_planilha(db, path, usuario_id=usuario.id)
    except ValueError as e:
        contexto["erro"] = str(e)
    else:
        registrar(db, usuario, "IMPORTOU_PROCESSOS", entidade="processo", detalhes=str(resumo))
        contexto["mensagem"] = (
            f"{resumo.linhas_novas} evento(s) novo(s) importado(s) "
            f"({resumo.linhas_ja_existentes} já existiam de antes, "
            f"{resumo.linhas_atualizadas} desses com dado atualizado agora)."
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


@router.post("/apagar-tudo")
def apagar_tudo(
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Apaga todo o histórico de Gestão de Processos (processos + eventos)
    — irreversível; só Admin Superior/T.I. A confirmação (obrigatória, com
    o nome digitado) acontece no navegador antes desse POST — ver
    processos.html/static/app.js."""
    total = processos_service.apagar_todos_processos(db)
    registrar(db, usuario, "APAGOU_TODOS_PROCESSOS", entidade="processo", detalhes=f"{total} processo(s) apagado(s)")
    mensagem = quote(f"{total} processo(s) apagado(s). Pode importar a planilha do zero agora.")
    return RedirectResponse(f"/app/processos?mensagem={mensagem}", status_code=303)
