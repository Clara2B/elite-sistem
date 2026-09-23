"""Autenticação para as páginas HTML (Fase 6) — cookie de sessão, não
Bearer token. A API JSON (`app/auth.py`) continua exigindo
`Authorization: Bearer <token>` normalmente; isso aqui é só para o
navegador, que não tem como anexar esse cabeçalho em navegação comum.

O cookie guarda o mesmo token opaco de `Sessao` (app/models.py) — mesma
tabela, mesma expiração, mesmo "sair" apaga a sessão de verdade. HttpOnly
(JS não lê o cookie, mitiga roubo por XSS) e `secure` dinâmico conforme o
esquema da requisição (funciona tanto em produção HTTPS quanto em dev
local HTTP, sem precisar de uma variável de ambiente extra).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import COOKIE_SESSAO, PAPEIS_GLOBAIS, operadoras_acessiveis
from app.db import get_db
from app.models import Sessao, Usuario

COOKIE_NOME = COOKIE_SESSAO  # mesmo nome de cookie que app/auth.py::_extrair_token lê


class PrecisaLogin(Exception):
    """Sem sessão válida numa página HTML — capturada em app/main.py, que
    redireciona para /login (a API usa 401 JSON; a página usa isso)."""


class SemPermissao(Exception):
    """Logado, mas sem papel_global — capturada em app/main.py, que
    responde uma página 403 simples em vez do redirecionamento de login."""


def definir_cookie_sessao(response, request: Request, token: str, expira_em: datetime) -> None:
    # max_age (segundos), não expires: o projeto usa datetime naive (UTC)
    # por convenção (ver pyproject.toml) — o set_cookie do Starlette exige
    # datetime com tzinfo quando recebe `expires`, o que quebraria essa
    # convenção só pra essa chamada. max_age evita o problema de vez.
    max_age = max(0, int((expira_em - datetime.utcnow()).total_seconds()))
    response.set_cookie(
        COOKIE_NOME,
        token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=max_age,
    )


def usuario_logado_web(request: Request, db: Session = Depends(get_db)) -> Usuario:
    token = request.cookies.get(COOKIE_NOME)
    if not token:
        raise PrecisaLogin
    sessao = db.get(Sessao, token)
    if sessao is None or sessao.expira_em < datetime.utcnow():
        raise PrecisaLogin
    usuario = db.get(Usuario, sessao.usuario_id)
    if usuario is None or not usuario.ativo:
        raise PrecisaLogin
    return usuario


def admin_logado_web(usuario: Usuario = Depends(usuario_logado_web)) -> Usuario:
    if usuario.papel_global not in PAPEIS_GLOBAIS:
        raise SemPermissao
    return usuario


def require_operadora_web(nome_operadora: str):
    """Equivalente web de `app.auth.require_operadora` — mesma regra de
    acesso por operadora, mas responde a página 403 (SemPermissao) em vez
    do 403 JSON da API."""

    def _checar(
        usuario: Usuario = Depends(usuario_logado_web),
        db: Session = Depends(get_db),
    ) -> Usuario:
        if nome_operadora not in operadoras_acessiveis(db, usuario):
            raise SemPermissao
        return usuario

    return _checar
