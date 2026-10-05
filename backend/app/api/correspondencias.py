from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import require_admin, require_modulo
from app.db import get_db
from app.excel_export import gerar_excel_correspondencias
from app.models import Usuario
from app.pdf_export import gerar_pdf_correspondencias
from app.services import correspondencias as correspondencias_service
from app.services.auditoria import registrar
from app.utils import nome_arquivo_pdf, nome_arquivo_xlsx

router = APIRouter(prefix="/correspondencias", tags=["correspondencias"])

# Correspondências é um produto da ELITE (ver ARCHITECTURE.md seção 1.3).
_acesso_elite = require_modulo("CORRESPONDENCIAS")


@router.post("/import")
def importar(
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    try:
        resumo = correspondencias_service.importar_planilha(db, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "IMPORTOU_CORRESPONDENCIAS", entidade="correspondencia", detalhes=str(resumo))
    return resumo


@router.delete("")
def apagar_tudo(
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Apaga todo o histórico de correspondências — irreversível; só Admin
    Superior/T.I."""
    total = correspondencias_service.apagar_todas_correspondencias(db)
    registrar(
        db, usuario, "APAGOU_TODAS_CORRESPONDENCIAS",
        entidade="correspondencia", detalhes=f"{total} correspondência(s) apagada(s)",
    )
    return {"apagados": total}


@router.get("/relatorio")
def relatorio(
    empresa: str,
    mes: str,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    try:
        resultado = correspondencias_service.gerar_relatorio(db, empresa, mes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(db, usuario, "GEROU_RELATORIO_CORRESPONDENCIAS", entidade="empresa_cliente", entidade_id=empresa)
    return {
        "empresa": resultado.empresa,
        "mes": resultado.mes,
        "total": resultado.total,
        "linhas": resultado.linhas,
    }


@router.get("/relatorio.pdf")
def relatorio_pdf(
    empresa: str,
    mes: str,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    try:
        resultado = correspondencias_service.gerar_relatorio(db, empresa, mes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(db, usuario, "GEROU_RELATORIO_CORRESPONDENCIAS_PDF", entidade="empresa_cliente", entidade_id=empresa)
    pdf_bytes = gerar_pdf_correspondencias(resultado)
    nome_arquivo = nome_arquivo_pdf("correspondencias", resultado.empresa, resultado.mes)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/relatorio.xlsx")
def relatorio_xlsx(
    empresa: str,
    mes: str,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    try:
        resultado = correspondencias_service.gerar_relatorio(db, empresa, mes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(db, usuario, "GEROU_RELATORIO_CORRESPONDENCIAS_XLSX", entidade="empresa_cliente", entidade_id=empresa)
    excel_bytes = gerar_excel_correspondencias(resultado)
    nome_arquivo = nome_arquivo_xlsx("correspondencias", resultado.empresa, resultado.mes)
    return Response(
        content=excel_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
