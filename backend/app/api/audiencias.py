from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import require_admin, require_operadora
from app.db import get_db
from app.models import Usuario
from app.pdf_export import gerar_pdf_audiencias
from app.services import audiencias as audiencias_service
from app.services.auditoria import registrar
from app.utils import nome_arquivo_pdf

router = APIRouter(prefix="/audiencias", tags=["audiencias"])

# Audiências é um produto da EXIMIA (ver ARCHITECTURE.md seção 1.3).
_acesso_eximia = require_operadora("EXIMIA")


@router.post("/import")
def importar(
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    try:
        resumo = audiencias_service.importar_planilha(db, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "IMPORTOU_AUDIENCIAS", entidade="audiencia", detalhes=str(resumo))
    return resumo


@router.delete("")
def apagar_tudo(
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Apaga todo o histórico de audiências — irreversível; só Admin
    Superior/T.I. (ver DECISIONS.md 2026-09-24)."""
    total = audiencias_service.apagar_todas_audiencias(db)
    registrar(db, usuario, "APAGOU_TODAS_AUDIENCIAS", entidade="audiencia", detalhes=f"{total} audiência(s) apagada(s)")
    return {"apagados": total}


@router.get("/relatorio")
def relatorio(
    empresa: str,
    ano: int,
    mes: int,
    quinzena: int,
    cnpj: str | None = None,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    periodo_ini, periodo_fim = audiencias_service.periodo_quinzenal(ano, mes, quinzena)
    try:
        resultado = audiencias_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim, cnpj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(db, usuario, "GEROU_RELATORIO_AUDIENCIAS", entidade="empresa_cliente", entidade_id=empresa)
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
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    periodo_ini, periodo_fim = audiencias_service.periodo_quinzenal(ano, mes, quinzena)
    try:
        resultado = audiencias_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim, cnpj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(db, usuario, "GEROU_RELATORIO_AUDIENCIAS_PDF", entidade="empresa_cliente", entidade_id=empresa)
    pdf_bytes = gerar_pdf_audiencias(resultado)
    nome_arquivo = nome_arquivo_pdf("audiencias", resultado.empresa, f"{ano}-{mes:02d}", f"q{quinzena}")
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
