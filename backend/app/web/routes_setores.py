"""Cadastro de Setores (2026-09-28, a pedido da Clara — "adicionar setores e
papéis para os setores") — antes só existiam pré-cadastrados via
DEFAULT_SETORES (app/db.py), sem nenhuma tela de administração; o vínculo
usuário-setor (com o papel LIDER/COLABORADOR dentro do setor) já existia em
Usuários e continua lá, sem mudança. Mesmo padrão de Empresas-clientes:
edição inline na tabela, com exclusão definitiva protegida contra vínculo
(ver services/setores.py::excluir_setor) — um Setor com usuário vinculado
não pode ser excluído, só desativado."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import MODULOS_OPERADORA, MODULOS_ROTULO, modulos_validos_para_operadora
from app.db import get_db
from app.models import Operadora, Setor, SetorModulo, Usuario
from app.services.auditoria import registrar
from app.services.setores import excluir_setor
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/setores")


def _modulos_por_setor(db: Session) -> dict[int, set[str]]:
    """Só traz uma entrada pro `setor_id` que tiver pelo menos uma linha em
    `SetorModulo` — um id ausente do dict é o estado padrão "sem restrição"
    (acesso a todas as abas válidas pra operadora do setor), igual à regra
    de `app/auth.py::modulos_acessiveis`."""
    resultado: dict[int, set[str]] = {}
    for linha in db.scalars(select(SetorModulo)):
        resultado.setdefault(linha.setor_id, set()).add(linha.modulo)
    return resultado


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "setores": db.scalars(select(Setor).order_by(Setor.operadora_id, Setor.nome)).all(),
        "operadoras": db.scalars(select(Operadora).order_by(Operadora.nome)).all(),
        "modulos_disponiveis": MODULOS_ROTULO,
        "modulos_operadora": MODULOS_OPERADORA,
        "modulos_por_setor": _modulos_por_setor(db),
        "mensagem": None,
        "erro": None,
    }


def _ler_modulos_do_form(form, operadora_id: int, db: Session) -> set[str] | None:
    """None = não restringir (mantém/deixa o setor com acesso total às abas
    da operadora). Um conjunto (nunca vazio — validado abaixo) = restringir
    exatamente a essas abas."""
    if str(form.get("restringir_modulos", "")).lower() not in {"true", "on", "1"}:
        return None
    operadora = db.get(Operadora, operadora_id)
    validos = modulos_validos_para_operadora(operadora.nome) if operadora else set()
    escolhidos = {m for m in form.getlist("modulos") if m in validos}
    if not escolhidos:
        raise ValueError("Selecione ao menos uma aba para restringir, ou desmarque \"Restringir abas\".")
    return escolhidos


def _salvar_modulos_do_setor(db: Session, setor_id: int, modulos: set[str] | None) -> None:
    db.execute(delete(SetorModulo).where(SetorModulo.setor_id == setor_id))
    if modulos:
        for modulo in modulos:
            db.add(SetorModulo(setor_id=setor_id, modulo=modulo))


@router.get("")
def tela(
    request: Request,
    erro: str | None = None,
    mensagem: str | None = None,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    contexto["erro"] = erro
    contexto["mensagem"] = mensagem
    return templates.TemplateResponse(request, "setores.html", contexto)


@router.post("")
async def criar(request: Request, usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db)):
    form = await request.form()
    contexto = _contexto_base(db, usuario)

    nome = str(form.get("nome", "")).strip()
    operadora_id = form.get("operadora_id")

    if not nome or not operadora_id:
        contexto["erro"] = "Nome e operadora são obrigatórios."
        return templates.TemplateResponse(request, "setores.html", contexto, status_code=400)

    try:
        modulos = _ler_modulos_do_form(form, int(operadora_id), db)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "setores.html", contexto, status_code=400)

    novo = Setor(nome=nome, operadora_id=int(operadora_id))
    db.add(novo)
    db.flush()
    _salvar_modulos_do_setor(db, novo.id, modulos)
    db.commit()
    registrar(db, usuario, "CRIOU_SETOR", entidade="setor", entidade_id=novo.id)

    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Setor {nome} criado."
    return templates.TemplateResponse(request, "setores.html", contexto)


@router.post("/{setor_id}")
async def editar(
    request: Request,
    setor_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)

    alvo = db.get(Setor, setor_id)
    if alvo is None:
        contexto["erro"] = "Setor não encontrado."
        return templates.TemplateResponse(request, "setores.html", contexto, status_code=404)

    nome = str(form.get("nome", "")).strip()
    operadora_id = form.get("operadora_id")
    if not nome or not operadora_id:
        contexto["erro"] = "Nome e operadora são obrigatórios."
        return templates.TemplateResponse(request, "setores.html", contexto, status_code=400)

    try:
        modulos = _ler_modulos_do_form(form, int(operadora_id), db)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "setores.html", contexto, status_code=400)

    alvo.nome = nome
    alvo.operadora_id = int(operadora_id)
    _salvar_modulos_do_setor(db, alvo.id, modulos)
    db.commit()
    registrar(db, usuario, "EDITOU_SETOR", entidade="setor", entidade_id=alvo.id)

    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Setor {nome} atualizado."
    return templates.TemplateResponse(request, "setores.html", contexto)


@router.post("/{setor_id}/ativo")
def alterar_ativo(
    setor_id: int,
    ativo: bool,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    alvo = db.get(Setor, setor_id)
    if alvo is not None:
        alvo.ativo = ativo
        db.commit()
        registrar(db, usuario, "ATIVOU_SETOR" if ativo else "DESATIVOU_SETOR", entidade="setor", entidade_id=setor_id)
    return RedirectResponse("/app/setores", status_code=303)


@router.post("/{setor_id}/excluir")
def excluir(
    setor_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Exclusão definitiva — a confirmação (obrigatória) acontece no
    navegador, num modal, antes desse POST (ver setores.html e
    static/app.js). Recusada se houver usuário vinculado (ver
    services/setores.py::excluir_setor)."""
    setor = db.get(Setor, setor_id)
    nome = setor.nome if setor else str(setor_id)
    try:
        excluir_setor(db, setor_id)
    except ValueError as e:
        return RedirectResponse(f"/app/setores?erro={quote(str(e))}", status_code=303)
    registrar(db, usuario, "EXCLUIU_SETOR", entidade="setor", entidade_id=setor_id)
    return RedirectResponse(f"/app/setores?mensagem={quote(f'Setor {nome} excluído definitivamente.')}", status_code=303)
