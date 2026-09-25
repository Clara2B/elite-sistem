from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.pdf_export import gerar_pdf_carta_banco, gerar_pdf_carta_cliente
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
        "valores_banco": {},
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


@router.post("/convite-banco")
def gerar_convite_banco(
    request: Request,
    banco_nome: str = Form(...),
    banco_cnpj: str = Form(...),
    nome: str = Form(...),
    cpf: str = Form(...),
    contrato: str = Form(...),
    data: date = Form(...),
    hora: str = Form(...),
    link: str = Form(...),
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["valores_banco"] = {
        "banco_nome": banco_nome, "banco_cnpj": banco_cnpj, "nome": nome, "cpf": cpf,
        "contrato": contrato, "data": data, "hora": hora, "link": link,
    }
    try:
        convite = cartas_service.montar_convite_banco(
            banco_nome, banco_cnpj, nome, cpf, contrato, data, hora, link,
        )
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "cartas.html", contexto)

    registrar(db, usuario, "GEROU_CARTA_CONVITE_BANCO", entidade="carta", entidade_id=convite.nome)
    pdf_bytes = gerar_pdf_carta_banco(convite)
    nome_arquivo = nome_arquivo_pdf("Carta_Convite_Banco", convite.nome)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
