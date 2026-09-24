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
    excluir_empresa,
    listar_empresas,
    sincronizar_lista_oficial,
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


@router.delete("/{empresa_id}")
def excluir(
    empresa_id: int,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Exclusão definitiva — bloqueada se houver laudo/audiência/cobrança/
    processo vinculado (ver services/empresas.py::excluir_empresa)."""
    try:
        excluir_empresa(db, empresa_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    registrar(db, usuario, "EXCLUIU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa_id)
    return {"ok": True}


@router.post("/sincronizar-lista-oficial")
def sincronizar(
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Sincroniza com a lista oficial de 48 empresas (nome + CNPJ) que a
    Clara mandou em PDF (2026-09-24) — cria as que faltam, atualiza CNPJ das
    existentes, exclui de verdade quem não está na lista (bloqueado se tiver
    histórico vinculado — ver services/empresas.py::sincronizar_lista_oficial).
    Irreversível para quem for excluído; só Admin Superior/T.I."""
    resumo = sincronizar_lista_oficial(db)
    registrar(
        db, usuario, "SINCRONIZOU_EMPRESAS_OFICIAIS", entidade="empresa_cliente",
        detalhes=(
            f"{len(resumo.criadas)} criada(s), {len(resumo.atualizadas_cnpj)} CNPJ atualizado(s), "
            f"{len(resumo.excluidas)} excluída(s), {len(resumo.nao_excluidas_por_vinculo)} não excluída(s) por vínculo"
        ),
    )
    return {
        "criadas": resumo.criadas,
        "atualizadas_cnpj": resumo.atualizadas_cnpj,
        "sem_mudanca": resumo.sem_mudanca,
        "excluidas": resumo.excluidas,
        "nao_excluidas_por_vinculo": resumo.nao_excluidas_por_vinculo,
    }
