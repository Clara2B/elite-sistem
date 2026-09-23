from __future__ import annotations

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import operadoras_acessiveis
from app.db import get_db
from app.models import Usuario
from app.services import pendencias as pendencias_service
from app.services.auditoria import registrar
from app.services.empresas import listar_empresas
from app.web.auth import usuario_logado_web
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
    }


@router.get("")
def tela(
    request: Request,
    empresa: str | None = None,
    usuario: Usuario = Depends(usuario_logado_web),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
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
