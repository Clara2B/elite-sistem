from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import PAPEIS_GLOBAIS, hash_senha, require_admin, restaria_sem_admin
from app.db import get_db
from app.models import Operadora, Setor, Usuario, UsuarioSetor
from app.services.auditoria import registrar

router = APIRouter(tags=["usuarios"])


class SetorVinculo(BaseModel):
    setor_id: int
    papel: str  # 'LIDER' | 'COLABORADOR'


class NovoUsuario(BaseModel):
    nome: str
    email: str
    senha: str
    papel_global: str | None = None  # 'ADMIN_SUPERIOR' | 'ADMIN_TI' | None
    setores: list[SetorVinculo] = []


class EdicaoUsuario(BaseModel):
    nome: str
    email: str
    papel_global: str | None = None  # 'ADMIN_SUPERIOR' | 'ADMIN_TI' | None
    senha: str | None = None  # None/vazio = mantém a senha atual
    setores: list[SetorVinculo] | None = None  # None = não mexe nos vínculos atuais


class NovoSetor(BaseModel):
    nome: str
    operadora_id: int


class EdicaoSetor(BaseModel):
    nome: str
    operadora_id: int


def _perfil(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "papel_global": usuario.papel_global,
        "ativo": usuario.ativo,
        "setores": [
            {"setor_id": v.setor_id, "setor": v.setor.nome, "operadora": v.setor.operadora.nome, "papel": v.papel}
            for v in usuario.setores
        ],
    }


@router.get("/setores")
def listar_setores(_: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    return [
        {"id": s.id, "nome": s.nome, "operadora": s.operadora.nome, "ativo": s.ativo}
        for s in db.scalars(select(Setor).order_by(Setor.operadora_id, Setor.nome))
    ]


@router.post("/setores")
def criar_setor(payload: NovoSetor, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    if db.get(Operadora, payload.operadora_id) is None:
        raise HTTPException(status_code=400, detail=f"Operadora {payload.operadora_id} não existe.")
    setor = Setor(nome=payload.nome.strip(), operadora_id=payload.operadora_id)
    db.add(setor)
    db.commit()
    registrar(db, admin, "CRIOU_SETOR", entidade="setor", entidade_id=setor.id)
    db.refresh(setor)
    return {"id": setor.id, "nome": setor.nome, "operadora": setor.operadora.nome, "ativo": setor.ativo}


@router.patch("/setores/{setor_id}")
def editar_setor(
    setor_id: int, payload: EdicaoSetor, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)
):
    setor = db.get(Setor, setor_id)
    if setor is None:
        raise HTTPException(status_code=404, detail="Setor não encontrado.")
    if db.get(Operadora, payload.operadora_id) is None:
        raise HTTPException(status_code=400, detail=f"Operadora {payload.operadora_id} não existe.")
    setor.nome = payload.nome.strip()
    setor.operadora_id = payload.operadora_id
    db.commit()
    registrar(db, admin, "EDITOU_SETOR", entidade="setor", entidade_id=setor.id)
    db.refresh(setor)
    return {"id": setor.id, "nome": setor.nome, "operadora": setor.operadora.nome, "ativo": setor.ativo}


@router.patch("/setores/{setor_id}/ativo")
def alterar_ativo_setor(
    setor_id: int, ativo: bool, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)
):
    setor = db.get(Setor, setor_id)
    if setor is None:
        raise HTTPException(status_code=404, detail="Setor não encontrado.")
    setor.ativo = ativo
    db.commit()
    registrar(db, admin, "ATIVOU_SETOR" if ativo else "DESATIVOU_SETOR", entidade="setor", entidade_id=setor_id)
    return {"id": setor.id, "nome": setor.nome, "operadora": setor.operadora.nome, "ativo": setor.ativo}


@router.get("/usuarios")
def listar_usuarios(admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    return [_perfil(u) for u in db.scalars(select(Usuario).order_by(Usuario.nome))]


@router.post("/usuarios")
def criar_usuario(payload: NovoUsuario, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.papel_global is not None and payload.papel_global not in PAPEIS_GLOBAIS:
        raise HTTPException(status_code=400, detail=f"papel_global precisa ser um de {sorted(PAPEIS_GLOBAIS)} ou nulo.")
    email = payload.email.strip().lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)) is not None:
        raise HTTPException(status_code=400, detail="Já existe um usuário com esse e-mail.")

    usuario = Usuario(
        nome=payload.nome.strip(),
        email=email,
        senha_hash=hash_senha(payload.senha),
        papel_global=payload.papel_global,
    )
    db.add(usuario)
    db.flush()

    for vinculo in payload.setores:
        setor = db.get(Setor, vinculo.setor_id)
        if setor is None:
            raise HTTPException(status_code=400, detail=f"Setor {vinculo.setor_id} não existe.")
        if vinculo.papel not in {"LIDER", "COLABORADOR"}:
            raise HTTPException(status_code=400, detail="papel do setor precisa ser 'LIDER' ou 'COLABORADOR'.")
        db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel=vinculo.papel))

    db.commit()
    registrar(db, admin, "CRIOU_USUARIO", entidade="usuario", entidade_id=usuario.id)
    db.refresh(usuario)
    return _perfil(usuario)


@router.patch("/usuarios/{usuario_id}")
def editar_usuario(
    usuario_id: int,
    payload: EdicaoUsuario,
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if payload.papel_global is not None and payload.papel_global not in PAPEIS_GLOBAIS:
        raise HTTPException(status_code=400, detail=f"papel_global precisa ser um de {sorted(PAPEIS_GLOBAIS)} ou nulo.")

    email = payload.email.strip().lower()
    if db.scalar(select(Usuario).where(Usuario.email == email, Usuario.id != usuario_id)) is not None:
        raise HTTPException(status_code=400, detail="Já existe um usuário com esse e-mail.")
    if restaria_sem_admin(db, usuario_id, payload.papel_global):
        raise HTTPException(
            status_code=400, detail="Não é possível remover o papel administrativo do último administrador do sistema."
        )

    usuario.nome = payload.nome.strip()
    usuario.email = email
    usuario.papel_global = payload.papel_global
    if payload.senha:
        usuario.senha_hash = hash_senha(payload.senha)

    if payload.setores is not None:
        db.execute(delete(UsuarioSetor).where(UsuarioSetor.usuario_id == usuario.id))
        for vinculo in payload.setores:
            setor = db.get(Setor, vinculo.setor_id)
            if setor is None:
                raise HTTPException(status_code=400, detail=f"Setor {vinculo.setor_id} não existe.")
            if vinculo.papel not in {"LIDER", "COLABORADOR"}:
                raise HTTPException(status_code=400, detail="papel do setor precisa ser 'LIDER' ou 'COLABORADOR'.")
            db.add(UsuarioSetor(usuario_id=usuario.id, setor_id=setor.id, papel=vinculo.papel))

    db.commit()
    registrar(db, admin, "EDITOU_USUARIO", entidade="usuario", entidade_id=usuario.id)
    db.refresh(usuario)
    return _perfil(usuario)


@router.patch("/usuarios/{usuario_id}/ativo")
def alterar_ativo(
    usuario_id: int,
    ativo: bool,
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    usuario.ativo = ativo
    db.commit()
    registrar(db, admin, "ATIVOU_USUARIO" if ativo else "DESATIVOU_USUARIO", entidade="usuario", entidade_id=usuario_id)
    return _perfil(usuario)
