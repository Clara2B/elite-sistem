from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Usuario
from app.services.empresas import listar_empresas

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("")
def listar(
    _: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista de empresas-clientes (mesma lista usada por laudos, audiências,
    pendências e processos — não é por operadora, ver ARCHITECTURE.md 1.3).
    Alimenta o seletor de empresa nas telas (Fase 6)."""
    return [
        {"id": e.id, "nome": e.nome, "cnpj": e.cnpj, "ativo": e.ativo}
        for e in listar_empresas(db, apenas_ativas=False)
    ]
