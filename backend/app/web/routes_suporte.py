"""Pop-up de suporte (2026-09-28, a pedido da Clara) — botão flutuante
disponível em qualquer tela autenticada (ver templates/base.html), sem gate
de operadora/módulo: é um recurso do sistema como um todo, não de um
produto específico. Chamado a partir do JS via fetch (não form/redirect),
porque o botão pode ser aberto de qualquer página — devolve JSON, nunca uma
página HTML (ver app/main.py::_e_rota_html, que trata esse prefixo à
parte)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.services.auditoria import registrar
from app.services.suporte import enviar_chamado
from app.web.auth import usuario_logado_web

router = APIRouter(prefix="/app/suporte")


class NovoChamado(BaseModel):
    assunto: str
    descricao: str


@router.post("/chamado")
def abrir_chamado(
    payload: NovoChamado,
    usuario: Usuario = Depends(usuario_logado_web),
    db: Session = Depends(get_db),
):
    assunto = payload.assunto.strip()
    descricao = payload.descricao.strip()
    if not assunto or not descricao:
        return JSONResponse({"erro": "Preencha o assunto e a descrição do chamado."}, status_code=400)

    try:
        enviar_chamado(usuario, assunto, descricao)
    except ValueError as e:
        return JSONResponse({"erro": str(e)}, status_code=400)

    registrar(db, usuario, "ABRIU_CHAMADO_SUPORTE", entidade="chamado", detalhes=assunto)
    return {"ok": True}
