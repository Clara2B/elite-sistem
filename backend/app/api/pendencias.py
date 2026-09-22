from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.auth import get_current_user, operadoras_acessiveis
from app.db import get_db
from app.models import Usuario
from app.services import pendencias as pendencias_service
from app.services.auditoria import registrar

router = APIRouter(prefix="/pendencias", tags=["pendencias"])

# Pendências mistura cobranças da EXIMIA e da ELITE na mesma planilha (o
# campo `cobrador` é que diferencia, linha a linha — ver ARCHITECTURE.md
# seção 1.4). Por isso não dá pra travar a rota numa operadora só: o import
# só exige estar logado, e a geração de mensagens filtra o resultado pelas
# operadoras que o usuário pode ver.


@router.post("/import")
def importar(
    arquivo: UploadFile,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    try:
        resumo = pendencias_service.importar_planilha(db, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "IMPORTOU_PENDENCIAS", entidade="cobranca", detalhes=str(resumo))
    return resumo


@router.get("/mensagens")
def mensagens(
    empresa: str,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        msgs = pendencias_service.gerar_mensagens(db, empresa)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    acessiveis = operadoras_acessiveis(db, usuario)
    msgs = [m for m in msgs if m.cobrador in acessiveis]

    registrar(db, usuario, "GEROU_MENSAGENS_PENDENCIAS", entidade="empresa_cliente", entidade_id=empresa)
    return [
        {
            "empresa": m.empresa,
            "cobrador": m.cobrador,
            "total": m.total,
            "itens": m.itens,
            "texto": pendencias_service.formatar_texto(m),
        }
        for m in msgs
    ]
