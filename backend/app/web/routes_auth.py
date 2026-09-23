from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import criar_sessao, verificar_senha
from app.db import get_db
from app.models import Sessao, Usuario
from app.services.auditoria import registrar
from app.web.auth import COOKIE_NOME, definir_cookie_sessao, usuario_logado_web
from app.web.templates import templates

router = APIRouter()


@router.get("/login")
def tela_login(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NOME)
    if token:
        sessao = db.get(Sessao, token)
        if sessao is not None and sessao.expira_em >= datetime.utcnow():
            return RedirectResponse("/", status_code=303)  # já logado
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
def processar_login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    email_normalizado = email.strip().lower()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email_normalizado))
    if usuario is None or not usuario.ativo or not verificar_senha(senha, usuario.senha_hash):
        registrar(db, usuario, "LOGIN_FALHOU", entidade="usuario", entidade_id=email_normalizado)
        return templates.TemplateResponse(
            request, "login.html",
            {"erro": "E-mail ou senha incorretos.", "email": email},
            status_code=401,
        )

    sessao = criar_sessao(db, usuario)
    registrar(db, usuario, "LOGIN", entidade="usuario", entidade_id=usuario.id)
    resposta = RedirectResponse("/", status_code=303)
    definir_cookie_sessao(resposta, request, sessao.token, sessao.expira_em)
    return resposta


@router.post("/logout")
def processar_logout(
    request: Request,
    usuario: Usuario = Depends(usuario_logado_web),
    db: Session = Depends(get_db),
):
    token = request.cookies.get(COOKIE_NOME)
    if token:
        sessao = db.get(Sessao, token)
        if sessao is not None:
            db.delete(sessao)
            db.commit()
    registrar(db, usuario, "LOGOUT", entidade="usuario", entidade_id=usuario.id)
    resposta = RedirectResponse("/login", status_code=303)
    resposta.delete_cookie(COOKIE_NOME)
    return resposta
