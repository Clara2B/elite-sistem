from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.db import get_db
from app.pdf_export import gerar_pdf_audiencias
from app.services import audiencias as audiencias_service

router = APIRouter(prefix="/audiencias", tags=["audiencias"])


@router.post("/import")
def importar(arquivo: UploadFile, db: Session = Depends(get_db)):
    path = salvar_temp(arquivo)
    try:
        resumo = audiencias_service.importar_planilha(db, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return resumo


@router.get("/relatorio")
def relatorio(
    empresa: str,
    ano: int,
    mes: int,
    quinzena: int,
    cnpj: str | None = None,
    db: Session = Depends(get_db),
):
    periodo_ini, periodo_fim = audiencias_service.periodo_quinzenal(ano, mes, quinzena)
    try:
        resultado = audiencias_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim, cnpj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "empresa": resultado.empresa,
        "cnpj": resultado.cnpj,
        "periodo_ini": resultado.periodo_ini,
        "periodo_fim": resultado.periodo_fim,
        "valor_unitario": resultado.valor_unitario,
        "clientes": resultado.clientes,
        "total": resultado.total,
        "valor_cadastrado": resultado.valor_cadastrado,
        "quantidade_mes_anterior": resultado.quantidade_mes_anterior,
        "quantidade_mes": resultado.quantidade_mes,
        "texto": audiencias_service.formatar_texto(resultado),
    }


@router.get("/relatorio.pdf")
def relatorio_pdf(
    empresa: str,
    ano: int,
    mes: int,
    quinzena: int,
    cnpj: str | None = None,
    db: Session = Depends(get_db),
):
    periodo_ini, periodo_fim = audiencias_service.periodo_quinzenal(ano, mes, quinzena)
    try:
        resultado = audiencias_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim, cnpj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    pdf_bytes = gerar_pdf_audiencias(resultado)
    return Response(content=pdf_bytes, media_type="application/pdf")
