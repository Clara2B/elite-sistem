from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.db import get_db
from app.models import Usuario
from app.services.auditoria import registrar
from app.services.funcionarios import (
    alterar_ativo_funcionario,
    atualizar_funcionario,
    criar_funcionario,
    excluir_funcionario,
    listar_funcionarios,
)

router = APIRouter(prefix="/funcionarios", tags=["funcionarios"])


class NovoFuncionario(BaseModel):
    nome: str


def _serializar(f) -> dict:
    return {"id": f.id, "nome": f.nome, "ativo": f.ativo}


@router.get("")
def listar(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista de funcionários (assistentes de Gestão de Processos) — alimenta
    o seletor "Funcionário" do relatório de Processos (Fase 6)."""
    return [_serializar(f) for f in listar_funcionarios(db, apenas_ativos=False)]


@router.post("")
def criar(
    payload: NovoFuncionario,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        funcionario = criar_funcionario(db, payload.nome)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "CRIOU_FUNCIONARIO", entidade="funcionario", entidade_id=funcionario.id)
    return _serializar(funcionario)


@router.patch("/{funcionario_id}")
def atualizar(
    funcionario_id: int,
    payload: NovoFuncionario,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        funcionario = atualizar_funcionario(db, funcionario_id, payload.nome)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "EDITOU_FUNCIONARIO", entidade="funcionario", entidade_id=funcionario_id)
    return _serializar(funcionario)


@router.patch("/{funcionario_id}/ativo")
def alterar_ativo(
    funcionario_id: int,
    ativo: bool,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        funcionario = alterar_ativo_funcionario(db, funcionario_id, ativo)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    registrar(
        db, usuario, "ATIVOU_FUNCIONARIO" if ativo else "DESATIVOU_FUNCIONARIO",
        entidade="funcionario", entidade_id=funcionario_id,
    )
    return _serializar(funcionario)


@router.delete("/{funcionario_id}")
def excluir(
    funcionario_id: int,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        excluir_funcionario(db, funcionario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "EXCLUIU_FUNCIONARIO", entidade="funcionario", entidade_id=funcionario_id)
    return {"ok": True}
