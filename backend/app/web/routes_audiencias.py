from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.db import get_db
from app.models import Usuario
from app.services import audiencias as audiencias_service
from app.services.auditoria import registrar
from app.services.empresas import listar_empresas
from app.web.auth import require_operadora_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/audiencias")

_acesso_eximia = require_operadora_web("EXIMIA")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": listar_empresas(db, apenas_ativas=False),
        "hoje": date.today(),
        "filtro": {},
        "resultado": None,
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(
    request: Request,
    empresa: str | None = None,
    ano: int | None = None,
    mes: int | None = None,
    quinzena: int | None = None,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["filtro"] = {"empresa": empresa, "ano": ano, "mes": mes, "quinzena": quinzena}
    if empresa and ano and mes and quinzena:
        periodo_ini, periodo_fim = audiencias_service.periodo_quinzenal(ano, mes, quinzena)
        try:
            resultado = audiencias_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim)
        except ValueError as e:
            contexto["erro"] = str(e)
        else:
            registrar(db, usuario, "GEROU_RELATORIO_AUDIENCIAS", entidade="empresa_cliente", entidade_id=empresa)
            contexto["resultado"] = resultado
    return templates.TemplateResponse(request, "audiencias.html", contexto)


@router.post("/import")
async def importar(
    request: Request,
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    contexto = _contexto_base(db, usuario)
    try:
        resumo = audiencias_service.importar_planilha(db, path)
    except ValueError as e:
        contexto["erro"] = str(e)
    else:
        registrar(db, usuario, "IMPORTOU_AUDIENCIAS", entidade="audiencia", detalhes=str(resumo))
        contexto["mensagem"] = (
            f"{resumo.linhas_novas} linha(s) nova(s) importada(s) "
            f"({resumo.linhas_ja_existentes} já existiam de antes)."
        )
    return templates.TemplateResponse(request, "audiencias.html", contexto)
