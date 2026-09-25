from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.pdf_export import gerar_pdf_carta_cliente
from app.services import cartas as cartas_service
from app.services.auditoria import registrar
from app.utils import nome_arquivo_pdf
from app.web.auth import require_operadora_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/cartas")

_acesso_eximia = require_operadora_web("EXIMIA")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "erro": None,
        "valores_cliente": {},
    }


@router.get("")
def tela(request: Request, usuario: Usuario = Depends(_acesso_eximia), db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "cartas.html", _contexto_base(db, usuario))


@router.post("/convite-cliente")
def gerar_convite_cliente(
    request: Request,
    autor: str = Form(...),
    reu: str = Form(...),
    dia: date = Form(...),
    hora: str = Form(...),
    link: str = Form(...),
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["valores_cliente"] = {"autor": autor, "reu": reu, "dia": dia, "hora": hora, "link": link}
    try:
        convite = cartas_service.montar_convite_cliente(autor, reu, dia, hora, link)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "cartas.html", contexto)

    registrar(db, usuario, "GEROU_CARTA_CONVITE_CLIENTE", entidade="carta", entidade_id=convite.autor)
    pdf_bytes = gerar_pdf_carta_cliente(convite)
    nome_arquivo = nome_arquivo_pdf("Carta_Convite_Cliente", convite.autor)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
