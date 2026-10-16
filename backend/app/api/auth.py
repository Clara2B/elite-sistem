from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    JANELA_BLOQUEIO_LOGIN_MINUTOS,
    _extrair_token,
    buscar_sessao,
    criar_sessao,
    excedeu_tentativas_login,
    get_current_user,
    hash_senha,
    verificar_senha,
)
from app.db import get_db
from app.models import Usuario
from app.services.auditoria import registrar

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    senha: str


class TrocaSenhaRequest(BaseModel):
    senha_atual: str
    senha_nova: str


def _perfil(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "papel_global": usuario.papel_global,
        "setores": [
            {"setor": v.setor.nome, "operadora": v.setor.operadora.nome, "papel": v.papel}
            for v in usuario.setores
        ],
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email_normalizado = payload.email.strip().lower()
    if excedeu_tentativas_login(db, email_normalizado):
        raise HTTPException(
            status_code=429,
            detail=f"Muitas tentativas de login para esse e-mail. Tente novamente em até "
            f"{JANELA_BLOQUEIO_LOGIN_MINUTOS} minutos.",
        )

    usuario = db.scalar(select(Usuario).where(Usuario.email == email_normalizado))
    if usuario is None or not usuario.ativo or not verificar_senha(payload.senha, usuario.senha_hash):
        registrar(db, usuario, "LOGIN_FALHOU", entidade="usuario", entidade_id=email_normalizado)
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

    sessao, token = criar_sessao(db, usuario)
    registrar(db, usuario, "LOGIN", entidade="usuario", entidade_id=usuario.id)
    return {"token": token, "expira_em": sessao.expira_em, "usuario": _perfil(usuario)}


@router.post("/logout")
def logout(
    token: str = Depends(_extrair_token),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessao = buscar_sessao(db, token)
    if sessao is not None:
        db.delete(sessao)
        db.commit()
    registrar(db, usuario, "LOGOUT", entidade="usuario", entidade_id=usuario.id)
    return {"ok": True}


@router.get("/me")
def me(usuario: Usuario = Depends(get_current_user)):
    return _perfil(usuario)


@router.post("/senha")
def trocar_senha(
    payload: TrocaSenhaRequest,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Troca a própria senha — primeiro uso esperado: quem entrou com o
    Admin Superior criado via bootstrap (ADMIN_BOOTSTRAP_EMAIL/SENHA, ver
    README.md) troca a senha logo no primeiro login."""
    if not verificar_senha(payload.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Senha atual incorreta.")
    usuario.senha_hash = hash_senha(payload.senha_nova)
    db.commit()
    registrar(db, usuario, "TROCOU_SENHA", entidade="usuario", entidade_id=usuario.id)
    return {"ok": True}
