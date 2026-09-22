from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import require_operadora
from app.db import get_db
from app.models import Usuario
from app.pdf_export import gerar_pdf_laudos
from app.services import laudos as laudos_service
from app.services.auditoria import registrar

router = APIRouter(prefix="/laudos", tags=["laudos"])

# Laudos é um produto da ELITE (ver ARCHITECTURE.md seção 1.3) — só quem tem
# acesso à operadora ELITE (Admin Superior/T.I. ou setor vinculado a ela)
# pode usar essas rotas.
_acesso_elite = require_operadora("ELITE")


@router.post("/import")
def importar(
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    try:
        resumo = laudos_service.importar_planilha(db, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "IMPORTOU_LAUDOS", entidade="laudo", detalhes=str(resumo))
    return resumo


@router.get("/relatorio")
def relatorio(
    empresa: str,
    ano: int,
    mes: int,
    status: str = laudos_service.OPCOES_STATUS[0],
    cnpj: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    periodo_ini, periodo_fim = laudos_service.periodo_20_a_20(ano, mes)
    try:
        resultado = laudos_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim, status, cnpj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(db, usuario, "GEROU_RELATORIO_LAUDOS", entidade="empresa_cliente", entidade_id=empresa)
    return {
        "empresa": resultado.empresa,
        "cnpj": resultado.cnpj,
        "periodo_ini": resultado.periodo_ini,
        "periodo_fim": resultado.periodo_fim,
        "status": resultado.status,
        "total": resultado.total,
        "tipos_sem_valor": resultado.tipos_sem_valor,
        "linhas": resultado.linhas,
        "texto": laudos_service.formatar_texto(resultado),
    }


@router.get("/relatorio.pdf")
def relatorio_pdf(
    empresa: str,
    ano: int,
    mes: int,
    status: str = laudos_service.OPCOES_STATUS[0],
    cnpj: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    periodo_ini, periodo_fim = laudos_service.periodo_20_a_20(ano, mes)
    try:
        resultado = laudos_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim, status, cnpj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(db, usuario, "GEROU_RELATORIO_LAUDOS_PDF", entidade="empresa_cliente", entidade_id=empresa)
    pdf_bytes = gerar_pdf_laudos(resultado)
    return Response(content=pdf_bytes, media_type="application/pdf")
