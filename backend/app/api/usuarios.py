from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import PAPEIS_GLOBAIS, hash_senha, require_admin
from app.db import get_db
from app.models import Setor, Usuario, UsuarioSetor
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
