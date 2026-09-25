from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import require_operadora
from app.db import get_db
from app.models import Usuario
from app.pdf_export import gerar_pdf_carta_cliente
from app.services import cartas as cartas_service
from app.services.auditoria import registrar
from app.utils import nome_arquivo_pdf

router = APIRouter(prefix="/cartas", tags=["cartas"])

# Cartas é um produto da EXIMIA (mesma regra de acesso de Audiências).
_acesso_eximia = require_operadora("EXIMIA")


@router.get("/convite-cliente.pdf")
def convite_cliente_pdf(
    autor: str,
    reu: str,
    dia: date,
    hora: str,
    link: str,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    try:
        convite = cartas_service.montar_convite_cliente(autor, reu, dia, hora, link)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "GEROU_CARTA_CONVITE_CLIENTE", entidade="carta", entidade_id=convite.autor)
    pdf_bytes = gerar_pdf_carta_cliente(convite)
    nome_arquivo = nome_arquivo_pdf("Carta_Convite_Cliente", convite.autor)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
