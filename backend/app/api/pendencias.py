from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.db import get_db
from app.services import pendencias as pendencias_service

router = APIRouter(prefix="/pendencias", tags=["pendencias"])


@router.post("/import")
def importar(arquivo: UploadFile, db: Session = Depends(get_db)):
    path = salvar_temp(arquivo)
    try:
        resumo = pendencias_service.importar_planilha(db, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return resumo


@router.get("/mensagens")
def mensagens(empresa: str, db: Session = Depends(get_db)):
    try:
        msgs = pendencias_service.gerar_mensagens(db, empresa)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
