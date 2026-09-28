"""Exclusão definitiva de Setor (2026-09-28, a pedido da Clara) — antes só
existia ativar/desativar (ver web/routes_setores.py). Mesma proteção contra
apagar histórico usada em `services/empresas.py::excluir_empresa`: um Setor
com usuário vinculado (`UsuarioSetor`) não pode ser excluído, pra não perder
esse vínculo silenciosamente — desativar continua sendo o caminho pra tirar
um setor de uso sem apagar histórico."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Setor, SetorModulo, UsuarioSetor


def excluir_setor(db: Session, setor_id: int) -> None:
    setor = db.get(Setor, setor_id)
    if setor is None:
        raise ValueError(f"Setor {setor_id} não encontrado.")

    vinculados = db.scalar(
        select(func.count()).select_from(UsuarioSetor).where(UsuarioSetor.setor_id == setor_id)
    )
    if vinculados:
        raise ValueError(
            f"Não é possível excluir '{setor.nome}': existe {vinculados} usuário(s) vinculado(s) a ele. "
            "Desative em vez de excluir, ou remova esse vínculo em Usuários primeiro."
        )

    db.execute(delete(SetorModulo).where(SetorModulo.setor_id == setor_id))
    db.delete(setor)
    db.commit()
