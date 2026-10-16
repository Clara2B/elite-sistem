from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api._shared import remover_temp, salvar_temp
from app.config import settings
from app.db import get_db
from app.models import Banco, Usuario
from app.services.auditoria import registrar
from app.services.bancos import (
    alterar_ativo_banco,
    atualizar_banco,
    criar_banco,
    excluir_banco,
    importar_do_google_sheets,
    importar_planilha_bancos,
    listar_bancos,
)
from app.web.auth import require_modulo_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/bancos")

# Mesmo acesso de Audiências/Cartas (2026-10-16, a pedido da Clara: "reaproveita
# o acesso" — sem módulo novo só pra isso) — ver app/auth.py::MODULOS_OPERADORA.
_acesso_eximia = require_modulo_web("AUDIENCIAS")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "bancos": listar_bancos(db, apenas_ativos=False),
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(
    request: Request,
    erro: str | None = None,
    mensagem: str | None = None,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["erro"] = erro
    contexto["mensagem"] = mensagem
    return templates.TemplateResponse(request, "bancos.html", contexto)


@router.post("")
async def criar(
    request: Request,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    nome = str(form.get("nome", "")).strip()
    cnpj = str(form.get("cnpj", "")).strip()
    cnpj_alternativo = str(form.get("cnpj_alternativo", "")).strip()
    email = str(form.get("email", "")).strip()
    if not nome or not cnpj or not email:
        contexto["erro"] = "Nome, CNPJ e e-mail são obrigatórios."
        return templates.TemplateResponse(request, "bancos.html", contexto, status_code=400)
    try:
        banco = criar_banco(db, nome, cnpj, email, cnpj_alternativo)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "bancos.html", contexto, status_code=400)
    registrar(db, usuario, "CRIOU_BANCO", entidade="banco", entidade_id=banco.id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Banco {banco.nome} cadastrado."
    return templates.TemplateResponse(request, "bancos.html", contexto)


@router.post("/import")
async def importar(
    request: Request,
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    contexto = _contexto_base(db, usuario)
    try:
        resumo = importar_planilha_bancos(db, path)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "bancos.html", contexto, status_code=400)
    finally:
        remover_temp(path)
    registrar(db, usuario, "IMPORTOU_BANCOS", entidade="banco", detalhes=str(resumo))
    contexto = _contexto_base(db, usuario)
    partes = [f"{resumo.criados} criado(s), {resumo.atualizados} atualizado(s)"]
    if resumo.rejeitados:
        partes.append(f"{len(resumo.rejeitados)} rejeitado(s): {'; '.join(resumo.rejeitados)}")
    contexto["mensagem"] = " — ".join(partes)
    return templates.TemplateResponse(request, "bancos.html", contexto)


@router.post("/importar-da-planilha")
def importar_sheets(
    request: Request,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    """Lê direto da aba "E-MAIL BANCO" da planilha de controle configurada
    em GOOGLE_SHEETS_ID — sem upload de arquivo (2026-10-16, a pedido da
    Clara). Mesmo upsert do botão de importar .xlsx; os dois convivem."""
    contexto = _contexto_base(db, usuario)
    if not settings.google_sheets_id:
        contexto["erro"] = "GOOGLE_SHEETS_ID não está configurado."
        return templates.TemplateResponse(request, "bancos.html", contexto, status_code=400)
    try:
        resumo = importar_do_google_sheets(db, settings.google_sheets_id)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "bancos.html", contexto, status_code=400)
    except Exception as e:  # noqa: BLE001 — qualquer falha da API do Google (rede, permissão) vira mensagem amigável, não 500
        contexto["erro"] = f"Não foi possível consultar a planilha de controle: {e}"
        return templates.TemplateResponse(request, "bancos.html", contexto, status_code=502)
    registrar(db, usuario, "IMPORTOU_BANCOS_GOOGLE_SHEETS", entidade="banco", detalhes=str(resumo))
    contexto = _contexto_base(db, usuario)
    partes = [f"{resumo.criados} criado(s), {resumo.atualizados} atualizado(s)"]
    if resumo.rejeitados:
        partes.append(f"{len(resumo.rejeitados)} rejeitado(s): {'; '.join(resumo.rejeitados)}")
    contexto["mensagem"] = " — ".join(partes)
    return templates.TemplateResponse(request, "bancos.html", contexto)


@router.post("/{banco_id}")
async def editar(
    request: Request,
    banco_id: int,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    nome = str(form.get("nome", "")).strip()
    cnpj = str(form.get("cnpj", "")).strip()
    cnpj_alternativo = str(form.get("cnpj_alternativo", "")).strip()
    email = str(form.get("email", "")).strip()
    if not nome or not cnpj or not email:
        contexto["erro"] = "Nome, CNPJ e e-mail são obrigatórios."
        return templates.TemplateResponse(request, "bancos.html", contexto, status_code=400)
    try:
        banco = atualizar_banco(db, banco_id, nome, cnpj, email, cnpj_alternativo)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "bancos.html", contexto, status_code=400)
    registrar(db, usuario, "EDITOU_BANCO", entidade="banco", entidade_id=banco_id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Banco {banco.nome} atualizado."
    return templates.TemplateResponse(request, "bancos.html", contexto)


@router.post("/{banco_id}/ativo")
def alterar_ativo(
    banco_id: int,
    ativo: bool,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    try:
        alterar_ativo_banco(db, banco_id, ativo)
    except ValueError:
        pass
    else:
        registrar(
            db, usuario, "ATIVOU_BANCO" if ativo else "DESATIVOU_BANCO",
            entidade="banco", entidade_id=banco_id,
        )
    return RedirectResponse("/app/bancos", status_code=303)


@router.post("/{banco_id}/excluir")
def excluir(
    banco_id: int,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    """Exclusão definitiva — a confirmação (obrigatória) acontece no
    navegador, num modal, antes desse POST (mesmo padrão de
    funcionarios.html/empresas.html)."""
    banco = db.get(Banco, banco_id)
    nome = banco.nome if banco else str(banco_id)
    try:
        excluir_banco(db, banco_id)
    except ValueError as e:
        return RedirectResponse(f"/app/bancos?erro={quote(str(e))}", status_code=303)
    registrar(db, usuario, "EXCLUIU_BANCO", entidade="banco", entidade_id=banco_id)
    return RedirectResponse(f"/app/bancos?mensagem={quote(f'Banco {nome} excluído definitivamente.')}", status_code=303)
