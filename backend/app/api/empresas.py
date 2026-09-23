from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.db import get_db
from app.models import Usuario
from app.services.auditoria import registrar
from app.services.empresas import (
    alterar_ativo_empresa,
    atualizar_empresa,
    criar_empresa,
    listar_empresas,
)

router = APIRouter(prefix="/empresas", tags=["empresas"])


class NovaEmpresa(BaseModel):
    nome: str
    cnpj: str | None = None


def _serializar(e) -> dict:
    return {"id": e.id, "nome": e.nome, "cnpj": e.cnpj, "ativo": e.ativo}


@router.get("")
def listar(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista de empresas-clientes (mesma lista usada por laudos, audiências,
    pendências e processos — não é por operadora, ver ARCHITECTURE.md 1.3).
    Alimenta o seletor de empresa nas telas (Fase 6)."""
    return [_serializar(e) for e in listar_empresas(db, apenas_ativas=False)]


@router.post("")
def criar(
    payload: NovaEmpresa,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Cadastro manual — só Admin Superior/T.I., mesma regra de
    `/usuarios`/`/setores` (dado compartilhado por todo o sistema)."""
    try:
        empresa = criar_empresa(db, payload.nome, payload.cnpj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "CRIOU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa.id)
    return _serializar(empresa)


@router.patch("/{empresa_id}")
def atualizar(
    empresa_id: int,
    payload: NovaEmpresa,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        empresa = atualizar_empresa(db, empresa_id, payload.nome, payload.cnpj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "EDITOU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa_id)
    return _serializar(empresa)


@router.patch("/{empresa_id}/ativo")
def alterar_ativo(
    empresa_id: int,
    ativo: bool,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        empresa = alterar_ativo_empresa(db, empresa_id, ativo)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(
        db, usuario, "ATIVOU_EMPRESA" if ativo else "DESATIVOU_EMPRESA",
        entidade="empresa_cliente", entidade_id=empresa_id,
    )
    return _serializar(empresa)
