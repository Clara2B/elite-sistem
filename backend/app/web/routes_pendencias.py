from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import PAPEIS_GLOBAIS, operadoras_acessiveis
from app.db import get_db
from app.models import Usuario
from app.services import pendencias as pendencias_service
from app.services.auditoria import registrar
from app.services.empresas import listar_empresas
from app.web.auth import admin_logado_web, usuario_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/pendencias")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": listar_empresas(db, apenas_ativas=False),
        "filtro": {},
        "mensagens": None,
        "mensagem": None,
        "erro": None,
        "eh_admin": usuario.papel_global in PAPEIS_GLOBAIS,
    }


@router.get("")
def tela(
    request: Request,
    empresa: str | None = None,
    mensagem: str | None = None,
    usuario: Usuario = Depends(usuario_logado_web),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = mensagem
    contexto["filtro"] = {"empresa": empresa}
    if empresa:
        try:
            msgs = pendencias_service.gerar_mensagens(db, empresa)
        except ValueError as e:
            contexto["erro"] = str(e)
        else:
            acessiveis = operadoras_acessiveis(db, usuario)
            msgs = [m for m in msgs if m.cobrador in acessiveis]
            registrar(db, usuario, "GEROU_MENSAGENS_PENDENCIAS", entidade="empresa_cliente", entidade_id=empresa)
            contexto["mensagens"] = [
                {"cobrador": m.cobrador, "total": m.total, "texto": pendencias_service.formatar_texto(m)}
                for m in msgs
            ]
    return templates.TemplateResponse(request, "pendencias.html", contexto)


@router.post("/import")
async def importar(
    request: Request,
    arquivo: UploadFile,
    usuario: Usuario = Depends(usuario_logado_web),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    contexto = _contexto_base(db, usuario)
    try:
        resumo = pendencias_service.importar_planilha(db, path)
    except ValueError as e:
        contexto["erro"] = str(e)
    else:
        registrar(db, usuario, "IMPORTOU_PENDENCIAS", entidade="cobranca", detalhes=str(resumo))
        contexto["mensagem"] = (
            f"{resumo.linhas_novas} linha(s) nova(s) importada(s) "
            f"({resumo.linhas_ja_existentes} já existiam de antes)."
        )
    return templates.TemplateResponse(request, "pendencias.html", contexto)


@router.post("/apagar-tudo")
def apagar_tudo(
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Apaga todo o histórico de cobranças/pendências (EXÍMIA e ELITE) —
    irreversível; só Admin Superior/T.I. A confirmação (obrigatória, com o
    nome digitado) acontece no navegador antes desse POST — ver
    pendencias.html/static/app.js."""
    total = pendencias_service.apagar_todas_pendencias(db)
    registrar(db, usuario, "APAGOU_TODAS_PENDENCIAS", entidade="cobranca", detalhes=f"{total} cobrança(s) apagada(s)")
    mensagem = quote(f"{total} cobrança(s) apagada(s). Pode importar a planilha do zero agora.")
    return RedirectResponse(f"/app/pendencias?mensagem={mensagem}", status_code=303)
