"""Autenticação e autorização — Fase 4.

Login individual (e-mail + senha com hash bcrypt), sessão por token opaco
(não JWT: evita gerenciar segredo de assinatura, e "sair" apaga a sessão de
verdade em vez de esperar o token expirar sozinho). Segregação por
operadora: só `papel_global` (ADMIN_SUPERIOR ou ADMIN_TI) enxerga as duas
operadoras — qualquer outro usuário fica restrito às operadoras dos setores
a que pertence (ver ARCHITECTURE.md seção 2.6 e seção 1.9 item 3).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Sessao, Usuario, UsuarioSetor

SESSAO_DURACAO_HORAS = 12
PAPEIS_GLOBAIS = {"ADMIN_SUPERIOR", "ADMIN_TI"}


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("ascii"))
    except ValueError:
        return False  # hash malformado/vazio — nunca deveria acontecer, mas não derruba o login


def criar_sessao(db: Session, usuario: Usuario) -> Sessao:
    sessao = Sessao(
        token=secrets.token_hex(32),
        usuario_id=usuario.id,
        expira_em=datetime.utcnow() + timedelta(hours=SESSAO_DURACAO_HORAS),
    )
    db.add(sessao)
    db.commit()
    return sessao


def _extrair_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autenticado. Envie 'Authorization: Bearer <token>'.")
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Usuario:
    token = _extrair_token(authorization)
    sessao = db.get(Sessao, token)
    if sessao is None or sessao.expira_em < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")
    usuario = db.get(Usuario, sessao.usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Usuário inativo ou não encontrado.")
    return usuario


def require_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if usuario.papel_global not in PAPEIS_GLOBAIS:
        raise HTTPException(status_code=403, detail="Ação restrita a Admin Superior ou T.I.")
    return usuario


def operadoras_acessiveis(db: Session, usuario: Usuario) -> set[str]:
    """Nomes das operadoras que o usuário pode enxergar. Admin Superior/T.I.
    veem as duas; qualquer outro usuário só as operadoras dos setores a que
    pertence (regra dura — ver ARCHITECTURE.md 1.9 item 3)."""
    if usuario.papel_global in PAPEIS_GLOBAIS:
        return {"EXIMIA", "ELITE"}
    vinculos = db.scalars(select(UsuarioSetor).where(UsuarioSetor.usuario_id == usuario.id))
    return {v.setor.operadora.nome for v in vinculos}


def require_operadora(nome_operadora: str):
    """Dependency factory: garante que o usuário logado tem acesso à
    operadora dona do módulo (ex.: Laudos = ELITE, Audiências = EXIMIA)."""

    def _checar(
        usuario: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        if nome_operadora not in operadoras_acessiveis(db, usuario):
            raise HTTPException(
                status_code=403,
                detail=f"Sem acesso aos dados da {nome_operadora}.",
            )
        return usuario

    return _checar
