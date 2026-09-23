from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import require_operadora
from app.db import get_db
from app.models import Usuario
from app.pdf_export import gerar_pdf_processos
from app.services import processos as processos_service
from app.services.auditoria import registrar
from app.utils import nome_arquivo_pdf

router = APIRouter(prefix="/processos", tags=["processos"])

# Gestão de Processos é um setor da ELITE (ver ARCHITECTURE.md seção 1.3/3).
_acesso_elite = require_operadora("ELITE")


@router.post("/import")
def importar(
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    try:
        resumo = processos_service.importar_planilha(db, path, usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "IMPORTOU_PROCESSOS", entidade="processo", detalhes=str(resumo))
    return resumo


@router.get("/relatorio")
def relatorio(
    periodo_ini: date,
    periodo_fim: date,
    agrupar_por: str = "assistente",
    pessoa: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    try:
        resultado = processos_service.gerar_relatorio(db, periodo_ini, periodo_fim, agrupar_por, pessoa)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    titulo = f"Relatório de {pessoa}" if pessoa else "Relatório geral da equipe"
    registrar(db, usuario, "GEROU_RELATORIO_PROCESSOS", entidade="processo", detalhes=titulo)
    return {
        "periodo_ini": resultado.periodo_ini,
        "periodo_fim": resultado.periodo_fim,
        "linhas": resultado.linhas,
        "total": resultado.total,
        "texto": processos_service.formatar_texto(resultado, titulo),
    }


@router.get("/relatorio.pdf")
def relatorio_pdf(
    periodo_ini: date,
    periodo_fim: date,
    agrupar_por: str = "assistente",
    pessoa: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    try:
        resultado = processos_service.gerar_relatorio(db, periodo_ini, periodo_fim, agrupar_por, pessoa)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    titulo = f"Relatório de {pessoa}" if pessoa else "Relatório geral da equipe"
    registrar(db, usuario, "GEROU_RELATORIO_PROCESSOS_PDF", entidade="processo", detalhes=titulo)
    pdf_bytes = gerar_pdf_processos(resultado, titulo)
    nome_arquivo = nome_arquivo_pdf("processos", pessoa or "equipe", str(periodo_ini), str(periodo_fim))
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/prazos-proximos")
def prazos_proximos(
    dias: int = 7,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    """Alerta de prazo dentro do sistema — lista de eventos com prazo fatal
    vencendo nos próximos `dias` dias (ou já vencidos). Sem envio por
    e-mail (decisão da Clara, ver DECISIONS.md)."""
    return processos_service.prazos_proximos(db, dias)


@router.post("/eventos/{evento_id}/resolver")
def resolver_evento(
    evento_id: int,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    try:
        evento = processos_service.marcar_resolvido(db, evento_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(db, usuario, "RESOLVEU_EVENTO_PROCESSO", entidade="evento_processo", entidade_id=evento_id)
    return {
        "id": evento.id,
        "resolvido": evento.resolvido,
        "resolvido_em": evento.resolvido_em,
        "status_prazo": processos_service.status_prazo(evento),
        "mes_referencia": evento.mes_referencia,
    }
