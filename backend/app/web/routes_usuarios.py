from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import PAPEIS_GLOBAIS, hash_senha, restaria_sem_admin
from app.db import get_db
from app.models import Setor, Usuario, UsuarioSetor
from app.services.auditoria import registrar
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/usuarios")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    usuarios = db.scalars(select(Usuario).order_by(Usuario.nome)).all()
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "usuarios": usuarios,
        # {usuario_id: {setor_id: papel}} — pré-computado pra marcar os checkboxes/selects
        # certos no formulário de edição de cada linha, sem lógica pesada no template.
        "vinculos_por_usuario": {u.id: {v.setor_id: v.papel for v in u.setores} for u in usuarios},
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


@router.post("/{usuario_id}")
async def editar(
    request: Request,
    usuario_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)

    alvo = db.get(Usuario, usuario_id)
    if alvo is None:
        contexto["erro"] = "Usuário não encontrado."
        return templates.TemplateResponse(request, "usuarios.html", contexto, status_code=404)

    nome = str(form.get("nome", "")).strip()
    email = str(form.get("email", "")).strip().lower()
    senha = str(form.get("senha", "")).strip()
    papel_global = str(form.get("papel_global") or "") or None

    if not nome or not email:
        contexto["erro"] = "Nome e e-mail são obrigatórios."
        return templates.TemplateResponse(request, "usuarios.html", contexto, status_code=400)
    if db.scalar(select(Usuario).where(Usuario.email == email, Usuario.id != usuario_id)) is not None:
        contexto["erro"] = "Já existe um usuário com esse e-mail."
        return templates.TemplateResponse(request, "usuarios.html", contexto, status_code=400)
    if restaria_sem_admin(db, usuario_id, papel_global):
        contexto["erro"] = "Não é possível remover o papel administrativo do último administrador do sistema."
        return templates.TemplateResponse(request, "usuarios.html", contexto, status_code=400)

    alvo.nome = nome
    alvo.email = email
    alvo.papel_global = papel_global
    if senha:
        alvo.senha_hash = hash_senha(senha)

    db.execute(delete(UsuarioSetor).where(UsuarioSetor.usuario_id == alvo.id))
    for setor in contexto["setores"]:
        if form.get(f"setor_{setor.id}"):
            papel_setor = str(form.get(f"papel_{setor.id}") or "COLABORADOR")
            db.add(UsuarioSetor(usuario_id=alvo.id, setor_id=setor.id, papel=papel_setor))

    db.commit()
    registrar(db, usuario, "EDITOU_USUARIO", entidade="usuario", entidade_id=alvo.id)

    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Usuário {nome} atualizado."
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
