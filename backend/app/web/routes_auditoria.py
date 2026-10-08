"""Tela de Auditoria (2026-10-08, a pedido da Clara — "elevar o nível do
sistema com foco em otimização e produtividade"): o log já existia desde o
início do projeto (toda ação relevante chama `services/auditoria.py::
registrar`), só não tinha nenhuma tela pra consultar — dado já coletado,
só faltava expor. Admin-only, mesma área de Configuração das outras telas
administrativas (Usuários, Empresas-clientes, Assistentes, Setores,
Chamados)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.services import auditoria as auditoria_service
from app.web.areas_configuracao import AREAS_CONFIGURACAO
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/auditoria")


@router.get("")
def tela(
    request: Request,
    # str (não int/date) de propósito: o formulário de filtro é um GET
    # normal, e um <select>/<input type=date> deixado em branco manda o
    # campo como string vazia ("") em vez de simplesmente omiti-lo — FastAPI
    # recusa (422) tentar converter "" direto pra int/date. Convertidos à
    # mão logo abaixo, tratando "" como "sem filtro".
    usuario_id: str | None = None,
    acao: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    pagina: int = 1,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    usuario_id_int = int(usuario_id) if usuario_id else None
    data_inicio_data = date.fromisoformat(data_inicio) if data_inicio else None
    data_fim_data = date.fromisoformat(data_fim) if data_fim else None
    resultado = auditoria_service.listar(
        db, usuario_id=usuario_id_int, acao=acao or None,
        data_inicio=data_inicio_data, data_fim=data_fim_data, pagina=pagina,
    )
    return templates.TemplateResponse(
        request, "auditoria.html",
        {
            "usuario": usuario,
            "menu": itens_menu(db, usuario),
            "areas_configuracao": AREAS_CONFIGURACAO,
            "resultado": resultado,
            "humanizar_acao": auditoria_service.humanizar_acao,
            "usuarios": db.scalars(select(Usuario).order_by(Usuario.nome)).all(),
            "acoes": auditoria_service.acoes_distintas(db),
            "filtro": {
                "usuario_id": usuario_id_int, "acao": acao or None,
                "data_inicio": data_inicio_data, "data_fim": data_fim_data,
            },
        },
    )
