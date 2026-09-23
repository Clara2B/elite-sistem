from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import PAPEIS_GLOBAIS, hash_senha
from app.db import get_db
from app.models import Setor, Usuario, UsuarioSetor
from app.services.auditoria import registrar
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/usuarios")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "usuarios": db.scalars(select(Usuario).order_by(Usuario.nome)).all(),
        "setores": db.scalars(select(Setor).order_by(Setor.operadora_id, Setor.nome)).all(),
        "papeis_globais": sorted(PAPEIS_GLOBAIS),
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(
    request: Request,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(request, "usuarios.html", _contexto_base(db, usuario))


@router.post("")
async def criar(
    request: Request,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)

    nome = str(form.get("nome", "")).strip()
    email = str(form.get("email", "")).strip().lower()
    senha = str(form.get("senha", ""))
    papel_global = str(form.get("papel_global") or "") or None

    if not nome or not email or not senha:
        contexto["erro"] = "Nome, e-mail e senha são obrigatórios."
        return templates.TemplateResponse(request, "usuarios.html", contexto, status_code=400)
    if db.scalar(select(Usuario).where(Usuario.email == email)) is not None:
        contexto["erro"] = "Já existe um usuário com esse e-mail."
        return templates.TemplateResponse(request, "usuarios.html", contexto, status_code=400)

    novo = Usuario(nome=nome, email=email, senha_hash=hash_senha(senha), papel_global=papel_global)
    db.add(novo)
    db.flush()

    for setor in contexto["setores"]:
        if form.get(f"setor_{setor.id}"):
            papel = str(form.get(f"papel_{setor.id}") or "COLABORADOR")
            db.add(UsuarioSetor(usuario_id=novo.id, setor_id=setor.id, papel=papel))

    db.commit()
    registrar(db, usuario, "CRIOU_USUARIO", entidade="usuario", entidade_id=novo.id)

    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Usuário {nome} criado."
    return templates.TemplateResponse(request, "usuarios.html", contexto)


@router.post("/{usuario_id}/ativo")
def alterar_ativo(
    usuario_id: int,
    ativo: bool,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    alvo = db.get(Usuario, usuario_id)
    if alvo is not None:
        alvo.ativo = ativo
        db.commit()
        registrar(
            db, usuario, "ATIVOU_USUARIO" if ativo else "DESATIVOU_USUARIO",
            entidade="usuario", entidade_id=usuario_id,
        )
    return RedirectResponse("/app/usuarios", status_code=303)
